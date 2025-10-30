"""
Secrets Manager Stack

LINE認証情報を安全に保存するためのスタック
"""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class SecretsStack(Stack):
    """Secrets Managerリソースを管理するスタック"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # LINE認証情報用のSecret
        self.line_secret = secretsmanager.Secret(
            self,
            "LineCredentials",
            secret_name="line-agent-secretary/line-credentials",
            description="LINE Messaging API credentials (Channel Secret and Access Token)",
            # 本番環境では削除保護を有効にすること
            removal_policy=RemovalPolicy.DESTROY,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"channel_secret":"REPLACE_ME"}',
                generate_string_key="channel_access_token",
                exclude_punctuation=True,
            ),
        )

        # Secretの値は手動で設定する必要があることを示すメッセージ
        # CFn Outputで表示
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "LineSecretArn",
            value=self.line_secret.secret_arn,
            description="LINE credentials secret ARN - Update this secret with your LINE channel credentials",
        )

        CfnOutput(
            self,
            "LineSecretSetupInstructions",
            value=(
                "Update the LINE secret with: "
                'aws secretsmanager update-secret --secret-id '
                f"{self.line_secret.secret_name} "
                '--secret-string \'{"channel_secret":"YOUR_CHANNEL_SECRET",'
                '"channel_access_token":"YOUR_CHANNEL_ACCESS_TOKEN"}\''
            ),
            description="Command to update LINE credentials",
        )
