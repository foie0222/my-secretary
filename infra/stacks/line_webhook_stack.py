"""
LINE Webhook Stack

LINE WebhookとAPI Gatewayを管理するスタック
"""

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct


class LineWebhookStack(Stack):
    """LINE WebhookとAPI Gatewayを管理するスタック"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_runtime_id: str,
        line_secret: secretsmanager.ISecret,
        cognito_user_pool_id: str,
        cognito_app_client_id: str,
        oauth_session_table: dynamodb.ITable,
        **kwargs,
    ) -> None:
        """
        Args:
            scope: CDKスコープ
            construct_id: コンストラクトID
            agent_runtime_id: AgentCore RuntimeのID
            line_secret: LINE認証情報のSecret
            cognito_user_pool_id: Cognito User Pool ID
            cognito_app_client_id: Cognito App Client ID
            oauth_session_table: OAuth Session DynamoDB Table
            **kwargs: その他のスタックパラメータ
        """
        super().__init__(scope, construct_id, **kwargs)

        # LINE Webhook Lambda関数
        webhook_function = PythonFunction(
            self,
            "LineWebhookFunction",
            entry="../functions/line_webhook",
            runtime=lambda_.Runtime.PYTHON_3_12,
            index="handler.py",
            handler="lambda_handler",
            timeout=Duration.seconds(120),  # Increased to 120 seconds
            memory_size=256,
            environment={
                "LINE_CHANNEL_ACCESS_TOKEN": line_secret.secret_value_from_json("channel_access_token").unsafe_unwrap(),
                "LINE_CHANNEL_SECRET": line_secret.secret_value_from_json("channel_secret").unsafe_unwrap(),
                "AGENT_RUNTIME_ARN": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/{agent_runtime_id}",
                "COGNITO_USER_POOL_ID": cognito_user_pool_id,
                "COGNITO_APP_CLIENT_ID": cognito_app_client_id,
                "OAUTH_SESSION_TABLE_NAME": oauth_session_table.table_name,
            },
            description="LINE Webhook handler for LINE Agent Secretary",
        )

        # OAuth Callback Lambda関数
        oauth_callback_function = PythonFunction(
            self,
            "OAuthCallbackFunction",
            entry="../functions/oauth_callback",
            runtime=lambda_.Runtime.PYTHON_3_12,
            index="handler.py",
            handler="lambda_handler",
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "OAUTH_SESSION_TABLE_NAME": oauth_session_table.table_name,
            },
            description="OAuth2 callback handler for Google Calendar authentication",
        )

        # Secrets Managerへの読み取り権限を付与
        line_secret.grant_read(webhook_function)

        # DynamoDB への読み書き権限を付与
        oauth_session_table.grant_read_write_data(webhook_function)
        oauth_session_table.grant_read_write_data(oauth_callback_function)

        # AgentCore Runtimeを呼び出す権限
        webhook_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/{agent_runtime_id}",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/{agent_runtime_id}/*",
                ],
            )
        )

        # Cognito User Pool操作権限
        webhook_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminInitiateAuth",
                ],
                resources=[
                    f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/{cognito_user_pool_id}",
                ],
            )
        )

        # API Gateway (REST API)
        api = apigw.RestApi(
            self,
            "LineWebhookApi",
            rest_api_name="LINE Agent Secretary Webhook API",
            description="API for LINE Agent Secretary webhook",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=10,
                throttling_burst_limit=20,
            ),
        )

        # Lambda統合（プロキシ統合を使用）
        webhook_integration = apigw.LambdaIntegration(webhook_function)
        oauth_callback_integration = apigw.LambdaIntegration(oauth_callback_function)

        # /webhook エンドポイント
        webhook_resource = api.root.add_resource("webhook")
        webhook_resource.add_method("POST", webhook_integration)

        # /oauth2/callback エンドポイント
        oauth2_resource = api.root.add_resource("oauth2")
        callback_resource = oauth2_resource.add_resource("callback")
        callback_resource.add_method("GET", oauth_callback_integration)

        # Lambda権限（API Gatewayからの呼び出しを許可）
        webhook_function.add_permission(
            "ApiGatewayInvoke",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=api.arn_for_execute_api(),
        )

        oauth_callback_function.add_permission(
            "ApiGatewayInvoke",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=api.arn_for_execute_api(),
        )

        # OAuth Callback Lambda に AgentCore Identity の権限を付与
        oauth_callback_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore-identity:CompleteResourceTokenAuth",
                ],
                resources=["*"],
            )
        )

        # 出力
        CfnOutput(
            self,
            "WebhookUrl",
            value=f"{api.url}webhook",
            description="LINE Webhook URL (set this in LINE Developers Console)",
            export_name=f"{self.stack_name}-WebhookUrl",
        )

        CfnOutput(
            self,
            "OAuthCallbackUrl",
            value=f"{api.url}oauth2/callback",
            description="OAuth2 Callback URL (register this with AgentCore Workload Identity)",
            export_name=f"{self.stack_name}-OAuthCallbackUrl",
        )

        CfnOutput(
            self,
            "WebhookFunctionName",
            value=webhook_function.function_name,
            description="LINE Webhook Lambda function name",
            export_name=f"{self.stack_name}-WebhookFunctionName",
        )

        CfnOutput(
            self,
            "SetupInstructions",
            value=(
                "1. Update Lambda environment variables with your LINE credentials\n"
                "2. Set the Webhook URL in LINE Developers Console\n"
                "3. Enable webhook in LINE Developers Console"
            ),
            description="Setup instructions",
        )
