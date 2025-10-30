"""
Google Calendar操作Lambda関数

AgentCore Identityを使用してGoogle Calendar APIにアクセスし、
4つの基本操作（確認・追加・変更・削除）を提供する
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any

from bedrock_agentcore.services.identity import IdentityClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Google Calendar APIのスコープ
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Workload Identity名（環境変数から取得、デフォルトは"line-agent-secretary"）
WORKLOAD_NAME = os.environ.get("WORKLOAD_NAME", "line-agent-secretary")

# Credential Provider名（環境変数から取得）
CREDENTIAL_PROVIDER_NAME = os.environ.get("CREDENTIAL_PROVIDER_NAME", "google-calendar-provider")

# Identity Client（グローバルに初期化）
identity_client = IdentityClient(os.environ.get("AWS_REGION", "ap-northeast-1"))


async def get_google_access_token(user_id: str = "default-user") -> str:
    """
    AgentCore Identityから Google OAuth トークンを取得する

    Args:
        user_id: ユーザー識別子（LINEユーザーIDなど）

    Returns:
        Google OAuth access token
    """
    # Step 1: Workload Access Tokenを取得
    workload_access_token = identity_client.get_workload_access_token(
        workload_name=WORKLOAD_NAME,
        user_id=user_id
    )

    # Step 2: Workload Access Tokenを使ってOAuth tokenを取得
    token_response = await identity_client.get_token(
        credential_provider_name=CREDENTIAL_PROVIDER_NAME,
        workload_access_token=workload_access_token
    )

    return token_response["access_token"]


async def list_calendar_events(
    *,
    user_id: str = "default-user",
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    カレンダーの予定を取得する

    Args:
        user_id: ユーザー識別子（LINEユーザーIDなど）
        time_min: 取得開始日時（ISO 8601形式）
        time_max: 取得終了日時（ISO 8601形式）
        max_results: 最大取得件数

    Returns:
        予定のリスト
    """
    try:
        # AgentCore Identityから Google OAuth トークンを取得
        access_token = await get_google_access_token(user_id)

        # 認証情報を構築
        creds = Credentials(token=access_token, scopes=SCOPES)

        # Calendar APIサービスを構築
        service = build("calendar", "v3", credentials=creds)

        # イベントを取得
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        return {
            "success": True,
            "events": events,
            "count": len(events),
        }

    except Exception as error:
        return {
            "success": False,
            "error": f"Error: {str(error)}",
        }


