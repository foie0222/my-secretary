"""
OAuth Session Table Stack

OAuth 3-legged フローで session_id と LINE user_id を一時的に保存するテーブル
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_dynamodb as dynamodb,
    CfnOutput,
)
from constructs import Construct


class OAuthSessionStack(Stack):
    """OAuth Session DynamoDB Table for 3-legged OAuth flow"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # OAuth Session テーブル
        self.session_table = dynamodb.Table(
            self,
            "OAuthSessionTable",
            table_name="line-agent-oauth-sessions",
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING,
            ),
            # Time-to-Live (10分で自動削除)
            time_to_live_attribute="ttl",
            # オンデマンド課金（使用量が少ない想定）
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # 開発用：削除時にテーブルも削除
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Outputs
        CfnOutput(
            self,
            "OAuthSessionTableName",
            value=self.session_table.table_name,
            description="OAuth Session DynamoDB Table Name",
            export_name="LineAgentOAuthSessionTableName",
        )

        CfnOutput(
            self,
            "OAuthSessionTableArn",
            value=self.session_table.table_arn,
            description="OAuth Session DynamoDB Table ARN",
            export_name="LineAgentOAuthSessionTableArn",
        )
