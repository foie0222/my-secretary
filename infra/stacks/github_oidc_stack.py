"""
GitHub OIDC Stack

GitHub ActionsからAWSリソースへのアクセスを可能にするOIDCプロバイダーとIAMロールを作成
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from constructs import Construct


class GitHubOIDCStack(Stack):
    """GitHub Actions用のOIDCプロバイダーとIAMロールを管理するスタック"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        github_owner: str,
        github_repo: str,
        ecr_repository_name: str,
        **kwargs,
    ) -> None:
        """
        Args:
            scope: CDKスコープ
            construct_id: コンストラクトID
            github_owner: GitHubリポジトリのオーナー名
            github_repo: GitHubリポジトリ名
            ecr_repository_name: ECRリポジトリ名
            **kwargs: その他のスタックパラメータ
        """
        super().__init__(scope, construct_id, **kwargs)

        # GitHub OIDC プロバイダー
        # NOTE: GitHub OIDCプロバイダーは1つのAWSアカウントに1つだけ作成する必要がある
        # すでに存在する場合は、このリソースをコメントアウトしてください
        github_provider = iam.OpenIdConnectProvider(
            self,
            "GitHubOIDCProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
            thumbprints=[
                # GitHub Actions OIDC thumbprint
                # 参考: https://github.blog/changelog/2023-06-27-github-actions-update-on-oidc-integration-with-aws/
                "6938fd4d98bab03faadb97b34396831e3780aea1",
                "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
            ],
        )

        # GitHub Actions用のIAMロール
        github_role = iam.Role(
            self,
            "GitHubActionsRole",
            role_name="github-actions-ecr-deploy",
            assumed_by=iam.FederatedPrincipal(
                github_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        # 特定のリポジトリのみアクセス許可
                        "token.actions.githubusercontent.com:sub": f"repo:{github_owner}/{github_repo}:*",
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            description=f"Role for GitHub Actions to deploy to ECR from {github_owner}/{github_repo}",
        )

        # ECRへのアクセス権限
        github_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                ],
                resources=["*"],
            )
        )

        github_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                ],
                resources=[
                    f"arn:aws:ecr:{self.region}:{self.account}:repository/{ecr_repository_name}"
                ],
            )
        )

        # 出力
        CfnOutput(
            self,
            "GitHubActionsRoleArn",
            value=github_role.role_arn,
            description="GitHub Actions用のIAMロールARN（GitHub Secretsに設定してください）",
            export_name=f"{self.stack_name}-GitHubActionsRoleArn",
        )

        CfnOutput(
            self,
            "GitHubOIDCProviderArn",
            value=github_provider.open_id_connect_provider_arn,
            description="GitHub OIDC プロバイダーARN",
            export_name=f"{self.stack_name}-GitHubOIDCProviderArn",
        )

        CfnOutput(
            self,
            "GitHubSecretsInstructions",
            value=(
                "GitHub Secretsに以下を設定してください:\n"
                f"Name: AWS_ROLE_ARN\n"
                f"Value: {github_role.role_arn}"
            ),
            description="GitHub Secretsの設定手順",
        )

        # 既存のECRリポジトリを参照
        self.ecr_repository = ecr.Repository.from_repository_name(
            self,
            "ECRRepository",
            repository_name=ecr_repository_name,
        )

        # ロールを他のスタックから参照できるようにする
        self.github_role = github_role
        self.github_provider = github_provider
