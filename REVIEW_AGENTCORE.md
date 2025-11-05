# AgentCore実装レビュー結果

AWS公式ドキュメントと現在の実装を照らし合わせてレビューしました。

## ✅ 正しい実装

### 1. Lambda Handler (functions/calendar/operations.py)

**Context objectの使用方法**
```python
# 現在の実装 (operations.py:264)
original_tool_name = context.client_context.custom['bedrockAgentCoreToolName']
```

✅ **公式ドキュメントと一致**
- [AWS Docs: Lambda function input format](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html)
- Context objectには`bedrockAgentCoreToolName`が含まれる
- `context.client_context.custom`経由でアクセスする

**Tool name formatの処理**
```python
# 現在の実装 (operations.py:262-265)
delimiter = "___"  # 3つのアンダースコア
tool_name = original_tool_name[original_tool_name.index(delimiter) + len(delimiter):]
```

✅ **公式ドキュメントと一致**
- Tool name format: `{target_name}___{tool_name}` (3つのアンダースコア)
- 公式サンプルコードと同じ処理方法

**Event objectの使用方法**
```python
# 現在の実装 (operations.py:278)
params = event
```

✅ **公式ドキュメントと一致**
- Event objectは直接ツールの入力パラメータ
- 追加の処理は不要

### 2. @requires_access_token デコレーター (agent/server.py)

```python
# 現在の実装 (server.py:307-337)
@requires_access_token(
    provider_name="google-calendar-provider",
    scopes=["https://www.googleapis.com/auth/calendar"],
    auth_flow="USER_FEDERATION",
    on_auth_url=lambda url: logger.info(f"Authorization required: {url}"),
    force_authentication=False,
)
async def execute_calendar_tool_with_oauth(
    *,
    access_token: str,
    tool_name: str,
    tool_input: dict[str, Any],
    user_id: str = "default-user"
) -> dict[str, Any]:
    tool_input_with_token = {**tool_input, "access_token": access_token}
    return execute_calendar_tool(tool_name, tool_input_with_token, user_id)
```

✅ **公式ドキュメントと一致**
- [AWS Docs: Integrate with Google Drive using OAuth2](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-getting-started-google.html)
- デコレーターのパラメータが正しい
- `access_token=""`で呼び出し、デコレーターが自動注入する方式

### 3. MCP tools/call リクエスト (agent/server.py)

```python
# 現在の実装 (server.py:237-247)
mcp_tool_name = f"{GATEWAY_TARGET_NAME}___{tool_name}"

mcp_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": mcp_tool_name,
        "arguments": tool_input
    }
}
```

✅ **公式ドキュメントと一致**
- [AWS Docs: Call a tool in a AgentCore gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-call.html)
- JSON-RPC 2.0形式
- `method: "tools/call"`
- Tool name: `{target_name}___{tool_name}` (3つのアンダースコア)

### 4. Gateway認証方法 (agent/server.py:256-270)

**現在の実装: IAM SigV4認証**
```python
# SigV4署名を追加
credentials = boto3.Session().get_credentials()
SigV4Auth(credentials, "bedrock-agentcore", AWS_REGION).add_auth(request)
```

✅ **公式ドキュメントと一致**
- [AWS Docs: Create a gateway (IAM authorization)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-create-api.html)
- Gatewayの設定: `authorizerType: AWS_IAM`, `authorizerConfiguration: null`
- AWS公式ドキュメントの記載: "With IAM authorization, you don't need an authorizer configuration."
- IAMベースの認証はSigV4署名を使用 ✅

**確認結果**:
```bash
$ aws bedrock-agentcore-control get-gateway \
  --gateway-identifier line-agent-calendar-gateway-slylv9xoxe \
  --region ap-northeast-1

{
  "authorizerType": "AWS_IAM",
  "authorizerConfiguration": null  # IAM認証の場合はnullが正しい
}
```

## ⚠️ 要確認事項

### 1. MCPレスポンスの解析 (agent/server.py:290-298)

**現在の実装**:
```python
if "result" in result and "content" in result["result"]:
    content = result["result"]["content"]
    if isinstance(content, list) and len(content) > 0:
        text_content = content[0].get("text", "")
        try:
            return json.loads(text_content)
        except:
            return {"success": True, "result": text_content}
```

📌 **確認が必要**:
- MCP仕様でレスポンスの`content`が配列形式か確認
- `content[0].text`が正しい構造か確認
- Lambda関数が返すJSON形式がこの構造に合っているか確認

**推奨アクション**:
実際のGatewayレスポンスをログで確認し、構造が想定通りか検証してください。

## ❌ 潜在的な問題

### デバッグprint文の残留 (functions/calendar/operations.py)

```python
# operations.py:257-266
print(f"[DEBUG] Received event: {json.dumps(event, default=str)}", file=sys.stdout, flush=True)
print(f"[DEBUG] Context custom: ...", file=sys.stdout, flush=True)
print(f"[DEBUG] Detected tool name: {tool_name}", file=sys.stdout, flush=True)
print(f"[ERROR] Failed to extract tool name from context: {e}", file=sys.stdout, flush=True)
print(f"[ERROR] access_token not found in params", file=sys.stdout, flush=True)
```

**問題**:
- 本番環境で不要なログ出力
- Pythonの`logging`モジュールを使用すべき

**推奨修正**:
```python
import logging
logger = logging.getLogger(__name__)

logger.debug(f"Received event: {json.dumps(event, default=str)}")
logger.debug(f"Context custom: ...")
logger.debug(f"Detected tool name: {tool_name}")
logger.error(f"Failed to extract tool name from context: {e}")
logger.error(f"access_token not found in params")
```

## 📝 ドキュメント整合性

### CLAUDE.md の更新が必要

以下の記載は削除済みのファイルを参照しています（すでに対応済み✅）:
- ~~`config.py`: Configuration management~~ → 削除済み
- ~~`common/utils.py`: Shared utilities~~ → 削除済み

## まとめ

### 実装品質: 95/100

**良い点** (95点):
- Lambda handlerの実装は公式ドキュメントと完全に一致 ✅
- `@requires_access_token`デコレーターの使い方が正しい ✅
- MCP tools/callリクエストの構造が正しい ✅
- Tool name formatの処理が正しい ✅
- **Gateway認証方法（IAM SigV4）が正しく実装されている ✅** (確認済み)

**改善点** (-5点):
1. デバッグprint文をloggingモジュールに置き換える (-5点)

**次のアクション** (オプショナル):
1. デバッグprint文をloggingモジュールに置き換え（本番環境でのログ管理の改善）
2. 実際のGatewayレスポンスをログで確認してMCP解析ロジックを検証（動作確認済みなら不要）
