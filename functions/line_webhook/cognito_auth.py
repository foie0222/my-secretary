"""
Cognito Authentication Helper

LINE User IDをCognito User IDにマッピングし、JWT認証を実行
"""

import hashlib
import hmac
import logging
import os
from typing import Optional

import boto3

logger = logging.getLogger()

# Cognito Client
cognito_client = boto3.client("cognito-idp")

# 環境変数
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
APP_CLIENT_SECRET = os.environ.get("COGNITO_APP_CLIENT_SECRET", "")  # オプション


def _calculate_secret_hash(username: str) -> str:
    """
    Calculate SECRET_HASH for Cognito authentication

    Args:
        username: Cognito username

    Returns:
        Calculated SECRET_HASH
    """
    if not APP_CLIENT_SECRET:
        return ""

    message = username + APP_CLIENT_ID
    secret_hash = hmac.new(
        APP_CLIENT_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return hashlib.b64encode(secret_hash).decode()


def get_or_create_cognito_user(line_user_id: str) -> str:
    """
    LINE User IDに対応するCognito Userを取得または作成

    Args:
        line_user_id: LINE User ID

    Returns:
        Cognito username
    """
    # Cognito usernameはLINE User IDをそのまま使用
    # （もしくは、ハッシュ化やプレフィックス追加も可能）
    cognito_username = f"line_{line_user_id}"

    try:
        # ユーザーが既に存在するか確認
        cognito_client.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=cognito_username
        )
        logger.info(f"Cognito user already exists: {cognito_username}")
        return cognito_username

    except cognito_client.exceptions.UserNotFoundException:
        # ユーザーが存在しない場合、新規作成
        logger.info(f"Creating new Cognito user: {cognito_username}")

        # ランダムなパスワードを生成（ユーザーはパスワードを使わない）
        import secrets
        import string
        password = ''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(32))

        try:
            # Cognito Userを作成
            cognito_client.admin_create_user(
                UserPoolId=USER_POOL_ID,
                Username=cognito_username,
                TemporaryPassword=password,
                UserAttributes=[
                    {"Name": "custom:line_user_id", "Value": line_user_id},
                ],
                MessageAction="SUPPRESS",  # ウェルカムメールを送信しない
            )

            # パスワードを永続化（FORCE_CHANGE_PASSWORDを解除）
            cognito_client.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=cognito_username,
                Password=password,
                Permanent=True
            )

            logger.info(f"Successfully created Cognito user: {cognito_username}")
            return cognito_username

        except Exception as e:
            logger.error(f"Failed to create Cognito user: {e}")
            raise


def get_jwt_token(line_user_id: str) -> str:
    """
    LINE User IDに対応するJWTトークンを取得

    Args:
        line_user_id: LINE User ID

    Returns:
        JWT access token
    """
    # Cognito Userを取得または作成
    cognito_username = get_or_create_cognito_user(line_user_id)

    # Cognito User情報を取得してパスワードを復元
    # 注: 実運用では、パスワードをSecrets Managerに保存する等の対策が必要
    # 今回は簡易実装として、ユーザー作成時のパスワードを再利用

    # ADMIN_NO_SRP_AUTH flowを使用してJWTトークンを取得
    try:
        # パスワード認証は使用せず、Admin APIでトークンを発行
        response = cognito_client.admin_initiate_auth(
            UserPoolId=USER_POOL_ID,
            ClientId=APP_CLIENT_ID,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={
                "USERNAME": cognito_username,
                # パスワード認証を使用しない場合、Cognitoの設定でカスタムAuthフローを使う必要がある
                # 簡易実装として、一時的なトークン発行を使用
            }
        )

        # Access Tokenを取得
        access_token = response["AuthenticationResult"]["AccessToken"]
        logger.info(f"Successfully retrieved JWT token for user: {cognito_username}")

        return access_token

    except Exception as e:
        logger.error(f"Failed to get JWT token: {e}")
        # フォールバック: AdminGetUserでユーザー存在を確認し、カスタムトークンを発行
        # （本番環境では適切な認証フローを実装）
        raise


def get_jwt_token_simple(line_user_id: str) -> str:
    """
    LINE User IDに対応するJWTトークンを簡易的に取得

    パスワード管理を簡略化するため、ユーザーごとにパスワードを保存せず、
    毎回新しいパスワードでトークンを発行する方式

    Args:
        line_user_id: LINE User ID

    Returns:
        JWT access token
    """
    import secrets
    import string

    cognito_username = get_or_create_cognito_user(line_user_id)

    # 新しいパスワードを生成
    password = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(32))

    # パスワードをリセット
    cognito_client.admin_set_user_password(
        UserPoolId=USER_POOL_ID,
        Username=cognito_username,
        Password=password,
        Permanent=True
    )

    # ADMIN_NO_SRP_AUTHでトークンを取得
    secret_hash_params = {}
    if APP_CLIENT_SECRET:
        secret_hash_params["SECRET_HASH"] = _calculate_secret_hash(cognito_username)

    response = cognito_client.admin_initiate_auth(
        UserPoolId=USER_POOL_ID,
        ClientId=APP_CLIENT_ID,
        AuthFlow="ADMIN_NO_SRP_AUTH",
        AuthParameters={
            "USERNAME": cognito_username,
            "PASSWORD": password,
            **secret_hash_params,
        }
    )

    access_token = response["AuthenticationResult"]["AccessToken"]
    logger.info(f"Successfully retrieved JWT token for user: {cognito_username}")

    return access_token
