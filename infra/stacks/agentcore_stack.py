"""
AgentCore Stack

AgentCore RuntimeとGatewayの設定を行うスタック
GatewayとLambda TargetをCDKで完全に定義します。
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_iam as iam
from constructs import Construct


class AgentCoreStack(Stack):
    """AgentCore RuntimeとGatewayを管理するスタック"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_function_arn: str,
        **kwargs,
    ) -> None:
        """
        Args:
            scope: CDKスコープ
            construct_id: コンストラクトID
            lambda_function_arn: Calendar操作Lambda関数のARN
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
                    "bedrock-agentcore:ListGatewayTargets",
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
            "SetupInstructions",
            value=(
                "Manual setup required:\n"
                "1. Create OAuth2 Credential Provider for Google Calendar\n"
                "2. Create AgentCore Gateway using the console or AWS CLI\n"
                "3. Add Lambda target to the Gateway\n"
                "4. Create and deploy AgentCore Runtime\n"
                "See requirements.md for detailed instructions"
            ),
            description="Post-deployment setup instructions",
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

        # IAMロールを他のスタックから参照できるようにする
        self.gateway_role = gateway_role
        self.runtime_role = runtime_role
        self.gateway = gateway

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
