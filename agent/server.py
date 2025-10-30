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

# AWS クライアント
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)
bedrock_agentcore = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

# AgentCore Gateway URL（環境変数から取得）
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
GATEWAY_ID = os.environ.get("GATEWAY_ID", "")

# Claudeに渡すツール定義
CALENDAR_TOOLS = [
    {
        "name": "list_calendar_events",
        "description": "カレンダーの予定を取得する。日時の範囲を指定して予定一覧を取得できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {
                    "type": "string",
                    "description": "取得開始日時（ISO 8601形式、例: 2025-10-30T00:00:00+09:00）"
                },
                "time_max": {
                    "type": "string",
                    "description": "取得終了日時（ISO 8601形式、例: 2025-11-06T23:59:59+09:00）"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大取得件数（デフォルト: 10）"
                }
            }
        }
    },
    {
        "name": "create_calendar_event",
        "description": "カレンダーに新しい予定を作成する。",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "予定のタイトル"
                },
                "start_time": {
                    "type": "string",
                    "description": "開始日時（ISO 8601形式、例: 2025-10-30T14:00:00+09:00）"
                },
                "end_time": {
                    "type": "string",
                    "description": "終了日時（ISO 8601形式、例: 2025-10-30T15:00:00+09:00）"
                },
                "description": {
                    "type": "string",
                    "description": "予定の説明（オプション）"
                },
                "location": {
                    "type": "string",
                    "description": "場所（オプション）"
                }
            },
            "required": ["summary", "start_time", "end_time"]
        }
    },
    {
        "name": "update_calendar_event",
        "description": "既存のカレンダー予定を更新する。",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "更新する予定のID"
                },
                "summary": {
                    "type": "string",
                    "description": "予定のタイトル（オプション）"
                },
                "start_time": {
                    "type": "string",
                    "description": "開始日時（ISO 8601形式、オプション）"
                },
                "end_time": {
                    "type": "string",
                    "description": "終了日時（ISO 8601形式、オプション）"
                },
                "description": {
                    "type": "string",
                    "description": "予定の説明（オプション）"
                },
                "location": {
                    "type": "string",
                    "description": "場所（オプション）"
                }
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": "カレンダーの予定を削除する。",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "削除する予定のID"
                }
            },
            "required": ["event_id"]
        }
    }
]


class InvocationRequest(BaseModel):
    """AgentCore Runtimeからの呼び出しリクエスト"""

    prompt: str
    user_id: str | None = None
    metadata: dict[str, Any] | None = None


class InvocationResponse(BaseModel):
    """AgentCore Runtimeへの応答"""

    response: str
    metadata: dict[str, Any] | None = None


