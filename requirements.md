# LINE AIエージェント秘書システム 要件定義書

## プロジェクト概要

LINEで対話できる個人用AIエージェント秘書システム。AWS AgentCoreをバックエンドとして、自然言語で様々なタスクを処理できる拡張可能なアーキテクチャを構築する。

**プロジェクト名**: line-agent-secretary  
**対象ユーザー**: シングルユーザー(個人専用)  
**主要技術**: AWS AgentCore, Python, LINE Messaging API

---

## Phase 1: MVP機能(Googleカレンダー統合)

### カレンダー操作機能

#### 1. 予定の確認(読み取り)
- 「今日の予定は?」
- 「来週の火曜日空いてる?」
- 「明日の会議は何時から?」

#### 2. 予定の追加(作成)
- 「明日14時から会議を入れて」
- 「来週の金曜日ランチミーティング追加」

#### 3. 予定の変更(更新)
- 「会議を1時間後ろ倒しにして」
- 「明日の予定の場所を変更して」

#### 4. 予定の削除
- 「明日の15時の予定をキャンセル」
- 「来週の会議を削除」

**対象カレンダー**: 主カレンダー(primary)のみ

---

## Phase 2以降: 拡張機能(将来実装)

### Gmail統合
- メールの確認・検索
- メールの作成・送信
- メールへの返信
- 重要メールの要約

### その他のタスク候補
- Slackメッセージの送信
- Notionへのメモ作成
- タスク管理(Asana/Jira連携)
- ファイル管理(Google Drive)
- 情報検索・要約
- リマインダー設定

---

## システムアーキテクチャ

### 全体構成

```
LINE (統一インターフェース)
 ↓
AgentCore Runtime (エージェント本体)
 ↓
AgentCore Gateway (ツール管理ハブ)
 ↓
┌─────────────┬─────────────┬─────────────┐
│ Lambda      │ Lambda      │ Lambda      │
│ Calendar    │ Gmail       │ その他      │
│ Operations  │ Operations  │ Tasks       │
└─────────────┴─────────────┴─────────────┘
      ↓              ↓              ↓
Google Calendar  Gmail API    他サービス
```

### Phase 1 アーキテクチャ(MVP)

```
LINE
 ↓
AgentCore Runtime
 ↓
AgentCore Gateway (4つのMCPツール定義)
 - list_calendar_events
 - create_calendar_event
 - update_calendar_event
 - delete_calendar_event
 ↓
Lambda 1つ (calendar_operations)
 ↓
Google Calendar API

補助リソース:
- AgentCore Identity: Google OAuth2認証管理（Credential Provider）
- Secrets Manager: LINE認証情報のみ
- CloudWatch: ログ・監視
```

### コンポーネント説明

#### AgentCore Runtime
- エージェント本体をホスト
- LINEからのWebhookを直接受信
- 最大8時間の実行時間をサポート
- 完全なセッション分離

#### AgentCore Gateway
- 既存のLambda関数をMCP互換ツールに変換
- ツールの統一的な管理
- 認証・認可の一元化

#### Lambda関数
- Google Calendar API呼び出し
- 1つのLambda内で4つの操作を処理
  - list: 予定の取得
  - create: 予定の作成
  - update: 予定の更新
  - delete: 予定の削除

---

## プロジェクト構造

```
line-agent-secretary/
├── pyproject.toml              # uv設定
├── .python-version             # Python 3.12
├── README.md                   # プロジェクト説明
├── requirements.md             # 本ドキュメント
│
├── agent/                      # エージェント本体
│   ├── main.py                # エントリーポイント
│   ├── line_handler.py        # LINE Webhook処理
│   └── config.py              # 設定管理
│
├── functions/                  # Lambda関数群
│   ├── calendar/              # Phase 1
│   │   └── operations.py     # カレンダー操作Lambda
│   ├── gmail/                 # Phase 2 (将来)
│   │   └── operations.py
│   ├── other_tasks/           # Phase 3+ (将来)
│   └── common/                # 共通処理
│       ├── auth_manager.py   # 認証管理
│       └── utils.py          # ユーティリティ
│
├── infra/                      # AWS CDK
│   ├── app.py                 # CDKアプリケーション
│   └── stacks/
│       ├── agentcore_stack.py    # AgentCore設定
│       ├── lambda_stack.py       # Lambda設定
│       └── secrets_stack.py      # Secrets Manager設定
│
└── scripts/                    # セットアップスクリプト
    └── setup_oauth.py         # OAuth設定補助
```

