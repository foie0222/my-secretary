"""
AgentCore Runtime Server

AgentCore Runtimeで実行されるHTTPサーバー
/ping、/invocations、/webhook エンドポイントを提供する
"""

import hashlib
import hmac
import json
import logging
import os
from typing import Any

import boto3
from fastapi import FastAPI, HTTPException, Request, Header
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage as LineTextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from pydantic import BaseModel

from agent.config import get_config

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション
app = FastAPI(title="LINE Agent Secretary - AgentCore Runtime")

# LINE Bot設定（環境変数から取得）
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

# LINE Bot API設定
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Bedrock Runtime クライアント
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)


class InvocationRequest(BaseModel):
    """AgentCore Runtimeからの呼び出しリクエスト"""

    prompt: str
    user_id: str | None = None
    metadata: dict[str, Any] | None = None


class InvocationResponse(BaseModel):
    """AgentCore Runtimeへの応答"""

    response: str
    metadata: dict[str, Any] | None = None


@app.get("/ping")
async def ping() -> dict[str, str]:
    """
    ヘルスチェックエンドポイント

    AgentCore Runtimeがコンテナの健全性を確認するために使用

    Returns:
        {"status": "Healthy"}
    """
    return {"status": "Healthy"}


def generate_ai_response(user_message: str) -> str:
    """
    Bedrockを使ってAI応答を生成する

    Args:
        user_message: ユーザーからのメッセージ

    Returns:
        AIが生成した応答
    """
    try:
        # Claude Sonnet 4.5を使用
        model_id = "anthropic.claude-sonnet-4-5-20250929-v1:0"

        # システムプロンプト
        system_prompt = """あなたはLINE秘書アシスタントです。
ユーザーの質問に対して、親切で簡潔な日本語で回答してください。
必要に応じて、スケジュール管理やリマインダーの設定などをサポートします。"""

        # リクエストボディを作成
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        }

        # Bedrock Runtimeを呼び出し
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )

        # レスポンスを解析
        response_body = json.loads(response["body"].read())

        # テキスト応答を抽出
        if response_body.get("content") and len(response_body["content"]) > 0:
            return response_body["content"][0]["text"]
        else:
            return "申し訳ございません。応答を生成できませんでした。"

    except Exception as e:
        logger.error(f"Error generating AI response: {e}", exc_info=True)
        return f"エラーが発生しました: {str(e)}"


@app.post("/invocations")
async def invocations(request: InvocationRequest) -> InvocationResponse:
    """
    AgentCore Runtimeからの呼び出しエンドポイント

    このエンドポイントは、AgentCore Runtimeがエージェントを呼び出すときに使用される。
    ユーザーからのメッセージ（prompt）を受け取り、エージェントの応答を返す。

    Args:
        request: 呼び出しリクエスト（prompt, user_id, metadata）

    Returns:
        エージェントの応答
    """
    try:
        logger.info(f"Received invocation request: prompt='{request.prompt[:50]}...', user_id={request.user_id}")

        # Bedrockを使ってAI応答を生成
        agent_response = generate_ai_response(request.prompt)

        return InvocationResponse(
            response=agent_response,
            metadata={"user_id": request.user_id},
        )

    except Exception as e:
        logger.error(f"Error processing invocation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> dict[str, str]:
    """
    追加のヘルスチェックエンドポイント

    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    # AgentCore Runtime環境で実行
    import uvicorn

    port = 8080  # AgentCore Runtimeの要件
    logger.info(f"Starting AgentCore Runtime server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
