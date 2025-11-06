"""
LINE Webhook Handler

LINEからのWebhookを受け取り、AgentCore Runtimeを呼び出して応答を返す
"""

import json
import logging
import os
from typing import Any

import boto3
import requests
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# Cognito認証ヘルパーをインポート
from cognito_auth import get_jwt_token_simple

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 環境変数
CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# LINE Bot API初期化
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Bedrock AgentCore Runtime client
bedrock_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda関数のエントリーポイント

    LINEからのWebhookを処理する

    Args:
        event: API Gatewayからのイベント
        context: Lambda コンテキスト

    Returns:
        レスポンス
    """
    # 署名検証
    signature = event["headers"].get("x-line-signature", "")
    body = event["body"]

    logger.info(f"Received webhook: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        return {"statusCode": 400, "body": json.dumps("Invalid signature")}
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}

    return {"statusCode": 200, "body": json.dumps("OK")}


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent) -> None:
    """
    テキストメッセージの処理

    Args:
        event: LINEメッセージイベント
    """
    user_id = event.source.user_id
    user_message = event.message.text

    logger.info(f"User {user_id} sent: {user_message}")

    try:
        # AgentCore Runtimeを呼び出し
        response_text = invoke_agent_runtime(user_message, user_id)

        # LINEに応答
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=response_text)],
                )
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="申し訳ございません。エラーが発生しました。")],
                )
            )


def invoke_agent_runtime(input_text: str, user_id: str) -> str:
    """
    AgentCore Runtimeを呼び出す（JWT認証）

    Args:
        input_text: ユーザーからの入力テキスト
        user_id: LINEユーザーID

    Returns:
        エージェントからの応答
    """
    try:
        logger.info(f"Getting JWT token for LINE user: {user_id}")

        # Cognito JWTトークンを取得
        jwt_token = get_jwt_token_simple(user_id)

        logger.info("JWT token retrieved successfully")

        # Runtime URLを構築
        runtime_url = f"https://{AGENT_RUNTIME_ARN.split('/')[-1]}.runtime.bedrock-agentcore.{AWS_REGION}.amazonaws.com/invocations"

        # ペイロードを準備
        payload = {"prompt": input_text}

        # HTTPSリクエストヘッダー（JWT Bearer Token使用）
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"Invoking Runtime with JWT auth: {runtime_url}")

        # AgentCore Runtimeを呼び出し
        response = requests.post(
            runtime_url,
            headers=headers,
            json=payload,
            timeout=120,
        )

        # レスポンスをチェック
        if response.status_code != 200:
            logger.error(f"Runtime returned error: {response.status_code} - {response.text}")
            return f"エラーが発生しました（ステータス: {response.status_code}）"

        # JSONレスポンスをパース
        result = response.json()
        agent_response = result.get("response", "申し訳ございません。応答を生成できませんでした。")

        logger.info("Successfully received response from Runtime")
        return agent_response

    except requests.exceptions.Timeout:
        logger.error("Runtime invocation timed out")
        return "タイムアウトしました。もう一度お試しください。"

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {e}", exc_info=True)
        return "通信エラーが発生しました。"

    except Exception as e:
        logger.error(f"Error invoking agent runtime: {e}", exc_info=True)
        raise