async def create_calendar_event(
    *,
    user_id: str = "default-user",
    summary: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    """
    カレンダーに予定を作成する

    Args:
        user_id: ユーザー識別子（LINEユーザーIDなど）
        summary: 予定のタイトル
        start_time: 開始日時（ISO 8601形式）
        end_time: 終了日時（ISO 8601形式）
        description: 予定の説明（オプション）
        location: 場所（オプション）

    Returns:
        作成された予定の情報
    """
    try:
        # AgentCore Identityから Google OAuth トークンを取得
        access_token = await get_google_access_token(user_id)

        # 認証情報を構築
        creds = Credentials(token=access_token, scopes=SCOPES)

        # Calendar APIサービスを構築
        service = build("calendar", "v3", credentials=creds)

        # イベントデータを構築
        event = {
            "summary": summary,
            "start": {"dateTime": start_time, "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": end_time, "timeZone": "Asia/Tokyo"},
        }

        if description:
            event["description"] = description
        if location:
            event["location"] = location

        # イベントを作成
        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        return {
            "success": True,
            "event": created_event,
            "event_id": created_event["id"],
        }

    except HttpError as error:
        return {
            "success": False,
            "error": f"Google Calendar API error: {error}",
        }


async def update_calendar_event(
    *,
    user_id: str = "default-user",
    event_id: str,
    summary: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    """
    カレンダーの予定を更新する

    Args:
        user_id: ユーザー識別子（LINEユーザーIDなど）
        event_id: 更新する予定のID
        summary: 予定のタイトル（オプション）
        start_time: 開始日時（ISO 8601形式、オプション）
        end_time: 終了日時（ISO 8601形式、オプション）
        description: 予定の説明（オプション）
        location: 場所（オプション）

    Returns:
        更新された予定の情報
    """
    try:
        # AgentCore Identityから Google OAuth トークンを取得
        access_token = await get_google_access_token(user_id)

        # 認証情報を構築
        creds = Credentials(token=access_token, scopes=SCOPES)

        # Calendar APIサービスを構築
        service = build("calendar", "v3", credentials=creds)

        # 既存のイベントを取得
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        # 更新するフィールドを設定
        if summary is not None:
            event["summary"] = summary
        if start_time is not None:
            event["start"] = {"dateTime": start_time, "timeZone": "Asia/Tokyo"}
        if end_time is not None:
            event["end"] = {"dateTime": end_time, "timeZone": "Asia/Tokyo"}
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location

        # イベントを更新
        updated_event = (
            service.events()
            .update(calendarId="primary", eventId=event_id, body=event)
            .execute()
        )

        return {
            "success": True,
            "event": updated_event,
        }

    except HttpError as error:
        return {
            "success": False,
            "error": f"Google Calendar API error: {error}",
        }


async def delete_calendar_event(
    *,
    user_id: str = "default-user",
    event_id: str,
) -> dict[str, Any]:
    """
    カレンダーの予定を削除する

    Args:
        user_id: ユーザー識別子（LINEユーザーIDなど）
        event_id: 削除する予定のID

    Returns:
        削除結果
    """
    try:
        # AgentCore Identityから Google OAuth トークンを取得
        access_token = await get_google_access_token(user_id)

        # 認証情報を構築
        creds = Credentials(token=access_token, scopes=SCOPES)

        # Calendar APIサービスを構築
        service = build("calendar", "v3", credentials=creds)

        # イベントを削除
        service.events().delete(calendarId="primary", eventId=event_id).execute()

        return {
            "success": True,
            "message": f"Event {event_id} deleted successfully",
        }

    except HttpError as error:
        return {
            "success": False,
            "error": f"Google Calendar API error: {error}",
        }


# Lambda ハンドラー
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda関数のエントリーポイント

    AgentCore Gatewayから呼び出される際のハンドラー

    Args:
        event: Lambda イベント（operation と parameters を含む）
        context: Lambda コンテキスト

    Returns:
        操作結果
    """
    operation = event.get("operation")
    params = event.get("parameters", {})

    # 非同期関数を同期的に実行
    user_id = params.get("user_id", "default-user")

    if operation == "list":
        result = asyncio.run(
            list_calendar_events(
                user_id=user_id,
                time_min=params.get("time_min"),
                time_max=params.get("time_max"),
                max_results=params.get("max_results", 10),
            )
        )
    elif operation == "create":
        result = asyncio.run(
            create_calendar_event(
                user_id=user_id,
                summary=params.get("summary"),
                start_time=params.get("start_time"),
                end_time=params.get("end_time"),
                description=params.get("description"),
                location=params.get("location"),
            )
        )
    elif operation == "update":
        result = asyncio.run(
            update_calendar_event(
                user_id=user_id,
                event_id=params.get("event_id"),
                summary=params.get("summary"),
                start_time=params.get("start_time"),
                end_time=params.get("end_time"),
                description=params.get("description"),
                location=params.get("location"),
            )
        )
    elif operation == "delete":
        result = asyncio.run(
            delete_calendar_event(
                user_id=user_id,
                event_id=params.get("event_id"),
            )
        )
    else:
        result = {
            "success": False,
            "error": f"Unknown operation: {operation}",
        }

    return {
        "statusCode": 200 if result.get("success") else 400,
        "body": json.dumps(result),
    }
