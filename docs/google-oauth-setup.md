# Google Cloud Console OAuth2 設定ガイド

AgentCore Identityを使用してGoogle Calendar APIにアクセスするための詳細なセットアップ手順

## 前提条件

- Googleアカウント（個人用またはWorkspace）
- AWSアカウントとAgentCore Identityへのアクセス権限

---

## Step 1: Google Cloud プロジェクトの作成

### 1.1 Google Cloud Consoleにアクセス

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. Googleアカウントでログイン

### 1.2 新しいプロジェクトを作成

1. 画面上部のプロジェクト選択ドロップダウンをクリック
2. 「新しいプロジェクト」をクリック
3. プロジェクト情報を入力:
   - **プロジェクト名**: `line-agent-secretary`（任意の名前）
   - **組織**: （個人の場合は「組織なし」）
   - **場所**: 任意
4. 「作成」をクリック
5. プロジェクトが作成されるまで数秒待機

### 1.3 プロジェクトを選択

作成したプロジェクトが自動的に選択されます。選択されていない場合は、画面上部のドロップダウンから選択してください。

---

## Step 2: Google Calendar APIを有効化

### 2.1 APIライブラリにアクセス

1. 左側のメニューから「APIとサービス」→「ライブラリ」をクリック
   - または直接 https://console.cloud.google.com/apis/library にアクセス

### 2.2 Google Calendar APIを検索して有効化

1. 検索バーに「Google Calendar API」と入力
2. 検索結果から「Google Calendar API」をクリック
3. 「有効にする」ボタンをクリック
4. APIが有効化されるまで数秒待機

---

## Step 3: OAuth同意画面の設定

### 3.1 OAuth同意画面にアクセス

1. 左側のメニューから「APIとサービス」→「OAuth同意画面」をクリック
   - または直接 https://console.cloud.google.com/apis/credentials/consent にアクセス

### 3.2 ユーザータイプを選択

1. **外部**を選択（個人用Googleアカウントの場合はこれのみ選択可能）
   - Workspaceアカウントの場合は「内部」も選択可能
2. 「作成」をクリック

### 3.3 OAuth同意画面の設定（ページ1: アプリ情報）

以下の情報を入力:

- **アプリ名**: `LINE Agent Secretary`（任意の名前）
- **ユーザーサポートメール**: あなたのメールアドレスを選択
- **アプリのロゴ**: （オプション）スキップ可能
- **アプリドメイン**: （オプション）スキップ可能
  - ホームページ: 空欄でOK
  - プライバシーポリシー: 空欄でOK
  - 利用規約: 空欄でOK
- **承認済みドメイン**: 空欄でOK
- **デベロッパーの連絡先情報**: あなたのメールアドレスを入力

「保存して次へ」をクリック

### 3.4 OAuth同意画面の設定（ページ2: スコープ）

1. 「スコープを追加または削除」ボタンをクリック
2. 表示されたダイアログで以下のスコープを検索して選択:
   ```
   https://www.googleapis.com/auth/calendar
   ```
   - フィルタに「calendar」と入力すると見つかります
   - 「Google Calendar API」の下にある「.../auth/calendar」を選択
   - 説明: 「See, edit, share, and permanently delete all the calendars you can access using Google Calendar」

3. 「更新」をクリック
4. 選択したスコープが表示されていることを確認
5. 「保存して次へ」をクリック

### 3.5 OAuth同意画面の設定（ページ3: テストユーザー）

⚠️ **重要**: アプリが「公開」状態でない限り、テストユーザーとして登録されたGoogleアカウントのみがアプリを使用できます。

1. 「+ ADD USERS」ボタンをクリック
2. あなたのGoogleアカウントのメールアドレスを入力（カレンダーにアクセスするアカウント）
3. 「追加」をクリック
4. 「保存して次へ」をクリック

### 3.6 OAuth同意画面の設定（ページ4: 概要）

1. 設定内容を確認
2. 「ダッシュボードに戻る」をクリック

---

## Step 4: OAuth 2.0 認証情報の作成

### 4.1 認証情報画面にアクセス

1. 左側のメニューから「APIとサービス」→「認証情報」をクリック
   - または直接 https://console.cloud.google.com/apis/credentials にアクセス

### 4.2 OAuth 2.0 クライアントIDの作成

1. 「+ 認証情報を作成」ボタンをクリック
2. 「OAuth クライアント ID」を選択

### 4.3 アプリケーションの種類を選択

1. **アプリケーションの種類**: 「ウェブ アプリケーション」を選択
2. **名前**: `LINE Agent Secretary - AgentCore`（任意の名前）

### 4.4 承認済みのリダイレクト URIを追加

⚠️ **最重要ステップ**: AgentCore Identityが使用するリダイレクトURIを正確に設定する必要があります。

1. 「承認済みのリダイレクト URI」セクションで「+ URIを追加」をクリック
2. 以下のURIを**正確に**入力:
   ```
   https://bedrock-agentcore.ap-northeast-1.amazonaws.com/identities/oauth2/callback
   ```

   ⚠️ **注意事項**:
   - リージョンを変更する場合は、`ap-northeast-1`の部分を使用するリージョンに変更してください
   - 例: `us-west-2`を使用する場合: `https://bedrock-agentcore.us-west-2.amazonaws.com/identities/oauth2/callback`
   - スペースや改行が入らないように注意
   - `https://`で始まり、`/callback`で終わることを確認

