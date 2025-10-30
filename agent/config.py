"""
Agent Configuration

環境変数と設定を管理する
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """アプリケーション設定"""

    # AgentCore設定
    agentcore_gateway_url: str = Field(
        ...,
        description="AgentCore Gateway MCP URL",
    )

    agentcore_runtime_id: str | None = Field(
        None,
        description="AgentCore Runtime ID (デプロイ後に設定)",
    )

    # LINE設定
    line_channel_secret: str = Field(
        ...,
        description="LINE Channel Secret",
    )

    line_channel_access_token: str = Field(
        ...,
        description="LINE Channel Access Token",
    )

    # AWS設定
    aws_region: str = Field(
        default="ap-northeast-1",
        description="AWS Region",
    )

    secrets_manager_secret_name: str = Field(
        default="line-agent-secretary/line-credentials",
        description="Secrets Manager secret name for LINE credentials",
    )

    # AgentCore Identity設定
    google_credential_provider_name: str = Field(
        default="google-calendar-provider",
        description="AgentCore Identity OAuth2 Credential Provider name for Google",
    )

    # ログレベル
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_config() -> Config:
    """設定を取得する"""
    return Config()
