"""
LINE Webhook Handler

LINEからのWebhookを受け取り、AgentCore Runtimeを呼び出して応答を返す
"""

import json
import logging
import os
import urllib.parse
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
OAUTH_SESSION_TABLE_NAME = os.environ.get("OAUTH_SESSION_TABLE_NAME", "line-agent-oauth-sessions")

# LINE Bot API初期化
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Bedrock AgentCore Runtime client
bedrock_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

# DynamoDB client
dynamodb = boto3.resource("dynamodb")
session_table = dynamodb.Table(OAUTH_SESSION_TABLE_NAME)


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


def store_oauth_session(session_id: str, line_user_id: str, cognito_token: str) -> None:
    """
    OAuth セッション情報を DynamoDB に保存

    Args:
        session_id: OAuth セッションID（認証URLから抽出）
        line_user_id: LINE User ID
        cognito_token: Cognito JWT access token
    """
    import time

    try:
        session_table.put_item(
            Item={
                "session_id": session_id,
                "line_user_id": line_user_id,
                "cognito_token": cognito_token,
                "ttl": int(time.time()) + 600,  # 10分後に自動削除
            }
        )
        logger.info(f"Stored OAuth session: session_id={session_id}, line_user_id={line_user_id}")
    except Exception as e:
        logger.error(f"Failed to store OAuth session: {e}", exc_info=True)
        raise


def extract_auth_url(response_text: str) -> str | None:
    """
    AgentCore Runtime の応答から認証URLを抽出

    Args:
        response_text: Runtime からの応答テキスト

    Returns:
        認証URL（見つからない場合はNone）
    """
    import re

    # パターン1: "Authorization URL: https://..."
    match = re.search(r"Authorization URL:\s*(https?://[^\s]+)", response_text)
    if match:
        return match.group(1)

    # パターン2: "認証してください: https://..."
    match = re.search(r"認証してください[：:]\s*(https?://[^\s]+)", response_text)
    if match:
        return match.group(1)

    # パターン3: URLのみ（https://accounts.google.com/... など）
    match = re.search(r"(https://accounts\.google\.com/[^\s]+)", response_text)
    if match:
        return match.group(1)

    return None


def extract_session_id_from_url(auth_url: str) -> str | None:
    """
    認証URLからsession_idを抽出

    Args:
        auth_url: 認証URL

    Returns:
        session_id（見つからない場合はNone）
    """
    import re
    from urllib.parse import parse_qs, urlparse

    # URLをパースしてクエリパラメータを取得
    parsed = urlparse(auth_url)
    query_params = parse_qs(parsed.query)

    # state パラメータから session_id を抽出
    if "state" in query_params:
        state = query_params["state"][0]
        # state 内の session_id を抽出（形式: session_id=xxx）
        match = re.search(r"session_id=([^&]+)", state)
        if match:
            return match.group(1)

    # redirect_uri パラメータから session_id を抽出
    if "redirect_uri" in query_params:
        redirect_uri = query_params["redirect_uri"][0]
        # redirect_uri に session_id が含まれている場合
        match = re.search(r"session_id=([^&]+)", redirect_uri)
        if match:
            return match.group(1)

    logger.warning(f"Failed to extract session_id from auth URL: {auth_url}")
    return None


def invoke_agent_runtime(input_text: str, user_id: str) -> str:
    """
    AgentCore Runtimeを呼び出す（JWT認証 + OAuth対応）

    Args:
        input_text: ユーザーからの入力テキスト
        user_id: LINEユーザーID

    Returns:
        エージェントからの応答
    """
    try:
        logger.info(f"Getting JWT token for LINE user: {user_id}")

        # Cognito JWTトークンを取得（ユーザーが存在しない場合は自動作成）
        jwt_token = get_jwt_token_simple(user_id)

        logger.info("JWT token retrieved successfully")

        # Runtime ARNをURLエンコード
        escaped_agent_arn = urllib.parse.quote(AGENT_RUNTIME_ARN, safe='')

        # Runtime URLを構築（JWT認証の場合の正しい形式）
        runtime_url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

        # ペイロードを準備
        payload = {"prompt": input_text}

        # HTTPSリクエストヘッダー（JWT Bearer Token使用）
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"line-session-{user_id}",
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

        # 認証URLが含まれているか確認
        auth_url = extract_auth_url(agent_response)
        if auth_url:
            logger.info(f"Authentication required. Auth URL: {auth_url}")

            # session_idを抽出
            session_id = extract_session_id_from_url(auth_url)
            if session_id:
                # OAuth セッション情報を DynamoDB に保存
                store_oauth_session(session_id, user_id, jwt_token)
                logger.info(f"OAuth session stored for session_id: {session_id}")
            else:
                logger.warning("Failed to extract session_id from auth URL")

            # 認証URLをユーザーフレンドリーなメッセージに変換
            return (
                f"Google Calendar との連携が必要です。\n\n"
                f"以下のリンクをタップして認証を完了してください：\n{auth_url}\n\n"
                f"認証完了後、LINEに戻って再度お試しください。"
            )

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
