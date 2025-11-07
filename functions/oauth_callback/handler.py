"""
OAuth2 Callback Handler for 3-legged OAuth flow

Google OAuth 認証後のコールバックを処理し、AgentCore Identity にトークンを登録する
"""

import json
import os
from typing import Any

import boto3
from bedrock_agentcore.services.identity import IdentityClient, UserTokenIdentifier

# AWS clients
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("OAUTH_SESSION_TABLE_NAME", "line-agent-oauth-sessions")
session_table = dynamodb.Table(table_name)

# AgentCore Identity client (AWS_REGION is automatically set by Lambda runtime)
region = os.environ.get("AWS_REGION", "ap-northeast-1")
identity_client = IdentityClient(region=region)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    OAuth2 Callback Handler

    Google OAuth 認証後のリダイレクトを受け取り、OAuth フローを完了する

    Args:
        event: API Gateway event (queryStringParameters に session_id を含む)
        context: Lambda context

    Returns:
        HTML レスポンス（認証完了メッセージ）
    """
    print(f"[DEBUG] Received event: {json.dumps(event)}")

    # session_id を取得
    query_params = event.get("queryStringParameters") or {}
    session_id = query_params.get("session_id")

    if not session_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": """
                <html>
                    <head><title>エラー</title></head>
                    <body>
                        <h1>❌ エラー</h1>
                        <p>session_id パラメータが見つかりません。</p>
                    </body>
                </html>
            """,
        }

    try:
        # DynamoDB から LINE user_id と Cognito token を取得
        response = session_table.get_item(Key={"session_id": session_id})

        if "Item" not in response:
            print(f"[ERROR] Session not found: {session_id}")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "text/html; charset=utf-8"},
                "body": """
                    <html>
                        <head><title>エラー</title></head>
                        <body>
                            <h1>❌ セッションが見つかりません</h1>
                            <p>セッションが期限切れか、無効です。</p>
                            <p>LINEに戻って再度お試しください。</p>
                        </body>
                    </html>
                """,
            }

        item = response["Item"]
        line_user_id = item["line_user_id"]
        cognito_token = item["cognito_token"]

        print(f"[INFO] Session found: line_user_id={line_user_id}")

        # OAuth フローを完了（AgentCore Identity に通知）
        user_identifier = UserTokenIdentifier(user_token=cognito_token)
        identity_client.complete_resource_token_auth(
            session_uri=session_id, user_identifier=user_identifier
        )

        print(f"[SUCCESS] OAuth flow completed for line_user_id={line_user_id}")

        # DynamoDB からセッションを削除（クリーンアップ）
        session_table.delete_item(Key={"session_id": session_id})
        print(f"[INFO] Session deleted: {session_id}")

        # 成功レスポンス
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": """
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>認証完了</title>
                    <style>
                        body {
                            margin: 0;
                            padding: 0;
                            height: 100vh;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }
                        .container {
                            text-align: center;
                            padding: 3rem;
                            background-color: white;
                            border-radius: 20px;
                            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                            max-width: 500px;
                        }
                        h1 {
                            color: #28a745;
                            margin: 0 0 1rem 0;
                            font-size: 2.5rem;
                        }
                        p {
                            color: #555;
                            font-size: 1.2rem;
                            line-height: 1.6;
                            margin: 1rem 0;
                        }
                        .icon {
                            font-size: 5rem;
                            margin-bottom: 1rem;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="icon">✅</div>
                        <h1>認証完了！</h1>
                        <p>Google Calendar との連携が完了しました。</p>
                        <p>LINEに戻って、再度カレンダー操作をお試しください。</p>
                    </div>
                </body>
                </html>
            """,
        }

    except Exception as e:
        print(f"[ERROR] Failed to complete OAuth flow: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": f"""
                <html>
                    <head><title>エラー</title></head>
                    <body>
                        <h1>❌ エラーが発生しました</h1>
                        <p>{str(e)}</p>
                        <p>LINEに戻って再度お試しください。</p>
                    </body>
                </html>
            """,
        }
