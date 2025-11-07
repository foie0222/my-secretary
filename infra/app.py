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
from stacks.oauth_session_stack import OAuthSessionStack
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

# OAuth Session テーブルスタック（3-legged OAuth用）
oauth_session_stack = OAuthSessionStack(
    app,
    "LineAgentOAuthSessionStack",
    env=env,
    description="DynamoDB table for OAuth session management",
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
    cognito_user_pool_id=cognito_stack.user_pool.user_pool_id,
    cognito_app_client_id=cognito_stack.app_client.user_pool_client_id,
    cognito_discovery_url=cognito_stack.user_pool.user_pool_provider_url,
    env=env,
    description="AgentCore Runtime and Gateway configuration with JWT authentication",
)

# LINE Webhookスタック（Lambda + API Gateway）
# Runtime IDは AgentCore スタックから動的に取得
line_webhook_stack = LineWebhookStack(
    app,
    "LineAgentWebhookStack",
    agent_runtime_id=agentcore_stack.runtime.attr_agent_runtime_id,
    line_secret=secrets_stack.line_secret,
    cognito_user_pool_id=cognito_stack.user_pool.user_pool_id,
    cognito_app_client_id=cognito_stack.app_client.user_pool_client_id,
    oauth_session_table=oauth_session_stack.session_table,
    env=env,
    description="LINE Webhook handler with API Gateway and JWT authentication",
)

# スタック間の依存関係を設定
agentcore_stack.add_dependency(lambda_stack)
agentcore_stack.add_dependency(secrets_stack)
agentcore_stack.add_dependency(cognito_stack)
line_webhook_stack.add_dependency(agentcore_stack)
line_webhook_stack.add_dependency(oauth_session_stack)

# タグを追加（コスト管理用）
cdk.Tags.of(app).add("Project", "LineAgentSecretary")
cdk.Tags.of(app).add("Environment", "Development")

app.synth()
