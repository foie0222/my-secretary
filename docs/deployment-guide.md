# デプロイガイド

Google OAuth2設定とAgentCore Identity Credential Providerの作成が完了した後のデプロイ手順

## 前提条件

✅ Google OAuth2設定が完了
✅ AgentCore Identity OAuth2 Credential Providerが作成済み
✅ uv環境のセットアップが完了（`uv sync`実行済み）

---

## Step 1: AWS CDKでインフラをデプロイ

### 1.1 CDK依存関係のインストール

```bash
# プロジェクトルートで実行
uv sync --extra infra
```

### 1.2 AWS認証情報の確認

```bash
# AWS CLIが正しく設定されているか確認
aws sts get-caller-identity

# 出力例：
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

### 1.3 CDK Bootstrap（初回のみ）

```bash
cd infra

# ap-northeast-1リージョンでBootstrap
cdk bootstrap aws://ACCOUNT_ID/ap-northeast-1

# または環境変数から自動取得
cdk bootstrap
```

**注意**: `ACCOUNT_ID`は`aws sts get-caller-identity`で確認したアカウントIDに置き換えてください。

### 1.4 CDKスタックのシンセサイズ（確認）

```bash
# CloudFormationテンプレートを生成して確認
cdk synth

# どのスタックが作成されるか確認
cdk list
```

出力例：
```
LineAgentSecretsStack
LineAgentLambdaStack
LineAgentAgentCoreStack
```

### 1.5 CDKスタックのデプロイ

```bash
# すべてのスタックをデプロイ
cdk deploy --all

# または個別にデプロイ
cdk deploy LineAgentSecretsStack
cdk deploy LineAgentLambdaStack
cdk deploy LineAgentAgentCoreStack
```

**確認プロンプト**: IAMリソースの作成許可を求められたら`y`を入力

### 1.6 デプロイ結果の確認

デプロイが完了すると、以下の出力が表示されます：

```
✅  LineAgentSecretsStack

Outputs:
LineAgentSecretsStack.LineSecretArn = arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:line-agent-secretary/line-credentials-XXXXXX
LineAgentSecretsStack.LineSecretSetupInstructions = Update the LINE secret with: aws secretsmanager update-secret...

✅  LineAgentLambdaStack

✅  LineAgentAgentCoreStack

Outputs:
LineAgentAgentCoreStack.GatewayRoleArn = arn:aws:iam::123456789012:role/LineAgentAgentCoreStack-GatewayServiceRole...
LineAgentAgentCoreStack.RuntimeRoleArn = arn:aws:iam::123456789012:role/LineAgentAgentCoreStack-RuntimeExecutionRole...
```

**重要**: これらの出力値（ARN）をメモしてください。次のステップで使用します。

---

## Step 2: LINE認証情報の設定

### 2.1 LINE Developer Consoleで認証情報を取得

1. [LINE Developers Console](https://developers.line.biz/console/)にアクセス
2. チャネルを作成または選択
3. 以下の情報をコピー:
   - **Channel Secret**: 「Basic settings」タブ
   - **Channel Access Token**: 「Messaging API」タブで発行

### 2.2 Secrets Managerに認証情報を保存

```bash
# プロジェクトルートディレクトリに戻る
cd ..

# LINE認証情報を設定
aws secretsmanager update-secret \
  --region ap-northeast-1 \
  --secret-id line-agent-secretary/line-credentials \
  --secret-string '{
    "channel_secret": "YOUR_LINE_CHANNEL_SECRET",
    "channel_access_token": "YOUR_LINE_CHANNEL_ACCESS_TOKEN"
  }'
```

**置き換える値**:
- `YOUR_LINE_CHANNEL_SECRET`: LINE Developer Consoleからコピーしたチャネルシークレット
- `YOUR_LINE_CHANNEL_ACCESS_TOKEN`: LINE Developer Consoleからコピーしたアクセストークン

### 2.3 設定の確認

```bash
# Secretが正しく更新されたか確認
aws secretsmanager get-secret-value \
  --region ap-northeast-1 \
  --secret-id line-agent-secretary/line-credentials \
  --query SecretString \
  --output text
```

---

## Step 3: Lambda関数の確認

### 3.1 Lambda関数が作成されたことを確認

```bash
# Lambda関数の一覧を取得
aws lambda list-functions \
  --region ap-northeast-1 \
  --query 'Functions[?contains(FunctionName, `CalendarOperations`)].FunctionName'
