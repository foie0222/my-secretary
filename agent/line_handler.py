"""
LINE Webhook Handler

LINEからのメッセージを受信し、Strands Agentsで処理する
"""

import logging
from typing import Any

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

from agent.config import Config

logger = logging.getLogger(__name__)


class LineWebhookHandler:
    """LINE Webhookハンドラー"""

    def __init__(self, config: Config):
        """
        Args:
            config: アプリケーション設定
        """
        self.config = config

        # LINE Messaging APIクライアントの設定
        configuration = Configuration(access_token=config.line_channel_access_token)
        self.api_client = ApiClient(configuration)
        self.messaging_api = MessagingApi(self.api_client)

        # Webhookハンドラーの設定
        self.handler = WebhookHandler(config.line_channel_secret)

        # メッセージイベントのハンドラーを登録
        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_text_message(event: MessageEvent) -> None:
            """テキストメッセージを処理する"""
            self._handle_text_message(event)

    def _handle_text_message(self, event: MessageEvent) -> None:
        """
        テキストメッセージを処理する

        Args:
            event: LINE メッセージイベント
        """
        # ユーザーからのメッセージを取得
        user_message = event.message.text
        logger.info(f"Received message: {user_message}")

        # TODO: Strands Agentsでメッセージを処理
        # 現在は簡単な応答を返す
        response_text = f"受信しました: {user_message}\n\n（エージェント機能は実装中です）"

        # LINEに返信
        self.messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=response_text)],
            )
        )

    async def process_agent_request(self, user_message: str) -> str:
        """
        エージェントにメッセージを送信して応答を取得する

        TODO: Strands Agentsとの統合を実装

        Args:
            user_message: ユーザーからのメッセージ

        Returns:
            エージェントからの応答
        """
        # TODO: Strands Agentsを使ってメッセージを処理
        # - AgentCore Gatewayに接続
        # - ツール（カレンダー操作）を利用可能にする
        # - ユーザーのメッセージに応答

        return f"エージェント応答（実装予定）: {user_message}"

    def handle_webhook(self, body: str, signature: str) -> None:
        """
        LINE Webhookリクエストを処理する

        Args:
            body: リクエストボディ
            signature: X-Line-Signature ヘッダー

        Raises:
            InvalidSignatureError: 署名が無効な場合
        """
        try:
            self.handler.handle(body, signature)
        except InvalidSignatureError:
            logger.error("Invalid signature. Check your channel secret.")
            raise
