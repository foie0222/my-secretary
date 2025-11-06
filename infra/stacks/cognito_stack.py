"""
Cognito User Pool Stack for JWT Authentication

LINE User IDをCognito User IDにマッピングして、JWT認証を実現
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_cognito as cognito,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class CognitoStack(Stack):
    """Cognito User Pool for LINE Agent JWT Authentication"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Cognito User Pool作成
        self.user_pool = cognito.UserPool(
            self,
            "LineAgentUserPool",
            user_pool_name="line-agent-user-pool",
            # パスワードポリシー（ユーザー作成時に使用）
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=False,
                require_uppercase=False,
                require_digits=False,
                require_symbols=False,
            ),
            # サインイン方法
            sign_in_aliases=cognito.SignInAliases(
                username=True,
                email=False,
                phone=False,
            ),
            # 自己サインアップを無効化（Lambda経由でのみユーザー作成）
            self_sign_up_enabled=False,
            # カスタム属性：LINE User IDを保存
            custom_attributes={
                "line_user_id": cognito.StringAttribute(
                    min_len=1,
                    max_len=256,
                    mutable=False,  # 作成後は変更不可
                )
            },
            # 開発用：削除時にUser Poolも削除
            removal_policy=RemovalPolicy.DESTROY,
        )

        # App Client作成（LINE Webhook Lambda用）
        self.app_client = self.user_pool.add_client(
            "LineWebhookAppClient",
            user_pool_client_name="line-webhook-client",
            # OAuth2フロー
            auth_flows=cognito.AuthFlow(
                user_password=True,  # USER_PASSWORD_AUTH有効化
                admin_user_password=True,  # ADMIN_NO_SRP_AUTH有効化
            ),
            # トークン有効期限
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            # OAuthフローは使用しない（Lambdaから直接認証）
            o_auth=None,
        )

        # Outputs
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name="LineAgentUserPoolId",
        )

        CfnOutput(
            self,
            "UserPoolArn",
            value=self.user_pool.user_pool_arn,
            description="Cognito User Pool ARN",
            export_name="LineAgentUserPoolArn",
        )

        CfnOutput(
            self,
            "AppClientId",
            value=self.app_client.user_pool_client_id,
            description="Cognito App Client ID",
            export_name="LineAgentAppClientId",
        )

        CfnOutput(
            self,
            "ProviderUrl",
            value=self.user_pool.user_pool_provider_url,
            description="Cognito OIDC Discovery URL",
            export_name="LineAgentProviderUrl",
        )
