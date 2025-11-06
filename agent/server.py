"""
AgentCore Runtime Server

BedrockAgentCoreAppを使用してAgentCore Runtimeで実行されるサーバー
"""

import asyncio
import contextvars
import json
import logging
import os
import sys
from typing import Any

import boto3
from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from bedrock_agentcore.identity.auth import requires_access_token

# Context variable for user_id (for AgentCore Identity SDK)
current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar('current_user_id', default='default-user')

# ログ設定 - 標準出力に明示的に出力
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# BedrockAgentCoreAppアプリケーション
app = BedrockAgentCoreApp()

# AWS クライアント
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)
bedrock_agentcore = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

# AgentCore Gateway URL and Target Name（環境変数またはAPIから取得）
def get_gateway_config():
    """
    Gateway URLとTarget Nameを取得する
    環境変数が設定されていればそれを使用し、なければAPI経由で取得

    Returns:
        Tuple of (gateway_url, gateway_id, target_name)
    """
    gateway_url = os.environ.get("GATEWAY_URL", "")
    gateway_id = os.environ.get("GATEWAY_ID", "")
    gateway_target_name = os.environ.get("GATEWAY_TARGET_NAME", "")

    if gateway_url and gateway_target_name:
        return gateway_url, gateway_id, gateway_target_name

    # Gateway名から取得
    gateway_name = os.environ.get("GATEWAY_NAME", "line-agent-calendar-gateway")
    target_name = os.environ.get("GATEWAY_TARGET_NAME", "calendar-operations")

    try:
        bedrock_agentcore_control = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION)

        # Gatewayを一覧取得して該当するものを見つける
        response = bedrock_agentcore_control.list_gateways()
        logger.info(f"ListGateways response: {response}")
        for gateway in response.get("items", []):
            logger.info(f"Checking gateway: {gateway}")
            if gateway.get("name") == gateway_name:
                gateway_id = gateway.get("gatewayId")

                # Gateway詳細を取得してURLを入手
                try:
                    gateway_detail = bedrock_agentcore_control.get_gateway(gatewayIdentifier=gateway_id)
                    gateway_url = gateway_detail.get("gatewayUrl")
                    logger.info(f"Found Gateway: {gateway_name} -> {gateway_url}")
                except Exception as e:
                    logger.error(f"Failed to get Gateway detail: {e}")
                    gateway_url = ""

                # Gateway Targetを取得
                try:
                    targets_response = bedrock_agentcore_control.list_gateway_targets(gatewayIdentifier=gateway_id)
                    for target in targets_response.get("items", []):
                        if target.get("name") == target_name:
                            target_name_found = target.get("name")
                            logger.info(f"Found Target: {target_name_found}")
                            return gateway_url, gateway_id, target_name_found
                except Exception as e:
                    logger.error(f"Failed to get Gateway Target: {e}")

                return gateway_url, gateway_id, ""

        logger.warning(f"Gateway not found: {gateway_name}")
    except Exception as e:
        logger.error(f"Failed to get Gateway config from API: {e}")

    return "", "", ""

