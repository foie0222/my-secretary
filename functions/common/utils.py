"""
共通ユーティリティ関数
"""

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def parse_datetime_expression(expression: str, timezone: str = "Asia/Tokyo") -> datetime:
    """
    自然言語の日時表現をdatetimeオブジェクトに変換する

    Args:
        expression: 日時表現（例: "明日", "来週の火曜日", "2024-03-15 14:00"）
        timezone: タイムゾーン

    Returns:
        datetime: パースされた日時

    Note:
        これは簡易版の実装です。実際にはより高度な自然言語処理が必要です。
        エージェントが解釈した日時を受け取ることを前提としています。
    """
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)

    # ISO形式のパース
    try:
        return datetime.fromisoformat(expression)
    except ValueError:
        pass

    # 相対的な表現のパース（簡易版）
    expression_lower = expression.lower()

    if "今日" in expression or "today" in expression_lower:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "明日" in expression or "tomorrow" in expression_lower:
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif "来週" in expression or "next week" in expression_lower:
        return (now + timedelta(weeks=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # デフォルトは現在時刻
    return now


def format_datetime_for_display(dt: datetime, timezone: str = "Asia/Tokyo") -> str:
    """
    datetimeオブジェクトを表示用の文字列に変換する

    Args:
        dt: datetime オブジェクト
        timezone: タイムゾーン

    Returns:
        str: フォーマットされた日時文字列
    """
    tz = ZoneInfo(timezone)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)

    # 曜日の日本語表記
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    weekday = weekdays[dt.weekday()]

    return dt.strftime(f"%Y年%m月%d日({weekday}) %H:%M")


def build_lambda_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """
    Lambda関数の標準的なレスポンスを構築する

    Args:
        status_code: HTTPステータスコード
        body: レスポンスボディ

    Returns:
        dict: Lambda レスポンス
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def build_success_response(data: Any, message: str | None = None) -> dict[str, Any]:
    """
    成功レスポンスを構築する

    Args:
        data: レスポンスデータ
        message: メッセージ（オプション）

    Returns:
        dict: Lambda レスポンス
    """
    body = {"success": True, "data": data}
    if message:
        body["message"] = message

    return build_lambda_response(200, body)


def build_error_response(error: str, status_code: int = 400) -> dict[str, Any]:
    """
    エラーレスポンスを構築する

    Args:
        error: エラーメッセージ
        status_code: HTTPステータスコード

    Returns:
        dict: Lambda レスポンス
    """
    body = {"success": False, "error": error}
    return build_lambda_response(status_code, body)


def extract_event_parameter(event: dict[str, Any], param_name: str) -> Any:
    """
    Lambda イベントからパラメータを抽出する

    Args:
        event: Lambda イベント
        param_name: パラメータ名

    Returns:
        Any: パラメータの値

    Raises:
        ValueError: パラメータが見つからない場合
    """
    # ボディからパラメータを取得
    if "body" in event:
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        if param_name in body:
            return body[param_name]

    # クエリパラメータから取得
    if "queryStringParameters" in event and event["queryStringParameters"]:
        if param_name in event["queryStringParameters"]:
            return event["queryStringParameters"][param_name]

    raise ValueError(f"必須パラメータ '{param_name}' が見つかりません")
