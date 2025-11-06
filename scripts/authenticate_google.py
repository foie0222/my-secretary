"""
Google Calendar OAuth2 Authentication Script

このスクリプトを実行して、共有カレンダー用のGoogle認証を完了させます。
全LINEユーザーが同じGoogleアカウントのカレンダーを共有します。
"""

import asyncio
import contextvars
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token, current_user_id

# AWS Region
AWS_REGION = "ap-northeast-1"

# Credential Provider Name
PROVIDER_NAME = "google-calendar-provider"

# Workload Identity Name
WORKLOAD_NAME = "line_agent_secretary-Z8wcZvH0aN"

# 固定のUser ID（全LINEユーザーで共有）
SHARED_USER_ID = "shared-calendar-user"

# Google Calendar Scopes
SCOPES = ["https://www.googleapis.com/auth/calendar"]


@requires_access_token(
    provider_name=PROVIDER_NAME,
    scopes=SCOPES,
    auth_flow="USER_FEDERATION",
    callback_url="https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback",
    on_auth_url=lambda url: print(f"\n🔗 認証URLをブラウザで開いてください:\n{url}\n"),
    force_authentication=True,
)
async def authenticate_google(*, access_token: str):
    """Google Calendar認証を実行"""
    print(f"\n✅ 認証成功！")
    print(f"Access Token取得: {access_token[:50]}...")
    print(f"\n認証情報が保存されました。")
    print(f"User ID: {SHARED_USER_ID}")
    print(f"以降、全LINEユーザーがこのGoogleアカウントのカレンダーを共有します。")
    return access_token


async def main():
    print("=" * 60)
    print("Google Calendar OAuth2 認証（共有カレンダー）")
    print("=" * 60)
    print(f"\nWorkload: {WORKLOAD_NAME}")
    print(f"Provider: {PROVIDER_NAME}")
    print(f"User ID: {SHARED_USER_ID} (固定)")
    print(f"Region: {AWS_REGION}")
    print(f"Scopes: {', '.join(SCOPES)}")
    print("\n" + "=" * 60)

    # 固定のuser_idを設定
    current_user_id.set(SHARED_USER_ID)

    try:
        await authenticate_google(access_token="")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