```

### 3.2 Lambda関数のARNを取得

```bash
# Lambda関数のARNを取得（次のステップで使用）
aws lambda get-function \
  --region ap-northeast-1 \
  --function-name $(aws lambda list-functions --region ap-northeast-1 --query 'Functions[?contains(FunctionName, `CalendarOperations`)].FunctionName' --output text) \
  --query 'Configuration.FunctionArn' \
  --output text
```

**出力例**: `arn:aws:lambda:ap-northeast-1:123456789012:function:LineAgentLambdaStack-CalendarOperationsFunction...`

この値を保存してください。

---

## Step 4: AgentCore Gatewayの作成

### 4.1 AgentCore ConsoleでGatewayを作成

1. [AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/)にアクセス
2. リージョンを**ap-northeast-1**に変更
3. 左メニューから「Gateways」を選択
4. 「Create gateway」をクリック

### 4.2 Gateway設定

#### Gateway details
- **Gateway name**: `line-agent-calendar-gateway`（任意の名前）
- **Description**: `Gateway for LINE Agent Secretary calendar operations`

#### Inbound Auth configurations
オプション1: Quick create（推奨）
- 「Quick create configurations with Cognito」を選択
- Cognitoリソースが自動的に作成されます

オプション2: Existing identity provider
- 既存のIDPがある場合はそちらを使用

#### Permissions
- 「Use an IAM service role」を選択
- 「Use an existing service role」を選択
- **Service role name**: CDKで作成された`LineAgentAgentCoreStack-GatewayServiceRole...`を選択
  - ドロップダウンから選択するか、Step 1.6でメモしたARNを参照

#### Target設定（Gatewayと同時に作成する場合）
一旦スキップして、Gateway作成後に追加することもできます。

「Create gateway」をクリック

### 4.3 Gateway IDとURLを保存

作成が完了すると、以下の情報が表示されます：
- **Gateway ID**: `gtw-xxxxxxxxxxxxx`
- **Gateway URL**: `https://gtw-xxxxxxxxxxxxx.gateway.bedrock-agentcore.ap-northeast-1.amazonaws.com/mcp`

この情報をメモしてください。

---

## Step 5: Lambda TargetをGatewayに追加

### 5.1 Targetの追加（コンソール）

1. 作成したGatewayの詳細画面で「Targets」タブを選択
2. 「Add target」をクリック

#### Target configuration
- **Target name**: `calendar-operations`
- **Target type**: Lambda を選択
- **Lambda ARN**: Step 3.2で取得したLambda関数のARNを入力

#### Tool schema
「Define inline」を選択し、以下のJSONを入力:

```json
[
  {
    "name": "list_calendar_events",
    "description": "カレンダーの予定を取得する",
    "inputSchema": {
      "type": "object",
      "properties": {
        "time_min": {
          "type": "string",
          "description": "取得開始日時（ISO 8601形式）"
        },
        "time_max": {
          "type": "string",
          "description": "取得終了日時（ISO 8601形式）"
        },
        "max_results": {
          "type": "number",
          "description": "最大取得件数"
        }
      }
    }
  },
  {
    "name": "create_calendar_event",
    "description": "カレンダーに予定を作成する",
    "inputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "予定のタイトル"
        },
        "start_time": {
          "type": "string",
          "description": "開始日時（ISO 8601形式）"
        },
        "end_time": {
          "type": "string",
          "description": "終了日時（ISO 8601形式）"
        },
        "description": {
          "type": "string",
          "description": "予定の説明"
        },
        "location": {
          "type": "string",
          "description": "場所"
        }
      },
      "required": ["summary", "start_time", "end_time"]
    }
  },
  {
    "name": "update_calendar_event",
    "description": "カレンダーの予定を更新する",
    "inputSchema": {
      "type": "object",
      "properties": {
        "event_id": {
          "type": "string",
          "description": "更新する予定のID"
        },
        "summary": {
          "type": "string",
          "description": "予定のタイトル"
        },
        "start_time": {
          "type": "string",
          "description": "開始日時（ISO 8601形式）"
        },
        "end_time": {
          "type": "string",
          "description": "終了日時（ISO 8601形式）"
        },
        "description": {
          "type": "string",
          "description": "予定の説明"
        },
        "location": {
          "type": "string",
          "description": "場所"
        }
      },
      "required": ["event_id"]
    }
  },
  {
    "name": "delete_calendar_event",
    "description": "カレンダーの予定を削除する",
    "inputSchema": {
      "type": "object",
      "properties": {
        "event_id": {
          "type": "string",
          "description": "削除する予定のID"
        }
      },
      "required": ["event_id"]
    }
  }
]
```

