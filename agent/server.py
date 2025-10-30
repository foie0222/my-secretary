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

        # TODO: AgentCore Gatewayを使ってClaudeと対話し、カレンダー機能を利用
        # 現在は簡単なエコー応答
        agent_response = f"受け取ったメッセージ: {request.prompt}"

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
