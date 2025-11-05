"""
LINE Webhook Handler

LINEからのWebhookを受け取り、AgentCore Runtimeを呼び出して応答を返す
"""

import json
import logging
import os
from typing import Any

import boto3
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
    AgentCore Runtimeを呼び出す

    Args:
        input_text: ユーザーからの入力テキスト
        user_id: LINEユーザーID

    Returns:
        エージェントからの応答
    """
    try:
        # ペイロードを準備
        payload = json.dumps({"prompt": input_text}).encode()

        # カスタムヘッダーを追加するためのイベントハンドラー
        def add_user_id_header(request, **kwargs):
            """Add X-Amzn-Bedrock-AgentCore-Runtime-User-Id header for user-specific OAuth tokens."""
            logger.info(f"Adding X-Amzn-Bedrock-AgentCore-Runtime-User-Id header with user_id: {user_id}")
            request.headers.add_header('X-Amzn-Bedrock-AgentCore-Runtime-User-Id', user_id)
            logger.info(f"Request headers after adding: {dict(request.headers)}")

        # イベントハンドラーを登録
        event_system = bedrock_client.meta.events
        event_name = 'before-sign.bedrock-agentcore.InvokeAgentRuntime'
        handler_id = event_system.register_first(event_name, add_user_id_header)

        logger.info(f"Invoking AgentCore Runtime with user_id: {user_id}")

        try:
            # AgentCore Runtime呼び出し
            response = bedrock_client.invoke_agent_runtime(
                agentRuntimeArn=AGENT_RUNTIME_ARN,
                runtimeSessionId=user_id,  # LINEユーザーIDをセッションIDとして使用
                payload=payload,
            )
        finally:
            # イベントハンドラーを解除
            event_system.unregister(event_name, handler_id)

        # ストリーミングレスポンスを処理
        if "text/event-stream" in response.get("contentType", ""):
            # ストリーミングレスポンスの処理
            content = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]
                        content.append(line_text)
            return "\n".join(content) if content else "申し訳ございません。応答を生成できませんでした。"

        elif response.get("contentType") == "application/json":
            # JSON レスポンスの処理
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode("utf-8"))
            result = json.loads("".join(content))
            return result.get("response", "申し訳ございません。応答を生成できませんでした。")

        else:
            # その他のレスポンス
            logger.warning(f"Unexpected content type: {response.get('contentType')}")
            return "申し訳ございません。応答を生成できませんでした。"

    except Exception as e:
        logger.error(f"Error invoking agent runtime: {e}", exc_info=True)
        raise