---

## 技術スタック

### Phase 1 (MVP)

| カテゴリ | 技術 |
|---------|------|
| 言語 | Python 3.12 |
| パッケージ管理 | uv |
| エージェントフレームワーク | Strands Agents |
| IaC | AWS CDK (Python) |
| ランタイム | AWS AgentCore Runtime |
| ツール統合 | AWS AgentCore Gateway |
| 認証管理 | **AWS AgentCore Identity** (OAuth2), AWS Secrets Manager (LINE認証) |
| ログ・監視 | AWS CloudWatch |
| Google API | google-api-python-client |
| AgentCore SDK | bedrock-agentcore |

### Phase 2以降の追加予定

- Gmail API client
- Slack SDK
- Notion API client
- その他サービスSDK

---

## 開発原則

### 1. 段階的実装
MVP(カレンダー機能)から始め、段階的に機能を追加

### 2. 疎結合設計
各機能(カレンダー、Gmail等)は独立したモジュールとして実装し、追加・削除が容易な構造

### 3. 統一インターフェース
すべての機能をLINEから自然言語で操作可能にする

### 4. セキュリティ優先
- LINE署名検証の実装
- **AgentCore Identity**によるOAuth 2.0認証管理
  - Token Vaultでの暗号化保存
  - エージェントは長期シークレットに直接アクセスしない
  - アクセストークンの自動リフレッシュ
- IAM最小権限の原則
- LINE認証情報のSecrets Manager管理

### 5. 保守性
- 明確なディレクトリ構造
- 適切なドキュメント
- コードの可読性重視

---

## 非機能要件

### パフォーマンス
- **応答時間**: LINE返信は5秒以内を目標
- **スケーラビリティ**: AgentCore Runtimeのオートスケーリング活用

### 可用性
- AgentCore Runtimeの高可用性を活用
- エラーハンドリングの徹底

### コスト
- **目標**: 月額$10以下(個人利用想定)
- 従量課金モデルの活用
- 不要なリソースの削減

### セキュリティ
- LINE署名検証による不正アクセス防止
- **AgentCore Identity**によるOAuth 2.0認証管理
  - 認証情報の分離とToken Vaultでの暗号化保存
  - 完全な監査ログとアクセス追跡
  - エージェントは短期アクセストークンのみ使用
- IAM最小権限の原則適用

---

## 実装フェーズ

### Phase 1: 基盤構築 (1-2日)
1. プロジェクトセットアップ(uv環境構築)
2. **AgentCore Identity OAuth2 Credential Provider設定** (Google Calendar API)
3. Lambda関数の実装(calendar_operations) - `@requires_access_token`使用
4. AgentCore Gateway設定（MCPツール定義）

### Phase 2: エージェント実装 (1-2日)
5. Strands AgentsでLINE連携実装
6. AgentCore Runtimeへのデプロイ
7. LINE Webhook設定

### Phase 3: テスト・改善 (1日)
8. 動作確認・統合テスト
9. エラーハンドリング強化
10. 会話フローの改善

### Phase 4: 拡張機能 (将来)
11. Gmail統合
12. その他タスク追加
13. 機能拡張に応じたアーキテクチャ最適化

---

## 拡張性の考慮事項