#### Outbound authorization
- 「Gateway IAM role」を選択

「Add target」をクリック

### 5.2 Target追加の確認

Targetsタブで`calendar-operations`が表示されることを確認してください。

---

## Step 6: Lambda関数のテスト（初回OAuth認証）

### 6.1 Lambda関数を直接テスト

```bash
# テストイベントを作成
cat > test-event.json << 'EOF'
{
  "operation": "list",
  "parameters": {
    "max_results": 5
  }
}
EOF

# Lambda関数を実行
aws lambda invoke \
  --region ap-northeast-1 \
  --function-name $(aws lambda list-functions --region ap-northeast-1 --query 'Functions[?contains(FunctionName, `CalendarOperations`)].FunctionName' --output text) \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

# レスポンスを確認
cat response.json
```

### 6.2 初回OAuth認証

Lambda関数を初めて実行すると、OAuth認証URLが返される場合があります：

```json
{
  "statusCode": 200,
  "body": "{\"auth_url\": \"https://accounts.google.com/o/oauth2/auth?...\"}"
}
```

**手順**:
1. `auth_url`の値をブラウザにコピー＆ペースト
2. Googleアカウントでログイン（テストユーザーとして登録したアカウント）
3. カレンダーへのアクセス許可を承認
4. 認証完了後、もう一度Lambda関数を実行

### 6.3 認証後のテスト

```bash
# もう一度Lambda関数を実行
aws lambda invoke \
  --region ap-northeast-1 \
  --function-name $(aws lambda list-functions --region ap-northeast-1 --query 'Functions[?contains(FunctionName, `CalendarOperations`)].FunctionName' --output text) \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

# レスポンスを確認（カレンダーイベントが取得できるはず）
cat response.json
```

---

## Step 7: AgentCore Runtimeの作成（今後の実装）

TODO: Strands Agentsを使ったエージェント実装後に以下を実装
- Dockerコンテナの作成
- ECRへのプッシュ
- AgentCore Runtimeの作成
- エンドポイントの設定

---

## トラブルシューティング

### CDKデプロイエラー: "Unable to determine which files to ship"

**原因**: pyproject.tomlにパッケージ設定が不足

**解決方法**: pyproject.tomlに以下が含まれているか確認:
```toml
[tool.hatch.build.targets.wheel]
packages = ["agent", "functions", "infra"]
```

### Lambda関数がAgentCore Identityにアクセスできない

**原因**: IAMロールの権限不足

**解決方法**: Lambda実行ロールに以下の権限があるか確認:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock-agentcore-control:CreateWorkloadIdentity",
    "bedrock-agentcore-control:GetWorkloadAccessToken",
    "bedrock-agentcore-control:GetResourceOauth2Token"
  ],
  "Resource": "*"
}
```

### Gateway作成時にService Roleが見つからない

**原因**: CDKスタックが正しくデプロイされていない

**解決方法**:
```bash
# スタックの状態を確認
aws cloudformation describe-stacks \
  --region ap-northeast-1 \
  --stack-name LineAgentAgentCoreStack

# ロールが存在するか確認
aws iam list-roles --query 'Roles[?contains(RoleName, `GatewayServiceRole`)]'
```

---

## チェックリスト

デプロイが完了したら、以下を確認してください:

- [ ] `uv sync --extra infra`実行済み
- [ ] CDK Bootstrapが完了
- [ ] 3つのCDKスタックがデプロイ済み
- [ ] LINE認証情報をSecrets Managerに設定
- [ ] Lambda関数が作成されている
- [ ] AgentCore Gatewayが作成されている
- [ ] Lambda TargetがGatewayに追加されている
- [ ] Lambda関数のテストが成功（OAuth認証完了）
- [ ] カレンダーイベントの取得が成功

すべて完了したら、エージェントの実装とLINE連携に進みます！
