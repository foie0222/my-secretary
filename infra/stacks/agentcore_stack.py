"""
AgentCore Stack

AgentCore RuntimeとGatewayの設定を行うスタック
GatewayとLambda TargetをCDKで完全に定義します。
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class AgentCoreStack(Stack):
    """AgentCore RuntimeとGatewayを管理するスタック"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_function_arn: str,
        line_secret: secretsmanager.ISecret,
        cognito_user_pool_id: str,
        cognito_app_client_id: str,
        cognito_discovery_url: str,
        oauth_callback_url: str | None = None,
        **kwargs,
    ) -> None:
        """
        Args:
            scope: CDKスコープ
            construct_id: コンストラクトID
            lambda_function_arn: Calendar操作Lambda関数のARN
            line_secret: LINE認証情報のSecret
            cognito_user_pool_id: Cognito User Pool ID
            cognito_app_client_id: Cognito App Client ID
            cognito_discovery_url: Cognito OIDC Discovery URL
            oauth_callback_url: OAuth2 Callback URL (optional, defaults to placeholder)
            **kwargs: その他のスタックパラメータ
        """
        super().__init__(scope, construct_id, **kwargs)

        # AgentCore Gateway用のサービスロール
        gateway_role = iam.Role(
            self,
            "GatewayServiceRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Service role for AgentCore Gateway",
        )

        # Lambda関数を呼び出す権限を追加
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[lambda_function_arn],
            )
        )

        # AgentCore Identity OAuth2 Credential Providerへのアクセス権限
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore-control:GetOauth2CredentialProvider",
                    "bedrock-agentcore-control:GetResourceOauth2Token",
                ],
                resources=["*"],  # 本番環境では適切なARNに制限すること
            )
        )

        # AgentCore Runtime用のIAMロール
        runtime_role = iam.Role(
            self,
            "RuntimeExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execution role for AgentCore Runtime",
        )

        # AgentCore Gatewayへのアクセス権限
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeGateway",
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:ListGateways",
                    "bedrock-agentcore:ListGatewayTargets",
                    "bedrock-agentcore-control:ListGateways",
                    "bedrock-agentcore-control:ListGatewayTargets",
                    "bedrock-agentcore-control:GetGateway",
                ],
                resources=["*"],  # 本番環境では適切なARNに制限すること
            )
        )

        # AgentCore Identity - Workload Identity管理とOAuth2 Token取得権限
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:CreateWorkloadIdentity",
                    "bedrock-agentcore:GetWorkloadIdentity",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    "bedrock-agentcore:GetResourceOauth2Token",
                ],
                resources=["*"],  # 本番環境では適切なARNに制限すること
            )
        )

        # ECRからDockerイメージを取得する権限
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                resources=["*"],
            )
        )

        # CloudWatch Logsへの書き込み権限
        runtime_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "CloudWatchLogsFullAccess"
            )
        )

        # Bedrock Runtimeへのアクセス権限（Claude 3.5 Sonnetなどのモデルを呼び出すため）
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],  # 本番環境では特定のモデルARNに制限することを推奨
            )
        )

        # Lambda関数を呼び出す権限（カレンダー操作）
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[lambda_function_arn],
            )
        )

        # Secrets Managerから認証情報を読み取る権限
        line_secret.grant_read(runtime_role)

        # OAuth2 Credential Providerが使用するSecrets Managerへのアクセス権限
        # AgentCore Identityが管理するOAuth2 credentialsにアクセス可能にする
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],  # 本番環境ではAgentCore Identity管理のSecretのARNに制限すること
            )
        )

        # AgentCore Gateway作成
        gateway = bedrockagentcore.CfnGateway(
            self,
            "CalendarGateway",
            name="line-agent-calendar-gateway",
            description="Gateway for LINE Agent Secretary calendar operations",
            authorizer_type="AWS_IAM",  # IAM認証を使用
            protocol_type="MCP",
            role_arn=gateway_role.role_arn,
            protocol_configuration=bedrockagentcore.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=bedrockagentcore.CfnGateway.MCPGatewayConfigurationProperty(
                    supported_versions=["2025-03-26"],
                    instructions="Google Calendar operations for LINE Agent Secretary",
                    # search_typeはoptionalなので省略
                )
            ),
        )

        # Gateway Target（Calendar Operations Lambda）
        # Lambda targetの場合、credential providerはGATEWAY_IAM_ROLEを使用
        # OAuth認証はLambda関数内でAgentCore Identityを使って処理
        calendar_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "CalendarTarget",
            name="calendar-operations",
            description="Google Calendar operations target",
            gateway_identifier=gateway.attr_gateway_identifier,
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                )
            ],
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=lambda_function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=self._create_calendar_tool_schemas()
                        ),
                    )
                )
            ),
        )

        # TargetはGatewayに依存
        calendar_target.add_dependency(gateway)

        # AgentCore Runtime作成（JWT認証付き）
        ecr_repository_name = "line-agent-secretary"
        ecr_uri = f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repository_name}:latest"

        runtime = bedrockagentcore.CfnRuntime(
            self,
            "LineAgentRuntime",
            agent_runtime_name="line_agent_secretary_jwt",
            role_arn=runtime_role.role_arn,
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=ecr_uri,
                )
            ),
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC",
            ),
            protocol_configuration="HTTP",
            authorizer_configuration=bedrockagentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bedrockagentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"{cognito_discovery_url}/.well-known/openid-configuration",
                    allowed_clients=[cognito_app_client_id],
                )
            ),
            environment_variables={
                "AWS_REGION": self.region,
                "GATEWAY_ID": gateway.attr_gateway_identifier,
                "GATEWAY_URL": gateway.attr_gateway_url,
                "OAUTH_CALLBACK_URL": oauth_callback_url or "https://placeholder.example.com/oauth2/callback",
            },
        )

        # RuntimeはGatewayに依存
        runtime.add_dependency(gateway)

        # 出力
        CfnOutput(
            self,
            "GatewayRoleArn",
            value=gateway_role.role_arn,
            description="AgentCore Gateway service role ARN",
            export_name=f"{self.stack_name}-GatewayRoleArn",
        )

        CfnOutput(
            self,
            "RuntimeRoleArn",
            value=runtime_role.role_arn,
            description="AgentCore Runtime execution role ARN",
            export_name=f"{self.stack_name}-RuntimeRoleArn",
        )

        CfnOutput(
            self,
            "RuntimeId",
            value=runtime.attr_agent_runtime_id,
            description="AgentCore Runtime ID",
            export_name=f"{self.stack_name}-RuntimeId",
        )

        CfnOutput(
            self,
            "RuntimeArn",
            value=runtime.attr_agent_runtime_arn,
            description="AgentCore Runtime ARN",
            export_name=f"{self.stack_name}-RuntimeArn",
        )

        # Gateway関連の出力
        CfnOutput(
            self,
            "GatewayId",
            value=gateway.attr_gateway_identifier,
            description="AgentCore Gateway ID",
            export_name=f"{self.stack_name}-GatewayId",
        )

        CfnOutput(
            self,
            "GatewayUrl",
            value=gateway.attr_gateway_url,
            description="AgentCore Gateway MCP URL",
            export_name=f"{self.stack_name}-GatewayUrl",
        )

        CfnOutput(
            self,
            "CalendarTargetId",
            value=calendar_target.attr_target_id,
            description="Calendar operations target ID",
            export_name=f"{self.stack_name}-CalendarTargetId",
        )

        # IAMロールとRuntimeを他のスタックから参照できるようにする
        self.gateway_role = gateway_role
        self.runtime_role = runtime_role
        self.gateway = gateway
        self.runtime = runtime

    def _create_calendar_tool_schemas(self) -> list:
        """
        Google Calendar操作のツールスキーマを作成

        Returns:
            ToolDefinitionのリスト
        """
        return [
            # list_calendar_events
            bedrockagentcore.CfnGatewayTarget.ToolDefinitionProperty(
                name="list_calendar_events",
                description="カレンダーの予定を取得する",
                input_schema=bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                    type="object",
                    properties={
                        "time_min": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="取得開始日時（ISO 8601形式）",
                        ),
                        "time_max": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="取得終了日時（ISO 8601形式）",
                        ),
                        "max_results": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="number",
                            description="最大取得件数",
                        ),
                    },
                ),
            ),
            # create_calendar_event
            bedrockagentcore.CfnGatewayTarget.ToolDefinitionProperty(
                name="create_calendar_event",
                description="カレンダーに予定を作成する",
                input_schema=bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                    type="object",
                    properties={
                        "summary": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="予定のタイトル",
                        ),
                        "start_time": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="開始日時（ISO 8601形式）",
                        ),
                        "end_time": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="終了日時（ISO 8601形式）",
                        ),
                        "description": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="予定の説明",
                        ),
                        "location": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="場所",
                        ),
                    },
                    required=["summary", "start_time", "end_time"],
                ),
            ),
            # update_calendar_event
            bedrockagentcore.CfnGatewayTarget.ToolDefinitionProperty(
                name="update_calendar_event",
                description="カレンダーの予定を更新する",
                input_schema=bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                    type="object",
                    properties={
                        "event_id": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="更新する予定のID",
                        ),
                        "summary": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="予定のタイトル",
                        ),
                        "start_time": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="開始日時（ISO 8601形式）",
                        ),
                        "end_time": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="終了日時（ISO 8601形式）",
                        ),
                        "description": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="予定の説明",
                        ),
                        "location": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="場所",
                        ),
                    },
                    required=["event_id"],
                ),
            ),
            # delete_calendar_event
            bedrockagentcore.CfnGatewayTarget.ToolDefinitionProperty(
                name="delete_calendar_event",
                description="カレンダーの予定を削除する",
                input_schema=bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                    type="object",
                    properties={
                        "event_id": bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                            type="string",
                            description="削除する予定のID",
                        ),
                    },
                    required=["event_id"],
                ),
            ),
        ]