### モジュラー設計
- 各サービス(Calendar、Gmail等)は独立したLambda関数として実装
- AgentCore Gatewayで統一的にツールとして管理
- 新機能追加時は新しいLambda関数 + Gateway設定のみで対応可能

### 認証管理の拡張性（AgentCore Identity使用）
- **AgentCore Identity**で各サービスのOAuthトークンを一元管理
  - OAuth2 Credential Providerを使用してGoogle API認証を管理
  - トークンはToken Vaultに安全に保存され、自動的に管理される
  - `@requires_access_token`デコレーターで簡単にアクセストークンを取得
- サービスごとに独立したCredential Provider設定
- トークンの自動リフレッシュはAgentCore Identityが処理

### 状態管理(将来必要に応じて)
- **DynamoDB**: ユーザー設定、会話履歴の永続化
- **AgentCore Memory**: 会話コンテキスト、長期記憶の管理

---

## AgentCore Identity統合詳細

### OAuth2 Credential Providerのセットアップ

#### Google Calendar API用Credential Provider作成

```bash
aws bedrock-agentcore-control create-oauth2-credential-provider \
  --region ap-northeast-1 \
  --name "google-calendar-provider" \
  --credential-provider-vendor "GoogleOauth2" \
  --oauth2-provider-config-input '{
      "googleOauth2ProviderConfig": {
        "clientId": "<your-google-client-id>",
        "clientSecret": "<your-google-client-secret>"
      }
    }'
```

#### 必要なGoogle OAuth2スコープ
- `https://www.googleapis.com/auth/calendar` - カレンダーの完全アクセス

#### リダイレクトURI設定
Google Developer Consoleで以下のURIを設定：
```
https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback
```

### Lambda関数での使用方法

```python
from bedrock_agentcore.identity.auth import requires_access_token
import asyncio

@requires_access_token(
    provider_name="google-calendar-provider",
    scopes=["https://www.googleapis.com/auth/calendar"],
    auth_flow="USER_FEDERATION",  # OAuth 2.0 Authorization Code flow
    force_authentication=False,    # アクセストークンをキャッシュ
)
async def calendar_operation(*, access_token: str):
    # Google Calendar APIを呼び出す
    # access_tokenは自動的にAgentCore Identityから注入される
    pass
```

### セキュリティ上の利点

1. **トークンの分離**: エージェントは長期的なリフレッシュトークンにアクセスできない
2. **自動管理**: トークンのリフレッシュはAgentCore Identityが自動処理
3. **監査**: すべてのトークンアクセスがログに記録される
4. **暗号化**: Token Vaultで認証情報を暗号化して保存

---

## リスクと対策

### リスク1: Google APIのレート制限
**対策**: 
- リクエストのキャッシュ化
- エラーハンドリングでリトライロジック実装

### リスク2: AgentCoreの学習コスト
**対策**:
- 公式ドキュメント・サンプルの活用
- 段階的な実装でノウハウ蓄積

### リスク3: コスト超過
**対策**:
- CloudWatchでコスト監視
- 不要な長時間実行の防止
- 定期的なコストレビュー

### リスク4: OAuth認証の複雑性
**対策**:
- 初回セットアップスクリプトの作成
- トークン管理の自動化

---

## 成功の定義

### Phase 1 (MVP)
- [ ] LINEから自然言語でカレンダー操作が可能
- [ ] 4つの基本操作(確認・追加・変更・削除)が動作
- [ ] 応答時間5秒以内を達成
- [ ] エラーなく1週間安定稼働

### Phase 2以降
- [ ] Gmail統合が動作
- [ ] 複数サービスをシームレスに連携
- [ ] 月額コストが目標内
- [ ] ユーザー満足度の高い会話体験

---

## 参考資料

- [AWS AgentCore公式ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)
- [LINE Messaging API リファレンス](https://developers.line.biz/en/reference/messaging-api/)
- [Google Calendar API](https://developers.google.com/calendar/api)
- [Strands Agents SDK](https://github.com/anthropics/strands)
