"""
Google Calendar OAuth2 Authentication Script

このスクリプトを実行して、共有カレンダー用のGoogle認証を完了させます。
全LINEユーザーが同じGoogleアカウントのカレンダーを共有します。
"""

import asyncio
import time
from bedrock_agentcore.services.identity import IdentityClient

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

# Callback URL
CALLBACK_URL = "https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback"


async def authenticate_google():
    """Google Calendar認証を実行"""

    print("=" * 70)
    print("Google Calendar OAuth2 認証（共有カレンダー）")
    print("=" * 70)
    print(f"\nWorkload: {WORKLOAD_NAME}")
    print(f"Provider: {PROVIDER_NAME}")
    print(f"User ID: {SHARED_USER_ID} (固定)")
    print(f"Region: {AWS_REGION}")
    print(f"Scopes: {', '.join(SCOPES)}")
    print("\n" + "=" * 70)

    # IdentityClient初期化
    client = IdentityClient(AWS_REGION)

    print("\n📝 ステップ1: Workload Access Token取得中...")

    # Workload Access Tokenを取得
    workload_access_token_response = client.get_workload_access_token(
        workload_name=WORKLOAD_NAME,
        user_id=SHARED_USER_ID
    )
    workload_access_token = workload_access_token_response["workloadAccessToken"]

    print("✅ Workload Access Token取得完了")

    print("\n📝 ステップ2: OAuth2 Token取得中...")
    print("   認証が必要な場合、URLが表示されます...\n")

    try:
        # OAuth2 Tokenを取得
        token_response = await client.get_token(
            provider_name=PROVIDER_NAME,
            agent_identity_token=workload_access_token,
            scopes=SCOPES,
            on_auth_url=lambda url: print(f"\n🔗 認証URLをブラウザで開いてください:\n{url}\n"),
            auth_flow="USER_FEDERATION",
            callback_url=CALLBACK_URL,
            force_authentication=True,
        )

        access_token = token_response.get("access_token")

        if access_token:
            print("\n✅ 認証成功！")
            print(f"Access Token取得: {access_token[:50]}...")
            print(f"\n認証情報が保存されました。")
            print(f"User ID: {SHARED_USER_ID}")
            print(f"以降、全LINEユーザーがこのGoogleアカウントのカレンダーを共有します。")
            print("\n" + "=" * 70)
            return True
        else:
            print("\n❌ Access Tokenが取得できませんでした")
            return False

    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(authenticate_google())
    exit(0 if success else 1)
