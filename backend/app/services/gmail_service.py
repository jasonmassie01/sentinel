"""
Gmail Integration — OAuth2 connection and email fetching.

Handles authentication, polling, and raw message retrieval.
Parsing is handled by receipt_parser.py.
"""

import json
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

import httpx

from app.config import settings

CREDENTIALS_PATH = settings.data_dir / "gmail_credentials.json"
TOKEN_PATH = settings.data_dir / "gmail_token.json"

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Search queries for financial emails
RECEIPT_QUERY = "subject:(order confirmation OR receipt OR purchase OR your order) -is:draft"
BILL_QUERY = "subject:(bill OR statement OR invoice OR payment due) -is:draft"
SUBSCRIPTION_QUERY = "subject:(subscription OR renewal OR recurring OR membership) -is:draft"


@dataclass
class GmailCredentials:
    client_id: str
    client_secret: str
    redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob"


@dataclass
class GmailToken:
    access_token: str
    refresh_token: str
    expires_at: float


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    body_html: str
    body_text: str
    snippet: str


def is_configured() -> bool:
    """Check if Gmail credentials are set up."""
    return CREDENTIALS_PATH.exists()


def is_authenticated() -> bool:
    """Check if we have a valid token."""
    return TOKEN_PATH.exists()


def get_auth_url() -> Optional[str]:
    """Generate OAuth2 authorization URL."""
    if not CREDENTIALS_PATH.exists():
        return None

    creds = _load_credentials()
    if not creds:
        return None

    params = {
        "client_id": creds.client_id,
        "redirect_uri": creds.redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
    }
    from urllib.parse import urlencode
    query = urlencode(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for tokens."""
    creds = _load_credentials()
    if not creds:
        raise ValueError("Gmail credentials not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "redirect_uri": creds.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    token = GmailToken(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.now().timestamp() + data.get("expires_in", 3600),
    )
    _save_token(token)
    return {"status": "authenticated"}


async def _get_valid_token() -> str:
    """Get a valid access token, refreshing if needed."""
    token = _load_token()
    if not token:
        raise ValueError("Not authenticated — run OAuth flow first")

    if datetime.now().timestamp() >= token.expires_at - 60:
        token = await _refresh_token(token)

    return token.access_token


async def _refresh_token(token: GmailToken) -> GmailToken:
    """Refresh an expired access token."""
    creds = _load_credentials()
    if not creds:
        raise ValueError("Gmail credentials not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "refresh_token": token.refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    new_token = GmailToken(
        access_token=data["access_token"],
        refresh_token=token.refresh_token,
        expires_at=datetime.now().timestamp() + data.get("expires_in", 3600),
    )
    _save_token(new_token)
    return new_token


async def search_messages(query: str, max_results: int = 50) -> list[str]:
    """Search Gmail and return message IDs."""
    access_token = await _get_valid_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/users/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": query, "maxResults": max_results},
        )
        resp.raise_for_status()
        data = resp.json()

    messages = data.get("messages", [])
    return [m["id"] for m in messages]


async def get_message(message_id: str) -> EmailMessage:
    """Fetch a full email message by ID."""
    access_token = await _get_valid_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/users/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"format": "full"},
        )
        resp.raise_for_status()
        data = resp.json()

    headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}

    body_html = ""
    body_text = ""
    _extract_body(data.get("payload", {}), body_html_parts := [], body_text_parts := [])
    body_html = "".join(body_html_parts)
    body_text = "".join(body_text_parts)

    return EmailMessage(
        id=data["id"],
        thread_id=data.get("threadId", ""),
        subject=headers.get("subject", ""),
        sender=headers.get("from", ""),
        date=headers.get("date", ""),
        body_html=body_html,
        body_text=body_text,
        snippet=data.get("snippet", ""),
    )


def _extract_body(payload: dict, html_parts: list, text_parts: list):
    """Recursively extract body content from MIME parts."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/html":
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            html_parts.append(base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace"))
    elif mime_type == "text/plain":
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            text_parts.append(base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace"))

    for part in payload.get("parts", []):
        _extract_body(part, html_parts, text_parts)


async def fetch_receipts(max_results: int = 50) -> list[EmailMessage]:
    """Fetch recent receipt/order confirmation emails."""
    message_ids = await search_messages(RECEIPT_QUERY, max_results)
    messages = []
    for mid in message_ids:
        try:
            msg = await get_message(mid)
            messages.append(msg)
        except Exception:
            continue
    return messages


async def fetch_bills(max_results: int = 50) -> list[EmailMessage]:
    """Fetch recent bill/statement emails."""
    message_ids = await search_messages(BILL_QUERY, max_results)
    messages = []
    for mid in message_ids:
        try:
            msg = await get_message(mid)
            messages.append(msg)
        except Exception:
            continue
    return messages


def save_credentials(client_id: str, client_secret: str):
    """Save Gmail OAuth2 credentials."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    creds = {"client_id": client_id, "client_secret": client_secret}
    CREDENTIALS_PATH.write_text(json.dumps(creds))


def _load_credentials() -> Optional[GmailCredentials]:
    if not CREDENTIALS_PATH.exists():
        return None
    data = json.loads(CREDENTIALS_PATH.read_text())
    return GmailCredentials(
        client_id=data["client_id"],
        client_secret=data["client_secret"],
    )


def _save_token(token: GmailToken):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_at": token.expires_at,
    }
    TOKEN_PATH.write_text(json.dumps(data))


def _load_token() -> Optional[GmailToken]:
    if not TOKEN_PATH.exists():
        return None
    data = json.loads(TOKEN_PATH.read_text())
    return GmailToken(**data)
