# デプロイ手順

このドキュメントは、ツール統合を実装した後のデプロイ手順を説明します。

## 実装内容

### 追加された機能

1. **Claudeツール統合**: agent/server.pyにカレンダー操作ツールを統合
2. **ツール実行ループ**: Claudeからのtool_use呼び出しに対応
3. **Lambda関数呼び出し**: boto3でカレンダーLambda関数を直接呼び出し
4. **IAM権限追加**: AgentCore RuntimeロールにLambda呼び出し権限を追加

## デプロイ手順

### 1. CDKスタックをデプロイ

```bash
cd infra

# すべてのスタックをデプロイ（既にデプロイ済みの場合は更新）
cdk deploy --all

# 出力からCalendarFunctionArnをメモ
# 例: arn:aws:lambda:ap-northeast-1:123456789012:function:LineAgentLambdaStack-CalendarOperationsFunction-xxx
```

### 2. Dockerイメージをビルド・プッシュ

GitHub Actionsで自動的にビルド・プッシュされます（masterブランチへのpush時）。

手動でビルドする場合：

```bash
cd agent

# ARM64アーキテクチャでビルド
docker buildx build --platform linux/arm64 -t line-agent-secretary .

# ECRにログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com

# ECRにプッシュ
docker tag line-agent-secretary:latest <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/line-agent-secretary:latest
docker push <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/line-agent-secretary:latest
```

### 3. AgentCore Runtimeの環境変数を更新

**重要**: AgentCore Runtimeに`CALENDAR_LAMBDA_ARN`環境変数を設定する必要があります。

#### AWS CLIでRuntime環境変数を更新

```bash
# Runtime IDを確認（infra/app.pyにハードコードされている）
RUNTIME_ID="line_agent_secretary-Z8wcZvH0aN"

# CDK出力からLambda ARNを取得
CALENDAR_LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name LineAgentLambdaStack \
  --query 'Stacks[0].Outputs[?OutputKey==`CalendarFunctionArn`].OutputValue' \
  --output text \
  --region ap-northeast-1)

echo "Calendar Lambda ARN: $CALENDAR_LAMBDA_ARN"

# AgentCore Runtimeの環境変数を更新
# 注意: 既存の環境変数（LINE_CHANNEL_SECRET等）も含めて指定する必要があります
aws bedrock-agentcore update-agent-runtime \
  --region ap-northeast-1 \
  --runtime-identifier $RUNTIME_ID \
  --environment-variables \
    LINE_CHANNEL_SECRET="${LINE_CHANNEL_SECRET}" \
    LINE_CHANNEL_ACCESS_TOKEN="${LINE_CHANNEL_ACCESS_TOKEN}" \
    CALENDAR_LAMBDA_ARN="${CALENDAR_LAMBDA_ARN}" \
    AWS_REGION="ap-northeast-1"
```

**注意**: `update-agent-runtime`コマンドが利用できない場合は、AgentCore RuntimeをWebコンソールから再作成し、環境変数を設定してください。

#### Webコンソールで設定する場合

1. [Amazon Bedrock AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/)にアクセス
2. Runtimesタブから該当Runtimeを選択
3. Editボタンをクリック
4. Environment variablesセクションに以下を追加：
   - `CALENDAR_LAMBDA_ARN`: CDK出力の`CalendarFunctionArn`の値
   - `LINE_CHANNEL_SECRET`: LINE channel secret
   - `LINE_CHANNEL_ACCESS_TOKEN`: LINE channel access token
   - `AWS_REGION`: `ap-northeast-1`
5. Save changes

### 4. AgentCore RuntimeのIAMロールを確認

AgentCore RuntimeのIAMロールに以下の権限が含まれていることを確認：

```json
{
  "Effect": "Allow",
  "Action": [
    "lambda:InvokeFunction"
  ],
  "Resource": "<CalendarFunctionArn>"
}
```

