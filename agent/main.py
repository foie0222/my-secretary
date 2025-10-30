"""
LINE Agent Secretary - Main Entry Point

AgentCore Runtimeで実行されるエージェントのエントリーポイント

このファイルは以下の2つのモードで動作します:
1. AgentCore Runtime (本番環境)
2. ローカル開発環境（FastAPIサーバー）
"""

import logging
import os
from typing import Any

from agent.config import get_config
from agent.line_handler import LineWebhookHandler

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# グローバル設定とハンドラー
config = get_config()
line_handler = LineWebhookHandler(config)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AgentCore RuntimeまたはAWS Lambdaから呼び出されるハンドラー

    Args:
        event: Lambda イベント（LINE Webhook リクエスト）
        context: Lambda コンテキスト

    Returns:
        Lambda レスポンス
    """
    try:
        # LINE Webhookリクエストを処理
        body = event.get("body", "")
        signature = event.get("headers", {}).get("x-line-signature", "")

        if not signature:
            logger.error("Missing x-line-signature header")
            return {"statusCode": 400, "body": "Missing signature"}

        # Webhookを処理
        line_handler.handle_webhook(body, signature)

        return {"statusCode": 200, "body": "OK"}

    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        return {"statusCode": 500, "body": "Internal Server Error"}


if __name__ == "__main__":
    # ローカル開発環境用のFastAPIサーバー
    import uvicorn
    from fastapi import FastAPI, Header, Request

    app = FastAPI(title="LINE Agent Secretary")

    @app.post("/webhook")
    async def webhook(
        request: Request,
        x_line_signature: str = Header(None),
    ) -> dict[str, str]:
        """LINE Webhook エンドポイント"""
        body = await request.body()

        if not x_line_signature:
            logger.error("Missing x-line-signature header")
            return {"status": "error", "message": "Missing signature"}

        try:
            line_handler.handle_webhook(body.decode("utf-8"), x_line_signature)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Error handling webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @app.get("/health")
    async def health() -> dict[str, str]:
        """ヘルスチェックエンドポイント"""
        return {"status": "healthy"}

    # ローカルサーバーを起動
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting local server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
