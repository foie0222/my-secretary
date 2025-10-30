# LINE Agent Secretary

LINEで対話できる個人用AIエージェント秘書システム

AWS AgentCore、AgentCore Identity、Strands Agentsを使用して、Google Calendarなどのサービスと連携します。

## プロジェクト構成

```
line-agent-secretary/
├── agent/                      # エージェント本体
│   ├── main.py                # エントリーポイント
│   ├── line_handler.py        # LINE Webhook処理
│   └── config.py              # 設定管理
├── functions/                  # Lambda関数群
│   ├── calendar/              # カレンダー操作
│   │   └── operations.py     # AgentCore Identity使用
│   └── common/                # 共通処理
│       └── utils.py
├── infra/                      # AWS CDK
│   ├── app.py                 # CDKアプリケーション
│   ├── cdk.json              # CDK設定
│   └── stacks/
│       ├── lambda_stack.py       # Lambda関数
│       ├── agentcore_stack.py    # AgentCore設定
│       └── secrets_stack.py      # Secrets Manager
├── pyproject.toml              # uv設定
├── requirements.md             # 詳細な要件定義
└── README.md                   # このファイル
```

## 技術スタック

- **言語**: Python 3.12
- **パッケージ管理**: uv
- **エージェント**: Strands Agents
- **インフラ**: AWS CDK
- **AWS サービス**:
  - AgentCore Runtime (エージェントホスティング)
  - AgentCore Gateway (ツール統合)
  - **AgentCore Identity** (OAuth2認証管理)
  - Lambda (Google Calendar API呼び出し)
  - Secrets Manager (LINE認証情報)

## セットアップ手順

### 1. 環境構築

```bash
# uvのインストール（既にインストール済み）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係のインストール
uv sync

# CDK用の依存関係
uv sync --extra infra
```

### 2. Google OAuth2設定

#### Google Cloud Consoleでの設定

📖 **[詳細な手順はこちら → docs/google-oauth-setup.md](./docs/google-oauth-setup.md)**