3. 「作成」をクリック

### 4.5 クライアントIDとシークレットを保存

作成が完了すると、以下の情報が表示されます:

```
クライアント ID: 123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com
クライアント シークレット: GOCSPX-abcdefghijklmnopqrstuvwxyz
```

⚠️ **重要**: この情報を安全な場所にコピーして保存してください。次のステップで使用します。

- ダイアログの「ダウンロード」ボタンをクリックしてJSON形式でダウンロードすることもできます
- 「OK」をクリック

### 4.6 後から認証情報を確認する方法

1. 「認証情報」画面で作成したOAuth 2.0 クライアントIDをクリック
2. クライアントIDとシークレットが表示されます
3. クライアントシークレットは「表示」アイコンをクリックすると確認できます

---

## Step 5: AWS AgentCore Identity OAuth2 Credential Providerの作成

Google Cloudでの設定が完了したら、次はAWS側でCredential Providerを作成します。

### 5.1 AWS CLIを使用して作成

保存したクライアントIDとシークレットを使用して、以下のコマンドを実行:

```bash
aws bedrock-agentcore-control create-oauth2-credential-provider \
  --region ap-northeast-1 \
  --name "google-calendar-provider" \
  --credential-provider-vendor "GoogleOauth2" \
  --oauth2-provider-config-input '{
      "googleOauth2ProviderConfig": {
        "clientId": "YOUR_CLIENT_ID_HERE",
        "clientSecret": "YOUR_CLIENT_SECRET_HERE"
      }
    }'
```

**置き換える値**:
- `YOUR_CLIENT_ID_HERE`: Step 4.5でコピーしたクライアントID
- `YOUR_CLIENT_SECRET_HERE`: Step 4.5でコピーしたクライアントシークレット
- `--region`: 使用するAWSリージョン（Google Cloud Console設定のリダイレクトURIと一致させる）

### 5.2 作成の確認

```bash
aws bedrock-agentcore-control list-oauth2-credential-providers \
  --region ap-northeast-1
```

作成した`google-calendar-provider`が表示されることを確認してください。

---

## Step 6: 初回のOAuth認証フロー

Lambda関数やエージェントを初めて実行すると、OAuth認証フローが開始されます。

### 6.1 認証フローの流れ

1. Lambda関数が`@requires_access_token`デコレーターを実行
2. AgentCore Identityが認証URLを生成
3. そのURLにブラウザでアクセス
4. Googleのログイン画面が表示される
5. テストユーザーとして登録したGoogleアカウントでログイン
6. カレンダーへのアクセス許可を求める画面が表示される
7. 「許可」をクリック
8. リダイレクトURIに戻り、認証完了
9. アクセストークンがToken Vaultに保存される

### 6.2 「このアプリは確認されていません」の対処

テスト段階では以下の警告が表示されることがあります:

```
このアプリは確認されていません
このアプリはGoogleにより確認されていません
```

**対処方法**:
1. 「詳細」リンクをクリック
2. 「LINE Agent Secretary（安全ではないページ）に移動」をクリック
   - これはあなた自身が作成したアプリなので、安全です
3. 権限を許可

### 6.3 本番環境への移行（オプション）

個人使用の場合はテストユーザーのままで問題ありませんが、他のユーザーにも使用させたい場合:

1. OAuth同意画面で「アプリを公開」をクリック
2. Googleの審査プロセスを経る必要があります（数週間かかる場合があります）

---

## トラブルシューティング

### エラー: "redirect_uri_mismatch"

**原因**: リダイレクトURIが一致していません

**解決方法**:
1. Google Cloud Console → 認証情報 → 使用しているOAuth 2.0 クライアントID
2. 「承認済みのリダイレクト URI」を確認
3. AgentCore Identityが使用するURIと完全に一致しているか確認
4. リージョンが正しいか確認

### エラー: "access_denied"

**原因**: テストユーザーとして登録されていないアカウントでログインしようとしている

**解決方法**:
1. OAuth同意画面 → テストユーザー
2. 使用するGoogleアカウントを追加

### エラー: "invalid_scope"

**原因**: 必要なスコープが設定されていません

**解決方法**:
1. OAuth同意画面 → スコープを編集
2. `https://www.googleapis.com/auth/calendar`が追加されているか確認

### Calendar APIが有効化されていない

**エラーメッセージ**: "Google Calendar API has not been used in project..."

**解決方法**:
1. APIライブラリでGoogle Calendar APIを検索
2. 「有効にする」をクリック

---

## 参考情報

- [Google OAuth 2.0 ドキュメント](https://developers.google.com/identity/protocols/oauth2)
- [Google Calendar API リファレンス](https://developers.google.com/calendar/api)
- [AWS AgentCore Identity ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)

---

## チェックリスト

設定が完了したら、以下を確認してください:

- [ ] Google Cloudプロジェクトを作成
- [ ] Google Calendar APIを有効化
- [ ] OAuth同意画面を設定
- [ ] テストユーザーを追加
- [ ] OAuth 2.0 クライアントIDを作成
- [ ] リダイレクトURI（`https://bedrock-agentcore.{region}.amazonaws.com/identities/oauth2/callback`）を設定
- [ ] クライアントIDとシークレットを保存
- [ ] AWS AgentCore Identity OAuth2 Credential Providerを作成
- [ ] Credential Providerの作成を確認

すべて完了したら、Lambda関数のテストまたはエージェントのデプロイに進んでください！
