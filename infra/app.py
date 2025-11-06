#!/usr/bin/env python3
"""
LINE Agent Secretary CDK Application

AWS CDKを使ってインフラストラクチャをデプロイする
"""

import aws_cdk as cdk

from stacks.agentcore_stack import AgentCoreStack
from stacks.cognito_stack import CognitoStack
from stacks.github_oidc_stack import GitHubOIDCStack
from stacks.lambda_stack import LambdaStack
from stacks.line_webhook_stack import LineWebhookStack
from stacks.secrets_stack import SecretsStack

app = cdk.App()

# 環境設定
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "ap-northeast-1",
)

# Secrets Managerスタック（LINE認証情報）
secrets_stack = SecretsStack(
    app,
    "LineAgentSecretsStack",
    env=env,
    description="Secrets Manager for LINE authentication credentials",
)

# Cognito User Poolスタック（JWT認証用）
cognito_stack = CognitoStack(
    app,
    "LineAgentCognitoStack",
    env=env,
    description="Cognito User Pool for JWT authentication",
)

# GitHub OIDCスタック（GitHub ActionsからECRへのデプロイ）
github_oidc_stack = GitHubOIDCStack(
    app,
    "LineAgentGitHubOIDCStack",
    github_owner="foie0222",
    github_repo="my-secretary",
    ecr_repository_name="line-agent-secretary",
    env=env,
    description="GitHub OIDC provider and IAM role for GitHub Actions",
)

# Lambda関数スタック（Google Calendar操作）
lambda_stack = LambdaStack(
    app,
    "LineAgentLambdaStack",
    env=env,
    description="Lambda functions for Google Calendar operations",
)

# AgentCoreスタック（Runtime & Gateway）
agentcore_stack = AgentCoreStack(
    app,
    "LineAgentAgentCoreStack",
    lambda_function_arn=lambda_stack.calendar_function.function_arn,
    line_secret=secrets_stack.line_secret,
    env=env,
    description="AgentCore Runtime and Gateway configuration",
)

# LINE WebhookスタックLambda + API Gateway）
# Runtime IDは既に作成済みのもの: line_agent_secretary-Z8wcZvH0aN
line_webhook_stack = LineWebhookStack(
    app,
    "LineAgentWebhookStack",
    agent_runtime_id="line_agent_secretary-Z8wcZvH0aN",
    line_secret=secrets_stack.line_secret,
    cognito_user_pool_id=cognito_stack.user_pool.user_pool_id,
    cognito_app_client_id=cognito_stack.app_client.user_pool_client_id,
    env=env,
    description="LINE Webhook handler with API Gateway",
)

# スタック間の依存関係を設定
agentcore_stack.add_dependency(lambda_stack)
agentcore_stack.add_dependency(secrets_stack)
line_webhook_stack.add_dependency(agentcore_stack)
line_webhook_stack.add_dependency(cognito_stack)

# タグを追加（コスト管理用）
cdk.Tags.of(app).add("Project", "LineAgentSecretary")
cdk.Tags.of(app).add("Environment", "Development")

app.synth()
