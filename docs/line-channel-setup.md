# LINE Messaging APIチャネル作成ガイド

LINE Agent Secretaryで使用するLINE Messaging APIチャネルの詳細なセットアップ手順

## 前提条件

- LINEアカウント（個人用またはビジネス用）
- メールアドレス（認証用）

---

## Step 1: LINE Developersアカウントの作成

### 1.1 LINE Developers Consoleにアクセス

1. [LINE Developers Console](https://developers.line.biz/console/)にアクセス
2. 「ログイン」ボタンをクリック

### 1.2 LINEアカウントでログイン

1. LINEアカウントでログイン
   - QRコードでログイン、または
   - メールアドレスとパスワードでログイン
2. 初回の場合、開発者登録が必要です

### 1.3 開発者登録（初回のみ）

1. 「開発者として登録する」をクリック
2. 利用規約を確認
3. 以下の情報を入力:
   - **名前**: あなたの名前（本名推奨）
   - **メールアドレス**: 連絡先メールアドレス
4. 「Register」をクリック
5. 登録確認メールが届くので、メール内のリンクをクリックして認証

---

## Step 2: プロバイダーの作成

プロバイダーは、複数のチャネルをグループ化するための組織単位です。

### 2.1 新しいプロバイダーを作成

1. LINE Developers Consoleのトップページで「Create」→「Provider」をクリック
2. プロバイダー情報を入力:
   - **Provider name**: `Personal Assistant`（任意の名前）
     - 個人使用の場合は自分の名前やプロジェクト名でOK
3. 「Create」をクリック

---

## Step 3: Messaging APIチャネルの作成

### 3.1 新しいチャネルを作成

1. 作成したプロバイダーのページで「Create a new channel」をクリック
2. チャネルタイプで「Messaging API」を選択

### 3.2 チャネル情報を入力

以下の情報を入力します:

#### 基本情報

- **Channel type**: Messaging API（自動選択済み）
- **Provider**: 先ほど作成したプロバイダー（自動選択済み）
- **Company or owner's country or region**: Japan（日本）
- **Channel icon**: （オプション）ボットのアイコン画像をアップロード
  - 推奨サイズ: 512x512px
  - スキップ可能、後から設定も可能

#### チャネル詳細

- **Channel name**: `LINE Agent Secretary`（任意の名前）
  - これがLINE上でユーザーに表示される名前になります
- **Channel description**: `個人用AIエージェント秘書`（任意の説明）
  - 最低10文字以上
  - 例: "個人用のAI秘書ボットです。カレンダー管理などをサポートします。"
- **Category**: `Personal`（個人用）または適切なカテゴリを選択
- **Subcategory**: 適切なサブカテゴリを選択（例: `Productivity`）

#### 利用規約とプライバシーポリシー（オプション）

個人使用の場合は空欄でOKです。

- **Terms of use URL**: 空欄
- **Privacy policy URL**: 空欄

### 3.3 規約への同意

1. 以下の項目にチェックを入れます:
   - ✅ LINE Official Account Terms of Use
   - ✅ LINE Official Account API Terms of Use
2. 「Create」ボタンをクリック

### 3.4 チャネル作成完了

チャネルが作成されると、チャネルの詳細ページに遷移します。

---

## Step 4: Messaging API設定

### 4.1 Messaging APIタブにアクセス

1. 作成したチャネルの詳細ページで「Messaging API」タブをクリック

### 4.2 Webhook設定の準備

後でAgentCore RuntimeのエンドポイントをWebhook URLとして設定します。現時点では以下を確認:

- **Webhook URL**: （空欄のまま、後で設定）
- **Use webhook**: OFF（後でONにする）

### 4.3 応答メッセージの設定

LINE公式アカウント機能と競合しないように設定します:

1. 「LINE Official Account features」セクションを見つける
2. 以下のように設定:
   - **Auto-reply messages**: Disabled（無効）
   - **Greeting messages**: Disabled（無効）

   これにより、ボットが独自の応答を制御できるようになります。

3. 設定を変更するには「Edit」リンクをクリックしてLINE Official Account Managerに移動:
   - 左メニューから「応答設定」を選択
   - 「応答メッセージ」をオフ
   - 「あいさつメッセージ」をオフ
   - 「Webhook」をオン

### 4.4 チャネルアクセストークンの発行

⚠️ **重要**: このトークンは秘密情報です。安全に保管してください。

1. 「Messaging API」タブの下部「Channel access token」セクションを見つける
2. 「Issue」ボタンをクリック
3. 発行されたトークンが表示されます（例: `abcdef1234567890...`）
4. **このトークンをコピーして安全な場所に保存**してください
   - 後でAWS Secrets Managerに保存します

---

## Step 5: Channel Secretの取得

### 5.1 Basic settingsタブにアクセス

1. チャネル詳細ページで「Basic settings」タブをクリック

### 5.2 Channel Secretをコピー

1. 「Channel secret」セクションを見つける
2. シークレットをコピー（例: `0123456789abcdef0123456789abcdef`）
3. **このシークレットをコピーして安全な場所に保存**してください
   - 後でAWS Secrets Managerに保存します

---

## Step 6: ボットを友だち追加

### 6.1 QRコードでボットを追加

1. 「Messaging API」タブに戻る
2. 「Bot information」セクションを見つける
3. **QRコード**または**Bot basic ID**を使ってLINEアプリでボットを友だち追加
   - スマートフォンのLINEアプリで「友だち追加」→「QRコード」でスキャン
   - または、Bot basic ID（@で始まるID）で検索

### 6.2 友だち追加の確認

LINEアプリで、作成したボットが友だちリストに表示されることを確認してください。

---

## Step 7: AWS Secrets Managerに認証情報を保存

Step 4とStep 5で取得した情報をAWSに保存します。

### 7.1 認証情報の確認

以下の2つの情報が揃っていることを確認:
- ✅ **Channel Secret**: Basic settingsタブから取得（32文字の16進数）
- ✅ **Channel Access Token**: Messaging APIタブで発行（長いトークン文字列）

### 7.2 Secrets Managerに保存

```bash
aws secretsmanager update-secret \
  --region ap-northeast-1 \
  --secret-id line-agent-secretary/line-credentials \
  --secret-string '{
    "channel_secret": "YOUR_CHANNEL_SECRET_HERE",
    "channel_access_token": "YOUR_CHANNEL_ACCESS_TOKEN_HERE"
  }'
```

**置き換える値**:
- `YOUR_CHANNEL_SECRET_HERE`: Step 5で取得したChannel Secret
- `YOUR_CHANNEL_ACCESS_TOKEN_HERE`: Step 4で取得したChannel Access Token

### 7.3 保存の確認

```bash
aws secretsmanager get-secret-value \
  --region ap-northeast-1 \
  --secret-id line-agent-secretary/line-credentials \
  --query SecretString \
  --output text
```

正しく保存されていれば、JSONが表示されます。

---

## Step 8: Webhook URLの設定（後で実装）

⚠️ **注意**: この手順はAgentCore Runtimeをデプロイした後に行います。

### 8.1 AgentCore RuntimeのエンドポイントURLを取得

AgentCore Runtimeをデプロイすると、以下のようなエンドポイントURLが発行されます:
```
https://runtime-xxxxxxxxxxxxx.runtime.bedrock-agentcore.ap-northeast-1.amazonaws.com/webhook
```

### 8.2 Webhook URLを設定

1. LINE Developers Console → チャネル → Messaging APIタブ
2. 「Webhook settings」セクション
3. 「Webhook URL」にAgentCore RuntimeのエンドポイントURLを入力
4. 「Update」をクリック
5. 「Verify」ボタンをクリックしてWebhookをテスト
6. 「Use webhook」をONにする

---

## トラブルシューティング

### チャネルアクセストークンが発行できない

**原因**: チャネルの設定が完了していない

**解決方法**:
1. チャネルの作成がすべて完了しているか確認
2. ページをリフレッシュして再度試す

### ボットからメッセージが返ってこない

**原因1**: 応答メッセージがオンになっている

**解決方法**:
1. LINE Official Account Managerで「応答メッセージ」をオフ
2. 「Webhook」をオンにする

**原因2**: Webhook URLが設定されていない

**解決方法**:
1. AgentCore Runtimeをデプロイ
2. Webhook URLを設定

### "Forbidden"エラーが出る

**原因**: Channel Secretが正しくない、または署名検証に失敗

**解決方法**:
1. Secrets Managerに保存したChannel Secretが正しいか確認
2. channel_secretの前後にスペースや改行が入っていないか確認

---

## セキュリティのベストプラクティス

### 認証情報の管理

1. **Channel SecretとAccess Tokenは絶対に公開しない**
   - GitHubなどのパブリックリポジトリにコミットしない
   - ログに出力しない

2. **Access Tokenは定期的に再発行する**
   - セキュリティ上、定期的にトークンを再発行することを推奨
   - 再発行後、AWS Secrets Managerを更新

3. **Webhook署名を必ず検証する**
   - エージェントのコードでLINEからのリクエスト署名を検証
   - これにより、なりすましを防止

---

## チェックリスト

LINEチャネルのセットアップが完了したら、以下を確認してください:

- [ ] LINE Developersアカウントを作成
- [ ] プロバイダーを作成
- [ ] Messaging APIチャネルを作成
- [ ] チャネルアクセストークンを発行して保存
- [ ] Channel Secretを取得して保存
- [ ] AWS Secrets Managerに認証情報を保存
- [ ] 応答メッセージとあいさつメッセージをオフ
- [ ] LINEアプリでボットを友だち追加
- [ ] （後で）Webhook URLを設定してテスト

すべて完了したら、AgentCore Gatewayの作成とLambda Targetの追加に進んでください！

---

## 参考情報

- [LINE Messaging API ドキュメント](https://developers.line.biz/en/docs/messaging-api/)
- [LINE Developers Console](https://developers.line.biz/console/)
- [Messaging API リファレンス](https://developers.line.biz/en/reference/messaging-api/)
