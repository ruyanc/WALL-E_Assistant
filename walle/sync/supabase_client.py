"""Supabase REST 客户端（Auth + sync_records 表）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .auth import AuthManager, AuthSession
from .backend import SyncBackendConfig, SyncBackendError


class SupabaseClient:
    TABLE = "sync_records"

    def __init__(self, config: SyncBackendConfig, auth: AuthManager) -> None:
        self.config = config
        self.auth = auth
        self.url = config.supabase_url
        self.anon_key = config.supabase_anon_key

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict | list | None = None,
        token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        if not self.url or not self.anon_key:
            raise SyncBackendError("backend_not_configured")
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SyncBackendError(detail or f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SyncBackendError(str(exc.reason)) from exc

    def login(self, email: str, password: str) -> AuthSession:
        data = self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            body={"email": email, "password": password},
        )
        return self.auth.set_session_from_supabase(data, email)

    def refresh_session(self) -> AuthSession:
        session = self.auth.session
        if session is None or not session.refresh_token:
            raise SyncBackendError("not_logged_in")
        data = self._request(
            "POST",
            "/auth/v1/token?grant_type=refresh_token",
            body={"refresh_token": session.refresh_token},
        )
        self.auth.update_tokens(
            access_token=str(data["access_token"]),
            refresh_token=str(data.get("refresh_token", "")) or None,
            expires_in=float(data.get("expires_in", 3600)),
        )
        return self.auth.session  # type: ignore[return-value]

    def ensure_token(self) -> str:
        session = self.auth.session
        if session is None:
            raise SyncBackendError("not_logged_in")
        if session.is_expired:
            session = self.refresh_session()
        return session.access_token

    def fetch_changes(self, since: float) -> list[dict[str, Any]]:
        token = self.ensure_token()
        since_ms = int(since * 1000)
        query = (
            f"/rest/v1/{self.TABLE}?updated_at=gt.{since_ms}"
            f"&select=record_id,collection,payload,updated_at,deleted"
            f"&order=updated_at.asc"
        )
        rows = self._request("GET", query, token=token)
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized.append(
                {
                    "record_id": str(row["record_id"]),
                    "collection": str(row["collection"]),
                    "payload": row.get("payload") or {},
                    "updated_at": float(row["updated_at"]) / 1000.0,
                    "deleted": bool(row.get("deleted", False)),
                }
            )
        return normalized

    def upsert_records(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        token = self.ensure_token()
        session = self.auth.session
        assert session is not None
        payload = []
        for row in rows:
            payload.append(
                {
                    "user_id": session.user_id,
                    "record_id": row["record_id"],
                    "collection": row["collection"],
                    "payload": row["payload"],
                    "updated_at": int(row["updated_at"] * 1000),
                    "deleted": bool(row.get("deleted", False)),
                }
            )
        self._request(
            "POST",
            f"/rest/v1/{self.TABLE}",
            body=payload,
            token=token,
            extra_headers={"Prefer": "resolution=merge-duplicates"},
        )
