"""
Lambda Functions Stack

Google Calendar操作用のLambda関数を定義するスタック
"""

from aws_cdk import (
    BundlingOptions,
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from constructs import Construct


class LambdaStack(Stack):
    """Lambda関数を管理するスタック"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Lambda実行ロールを作成
        lambda_role = iam.Role(
            self,
            "CalendarLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
            description="Execution role for Google Calendar operations Lambda",
        )

        # AgentCore Identityへのアクセス権限を追加
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:*",
                    "bedrock-agentcore-control:*",
                ],
                resources=["*"],  # 本番環境では適切なARNに制限すること
            )
        )

        # Secrets Managerへのアクセス権限を追加（OAuth tokenの取得用）
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=["*"],  # 本番環境では適切なARNに制限すること
            )
        )

        # Google Calendar操作Lambda関数
        # PythonFunctionを使用して依存関係を自動的にバンドル
        self.calendar_function = lambda_.Function(
            self,
            "CalendarOperationsFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="operations.lambda_handler",
            code=lambda_.Code.from_asset(
                "../functions/calendar",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                ),
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "CREDENTIAL_PROVIDER_NAME": "google-calendar-provider",
            },
            description="Google Calendar operations function using AgentCore Identity",
        )

        # AgentCore Gatewayからの呼び出しを許可
        self.calendar_function.grant_invoke(
            iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")
        )