GATEWAY_URL, GATEWAY_ID, GATEWAY_TARGET_NAME = get_gateway_config()

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
                    "description": "取得終了日時（ISO 8601形式、例: 2025-10-30T23:59:59+09:00）"
                },
                "max_results": {
                    "type": "integer",
                    "description": "取得する予定の最大数（デフォルト: 10）"
                }
            },
            "required": ["time_min", "time_max"]
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
                    "description": "予定の詳細説明（オプション）"
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
                    "description": "新しいタイトル（オプション）"
                },
                "start_time": {
                    "type": "string",
                    "description": "新しい開始日時（ISO 8601形式、オプション）"
                },
                "end_time": {
                    "type": "string",
                    "description": "新しい終了日時（ISO 8601形式、オプション）"
                },
                "description": {
                    "type": "string",
                    "description": "新しい詳細説明（オプション）"
                },
                "location": {
                    "type": "string",
                    "description": "新しい場所（オプション）"
                }
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": "カレンダーから予定を削除する。",
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
    logger.info(f"execute_calendar_tool called: tool_name={tool_name}, GATEWAY_URL={GATEWAY_URL}, GATEWAY_TARGET_NAME={GATEWAY_TARGET_NAME}")

    if not GATEWAY_URL:
        logger.error("Gateway URL not configured")
        return {"success": False, "error": "Gateway URL not configured"}

    try:
        # MCP tools/call リクエストを構築
        # ツール名を{TargetName}___{ToolName}形式に変換
        mcp_tool_name = f"{GATEWAY_TARGET_NAME}___{tool_name}"

        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": mcp_tool_name,
                "arguments": tool_input
            }
        }

        logger.info(f"Calling Gateway: {GATEWAY_URL} with tool={mcp_tool_name}")

        # GatewayにHTTPリクエストを送信（IAM認証のみ）
        import requests
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        # リクエストを準備（Workload Access Tokenは不要、IAM認証のみ）
        headers = {
            "Content-Type": "application/json",
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


@requires_access_token(
    provider_name="google-calendar-provider",
    scopes=["https://www.googleapis.com/auth/calendar"],
    auth_flow="USER_FEDERATION",
    callback_url="https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback",
    on_auth_url=lambda url: logger.info(f"Authorization required: {url}"),
    force_authentication=False,
)
async def execute_calendar_tool_with_oauth(
    *,
    access_token: str,
    tool_name: str,
    tool_input: dict[str, Any],
    user_id: str = "default-user"
) -> dict[str, Any]:
    """
    OAuth2認証付きでカレンダーツールを実行する

    Args:
        access_token: Google OAuth access token (auto-injected by decorator)
        tool_name: ツール名
        tool_input: ツールの入力パラメータ
        user_id: ユーザーID

    Returns:
        ツールの実行結果
    """
    # access_tokenをtool_inputに追加
    tool_input_with_token = {**tool_input, "access_token": access_token}

    # Gateway経由でLambdaを呼び出し
    return execute_calendar_tool(tool_name, tool_input_with_token, user_id)


async def generate_ai_response(user_message: str, user_id: str = "default-user") -> str:
    """
    Bedrockを使ってAI応答を生成する（ツール呼び出しに対応）

    Args:
        user_message: ユーザーからのメッセージ
        user_id: ユーザーID（OAuth2トークン取得に使用）

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

                        # ツールを実行（OAuth2認証付き）
                        tool_result = await execute_calendar_tool_with_oauth(
                            access_token="",  # Decorator will inject the actual token
                            tool_name=tool_name,
                            tool_input=tool_input,
                            user_id=user_id
                        )

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


@app.entrypoint
async def agent_invocation(payload: dict[str, Any], context: RequestContext) -> dict[str, str]:
    """
    AgentCore Runtimeからの呼び出しエントリーポイント

    BedrockAgentCoreAppが自動的にWorkloadAccessTokenなどのヘッダーを処理します。

    Args:
        payload: リクエストペイロード（prompt, user_id, metadata）
        context: RequestContext（headers, session_idなどを含む）

    Returns:
        エージェントの応答
    """
    try:
        # ペイロードからpromptを取得
        user_message = payload.get("prompt", "")
        user_id = payload.get("user_id", "default-user")

        logger.info(f"Received invocation: prompt='{user_message[:50]}...', user_id={user_id}")

        # RequestContextからヘッダーを確認（デバッグ用）
        if hasattr(context, 'request_headers'):
            logger.info(f"Request headers: {context.request_headers}")

        # Set user_id in context for AgentCore Identity SDK
        current_user_id.set(user_id)

        # Bedrockを使ってAI応答を生成
        agent_response = await generate_ai_response(user_message, user_id=user_id)

        return {
            "response": agent_response,
            "metadata": {"user_id": user_id}
        }

    except Exception as e:
        logger.error(f"Error processing invocation: {e}", exc_info=True)
        return {
            "response": f"エラーが発生しました: {str(e)}",
            "metadata": {"error": str(e)}
        }


if __name__ == "__main__":
    # BedrockAgentCoreApp.run()を呼び出してサーバーを起動
    logger.info("Starting AgentCore Runtime server with BedrockAgentCoreApp")
    app.run()