簡易手順:
1. [Google Developer Console](https://console.developers.google.com/project)にアクセス
2. Google Calendar APIを有効化
3. OAuth同意画面を作成
4. OAuth 2.0 認証情報を作成
5. 以下のスコープを追加:
   ```
   https://www.googleapis.com/auth/calendar
   ```
6. リダイレクトURIを追加:
   ```
   https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback
   ```
   ⚠️ リージョンを変更する場合は`ap-northeast-1`を適切なリージョンに変更してください

#### AgentCore Identity OAuth2 Credential Provider作成

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

### 3. CDKでインフラをデプロイ

```bash
cd infra

# CDK Bootstrap（初回のみ）
cdk bootstrap

# スタックをデプロイ
cdk deploy --all

# 出力されたARNなどをメモ
```

### 4. LINE認証情報の設定

デプロイ後、Secrets Managerに手動でLINE認証情報を設定:

```bash
aws secretsmanager update-secret \
  --secret-id line-agent-secretary/line-credentials \
  --secret-string '{
    "channel_secret": "YOUR_LINE_CHANNEL_SECRET",
    "channel_access_token": "YOUR_LINE_CHANNEL_ACCESS_TOKEN"
  }'
```

### 5. AgentCore Gatewayの設定

#### コンソールでGatewayを作成

1. [AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/)にアクセス
2. **Gateways** → **Create gateway**
3. 設定:
   - **Inbound Auth**: Cognito Quick Create または既存のIDP
   - **Service Role**: CDKで作成されたGatewayRoleを選択
4. **Create gateway**

#### Lambda TargetをGatewayに追加

```bash
aws bedrock-agentcore-control create-gateway-target \
  --gateway-identifier <GATEWAY_ID> \
  --name "calendar-operations" \
  --target-configuration '{
    "mcp": {
      "lambda": {
        "lambdaArn": "<CALENDAR_LAMBDA_ARN>",
        "toolSchema": {
          "inlinePayload": [
            {
              "name": "list_calendar_events",
              "description": "カレンダーの予定を取得する",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "time_min": {"type": "string"},
                  "time_max": {"type": "string"},
                  "max_results": {"type": "number"}
                }
              }
            },
            {
              "name": "create_calendar_event",
              "description": "カレンダーに予定を作成する",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "summary": {"type": "string"},
                  "start_time": {"type": "string"},
                  "end_time": {"type": "string"},
                  "description": {"type": "string"},
                  "location": {"type": "string"}
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
                  "event_id": {"type": "string"},
                  "summary": {"type": "string"},
                  "start_time": {"type": "string"},
                  "end_time": {"type": "string"},
                  "description": {"type": "string"},
                  "location": {"type": "string"}
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
                  "event_id": {"type": "string"}
                },
                "required": ["event_id"]
              }
            }
          ]
        }
      }
    }
  }' \
  --credential-provider-configurations '[
    {
      "credentialProviderType": "GATEWAY_IAM_ROLE"
    }
  ]'
```

### 6. AgentCore Runtimeの作成とデプロイ

TODO: Strands Agentsを使ったエージェント実装とRuntimeへのデプロイ手順

### 7. LINE Webhookの設定

1. LINE Developers Consoleで Webhook URLを設定
2. AgentCore RuntimeのエンドポイントURLを指定

## ローカル開発

```bash
# 環境変数を設定
export LINE_CHANNEL_SECRET="your_channel_secret"
export LINE_CHANNEL_ACCESS_TOKEN="your_access_token"
export AGENTCORE_GATEWAY_URL="https://your-gateway.bedrock-agentcore.amazonaws.com/mcp"

# ローカルサーバーを起動
cd agent
python main.py

# ngrokなどでトンネルを作成してLINE Webhookをテスト
ngrok http 8000
```

## 主要な機能

### Phase 1 (MVP) - 実装済み

- ✅ Google Calendar操作Lambda関数（AgentCore Identity使用）
- ✅ CDKインフラストラクチャ
- ✅ LINE Webhookハンドラー（基本実装）
- ⬜ Strands Agentsとの統合（TODO）
- ⬜ AgentCore Runtimeへのデプロイ（TODO）

### Phase 2 (将来)

- Gmail統合
- Slack連携
- その他のタスク

## AgentCore Identityの使用方法

本プロジェクトでは、Google APIの認証にAgentCore Identityを使用しています:

```python
from bedrock_agentcore.identity.auth import requires_access_token

@requires_access_token(
    provider_name="google-calendar-provider",
    scopes=["https://www.googleapis.com/auth/calendar"],
    auth_flow="USER_FEDERATION",
)
async def calendar_operation(*, access_token: str):
    # access_tokenは自動的にAgentCore Identityから注入される
    # Google Calendar APIを呼び出す
    pass
```

### セキュリティ上の利点

1. **トークンの分離**: エージェントは長期的なリフレッシュトークンにアクセスできない
2. **自動管理**: トークンのリフレッシュはAgentCore Identityが自動処理
3. **監査**: すべてのトークンアクセスがログに記録される
4. **暗号化**: Token Vaultで認証情報を暗号化して保存

## トラブルシューティング

### Lambda関数がAgentCore Identityにアクセスできない

IAMロールに以下の権限が必要です:
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

### Google OAuth2認証エラー

1. リダイレクトURIが正しく設定されているか確認
2. Credential Providerが正しく作成されているか確認:
   ```bash
   aws bedrock-agentcore-control list-oauth2-credential-providers --region ap-northeast-1
   ```

## 参考資料

- [AWS AgentCore公式ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)
- [LINE Messaging API](https://developers.line.biz/en/reference/messaging-api/)
- [Google Calendar API](https://developers.google.com/calendar/api)
- [Strands Agents SDK](https://github.com/anthropics/strands)

## ライセンス

MIT