CDKでデプロイした場合は自動的に設定されています（infra/stacks/agentcore_stack.py:114-121）。

### 5. Google OAuth2認証の設定

まだ設定していない場合は、以下を実行：

#### Google Cloud Consoleでの設定

1. [Google Developer Console](https://console.developers.google.com/)にアクセス
2. Google Calendar APIを有効化
3. OAuth同意画面を作成
4. OAuth 2.0 認証情報を作成
5. リダイレクトURIを追加:
   ```
   https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback
   ```

#### AgentCore Identity Credential Providerの作成

```bash
aws bedrock-agentcore-control create-oauth2-credential-provider \
  --region ap-northeast-1 \
  --name "google-calendar-provider" \
  --credential-provider-vendor "GoogleOauth2" \
  --oauth2-provider-config-input '{
      "googleOauth2ProviderConfig": {
        "clientId": "<YOUR_GOOGLE_CLIENT_ID>",
        "clientSecret": "<YOUR_GOOGLE_CLIENT_SECRET>"
      }
    }'
```

#### ユーザー認証フローの実行

Lambda関数が初めて呼ばれたときに、ユーザーがGoogle認証を行う必要があります。

**TODO**: ユーザー認証フローの詳細な手順を追加

## テスト

### 1. LINEで動作確認

LINEアプリから以下のメッセージを送信してテスト：

```
今週の予定を教えて
```

期待される動作：
1. Claudeが`list_calendar_events`ツールを呼び出す
2. カレンダーLambda関数が実行される
3. Googleカレンダーから予定を取得
4. Claudeが予定を日本語で要約して返す

### 2. ログの確認

```bash
# AgentCore RuntimeのCloudWatch Logsを確認
aws logs tail /aws/bedrock-agentcore/runtime/line_agent_secretary-Z8wcZvH0aN --follow

# Lambda関数のログを確認
aws logs tail /aws/lambda/LineAgentLambdaStack-CalendarOperationsFunction-xxx --follow
```

### 3. トラブルシューティング

#### "Calendar Lambda ARN not configured"エラー

- AgentCore Runtimeの環境変数`CALENDAR_LAMBDA_ARN`が設定されていません
- 手順3を実行してください

#### "AccessDeniedException"エラー

- AgentCore RuntimeのIAMロールにLambda呼び出し権限がありません
- CDKを再デプロイするか、手動でIAMポリシーを追加してください

#### "ValidationException: You must register and use at least one ResourceOauth2ReturnUrl"

- AgentCore Identity Workload Identityが正しく設定されていません
- ユーザー認証フローを実行する必要があります（手順5参照）

#### Claudeが「予定情報にアクセスできません」と返す

- ツール統合が正しく動作していない可能性があります
- CloudWatch Logsで以下を確認：
  - `Iteration X: Invoking Bedrock`: Claudeが呼ばれている
  - `Stop reason: tool_use`: Claudeがツールを使おうとしている
  - `Executing tool: list_calendar_events`: ツールが実行されている
  - `Invoking Lambda: arn:aws:lambda:...`: Lambda関数が呼ばれている

## 次のステップ

### MCP統合への移行（オプション）

現在の実装ではLambda関数を直接呼び出していますが、AgentCore Gatewayを経由したMCP統合に移行することも可能です：

1. AgentCore GatewayのURLを取得
2. MCPクライアントを実装（mcp Python SDK使用）
3. Gatewayを通じてツールを呼び出す

詳細はAWS AgentCore Gatewayのドキュメントを参照してください。

### Strands Agentsへの移行（オプション）

より高度なエージェント機能が必要な場合、Strands Agentsフレームワークへの移行を検討してください：

1. `bedrock-agentcore` SDKの`BedrockAgentCoreApp`ラッパーを使用
2. Strands AgentsでエージェントロジックをAPIとして定義
3. AgentCore Runtimeにデプロイ

詳細は[Strands Agentsドキュメント](https://strandsagents.com/)を参照してください。