def execute_calendar_tool(tool_name: str, tool_input: dict[str, Any], user_id: str = "default-user") -> dict[str, Any]:
    """
    カレンダーツールを実行する（Gateway経由でLambda関数を呼び出す）

    Args:
        tool_name: ツール名（list_calendar_events, create_calendar_event, etc.）
        tool_input: ツールの入力パラメータ
        user_id: ユーザーID（OAuth2認証用）

    Returns:
        ツールの実行結果
    """
    if not GATEWAY_URL:
        return {"success": False, "error": "Gateway URL not configured"}

    try:
        # Workload Access Tokenを取得
        try:
            workload_token_response = bedrock_agentcore.get_workload_access_token_for_user_id(
                workloadIdentityName=f"line_agent_secretary-Z8wcZvH0aN",
                userId=user_id
            )
            workload_token = workload_token_response['accessToken']
            logger.info(f"Got workload access token for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to get workload access token: {e}")
            return {"success": False, "error": f"Authentication error: {str(e)}"}

        # MCP tools/call リクエストを構築
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_input
            }
        }

        logger.info(f"Calling Gateway: {GATEWAY_URL} with tool={tool_name}")

        # GatewayにHTTPリクエストを送信（IAM認証付き）
        import requests
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        # リクエストを準備
        headers = {
            "Content-Type": "application/json",
            "X-Workload-Access-Token": workload_token
        }

        request = AWSRequest(
            method="POST",
            url=GATEWAY_URL,
            data=json.dumps(mcp_request),
            headers=headers
        )

        # SigV4署名を追加
        credentials = boto3.Session().get_credentials()
        SigV4Auth(credentials, "bedrock-agentcore", AWS_REGION).add_auth(request)

        # リクエストを送信
        prepped = request.prepare()
        response = requests.post(
            prepped.url,
            headers=dict(prepped.headers),
            data=prepped.body,
            timeout=30
        )

        logger.info(f"Gateway response: {response.status_code}")

        if response.status_code != 200:
            return {"success": False, "error": f"Gateway error: {response.status_code} - {response.text}"}

        result = response.json()
        logger.info(f"Gateway result: {result}")

        # MCP responseからcontentを抽出
        if "result" in result and "content" in result["result"]:
            content = result["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                # テキストコンテンツを抽出
                text_content = content[0].get("text", "")
                try:
                    return json.loads(text_content)
                except:
                    return {"success": True, "result": text_content}

        return result

    except Exception as e:
        logger.error(f"Error executing calendar tool: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


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
    Bedrockを使ってAI応答を生成する（ツール呼び出しに対応）

    Args:
        user_message: ユーザーからのメッセージ

    Returns:
        AIが生成した応答
    """
    try:
        # Claude Sonnet 4.5を使用（Global Inference Profile）
        model_id = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

        # システムプロンプト
        system_prompt = """あなたはLINE秘書アシスタントです。
ユーザーの質問に対して、親切で簡潔な日本語で回答してください。

Googleカレンダーの操作ツールを使って、以下のことができます：
- 予定の確認・検索
- 新しい予定の作成
- 既存の予定の更新
- 予定の削除

日時を指定する際は、ISO 8601形式（例: 2025-10-30T14:00:00+09:00）を使用してください。
現在の日時を基準に適切に計算してください。"""

        # 会話履歴（messages配列）
        messages = [
            {
                "role": "user",
                "content": user_message
            }
        ]

        # ツール呼び出しループ（最大10回まで）
        max_iterations = 10
        for iteration in range(max_iterations):
            # リクエストボディを作成
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": messages,
                "tools": CALENDAR_TOOLS  # カレンダーツールを追加
            }

            logger.info(f"Iteration {iteration + 1}: Invoking Bedrock")

            # Bedrock Runtimeを呼び出し
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )

            # レスポンスを解析
            response_body = json.loads(response["body"].read())
            stop_reason = response_body.get("stop_reason")
            content = response_body.get("content", [])

            logger.info(f"Stop reason: {stop_reason}")

            # アシスタントの応答をメッセージ履歴に追加
            messages.append({
                "role": "assistant",
                "content": content
            })

            # tool_useがある場合はツールを実行
            if stop_reason == "tool_use":
                tool_results = []

                for block in content:
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name")
                        tool_input = block.get("input")
                        tool_use_id = block.get("id")

                        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

                        # ツールを実行
                        tool_result = execute_calendar_tool(tool_name, tool_input)

                        # ツール結果を追加
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })

                # ツール結果をメッセージ履歴に追加
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # 次のイテレーションでClaudeを再度呼び出す
                continue

            # end_turnの場合は終了
            elif stop_reason == "end_turn":
                # テキスト応答を抽出
                for block in content:
                    if block.get("type") == "text":
                        return block.get("text", "応答がありませんでした。")

                return "応答がありませんでした。"

            else:
                # 想定外のstop_reason
                logger.warning(f"Unexpected stop_reason: {stop_reason}")
                return "申し訳ございません。応答を生成できませんでした。"

        # 最大イテレーションに達した場合
        logger.error("Max iterations reached")
        return "申し訳ございません。処理に時間がかかりすぎました。"

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
