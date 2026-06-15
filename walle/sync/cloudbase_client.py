"""腾讯云 CloudBase HTTP 客户端（Auth + 文档库）。"""

from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..http_util import urlopen as http_urlopen
from .auth import AuthManager, AuthSession
from .backend import SyncBackendConfig, SyncBackendError
from .phone import normalize_phone, phone_local_digits, phone_lookup_variants

SYNC_COLLECTION = "sync_records"
USER_PROFILES = "user_profiles"
TASK_ASSIGNMENTS = "task_assignments"
DB_PREFIX = "/v1/database/instances/(default)/databases/(default)/collections"


class CloudBaseClient:
    def __init__(
        self,
        config: SyncBackendConfig,
        auth: AuthManager,
        *,
        sync_meta_path=None,
    ) -> None:
        if sync_meta_path is not None:
            self._sync_meta_path = sync_meta_path
        else:
            from ..config import SYNC_META_PATH

            self._sync_meta_path = SYNC_META_PATH
        self.config = config
        self.auth = auth
        self.env_id = config.cloudbase_env_id.strip()
        self.api_base = (
            f"https://{self.env_id}.api.tcloudbasegateway.com" if self.env_id else ""
        )
        self._device_id = self._load_device_id()

    def _require_config(self) -> None:
        if not self.env_id or not self.api_base:
            raise SyncBackendError("backend_not_configured")

    def _collection_base(self, collection: str) -> str:
        return f"{self.api_base}{DB_PREFIX}/{collection}"

    @property
    def db_base(self) -> str:
        return self._collection_base(SYNC_COLLECTION)

    def _load_device_id(self) -> str:
        if self._sync_meta_path.exists():
            try:
                raw = json.loads(self._sync_meta_path.read_text(encoding="utf-8-sig"))
                device_id = str(raw.get("device_id", "")).strip()
                if device_id:
                    return device_id
            except (json.JSONDecodeError, OSError, TypeError):
                pass
        device_id = str(uuid.uuid4())
        self._save_device_id(device_id)
        return device_id

    def _save_device_id(self, device_id: str) -> None:
        payload: dict[str, Any] = {"device_id": device_id}
        if self._sync_meta_path.exists():
            try:
                payload.update(json.loads(self._sync_meta_path.read_text(encoding="utf-8-sig")))
            except (json.JSONDecodeError, OSError):
                pass
        payload["device_id"] = device_id
        try:
            self._sync_meta_path.parent.mkdir(parents=True, exist_ok=True)
            self._sync_meta_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: dict | list | None = None,
        token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers["x-device-id"] = self._device_id
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                with http_urlopen(req, timeout=25) as resp:
                    raw = resp.read().decode("utf-8")
                    if not raw:
                        return None
                    parsed = json.loads(raw)
                    self._raise_gateway_error(parsed)
                    return parsed
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise SyncBackendError(self._format_error(detail, exc.code)) from exc
            except urllib.error.URLError as exc:
                last_err = exc
            except OSError as exc:
                last_err = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        if isinstance(last_err, urllib.error.URLError):
            raise SyncBackendError(str(last_err.reason)) from last_err
        raise SyncBackendError(str(last_err)) from last_err

    @staticmethod
    def _raise_gateway_error(data: Any) -> None:
        if not isinstance(data, dict):
            return
        response = data.get("Response")
        if not isinstance(response, dict):
            return
        error = response.get("Error")
        if not isinstance(error, dict):
            return
        code = str(error.get("Code", "") or "").strip()
        message = str(error.get("Message", "") or "").strip()
        if code or message:
            raise SyncBackendError(message or code)

    @staticmethod
    def _format_error(detail: str, code: int) -> str:
        try:
            obj = json.loads(detail)
            if isinstance(obj, dict):
                return str(obj.get("message") or obj.get("error") or obj.get("code") or detail)
        except json.JSONDecodeError:
            pass
        return detail or f"HTTP {code}"

    @staticmethod
    def doc_id(prefix: str, record_id: str) -> str:
        return f"{prefix}_{record_id}"

    @staticmethod
    def _scoped_doc_id(user_id: str, prefix: str, record_id: str) -> str:
        """按用户隔离的文档 ID，避免不同账号的同名记录（如 settings_global）互相覆盖。"""
        uid = str(user_id or "").strip()
        if uid:
            return f"{uid}_{prefix}_{record_id}"
        return f"{prefix}_{record_id}"

    def login(self, username: str, password: str) -> AuthSession:
        self._require_config()
        account = normalize_phone(username) or username.strip()
        if not account or not password:
            raise SyncBackendError("empty_credentials")
        data = self._request(
            "POST",
            f"{self.api_base}/auth/v1/signin",
            body={"username": account, "password": password},
        )
        return self._session_from_auth_response(data, account)

    def send_phone_verification(self, phone: str, *, target: str = "USER") -> str:
        """发送手机验证码，返回 verification_id。

        target: USER=登录（用户须已存在），ANY=注册（新用户）。
        """
        self._require_config()
        account = normalize_phone(phone)
        if not account:
            raise SyncBackendError("invalid_phone")
        data = self._request(
            "POST",
            f"{self.api_base}/auth/v1/verification",
            body={"phone_number": account, "target": target},
        )
        if not isinstance(data, dict):
            raise SyncBackendError("invalid_verification_response")
        verification_id = str(data.get("verification_id", "")).strip()
        if not verification_id:
            raise SyncBackendError("invalid_verification_response")
        return verification_id

    def verify_phone_code(self, verification_id: str, code: str) -> str:
        """校验验证码，返回 verification_token。"""
        self._require_config()
        code = code.strip()
        if not verification_id or not code:
            raise SyncBackendError("empty_verification")
        data = self._request(
            "POST",
            f"{self.api_base}/auth/v1/verification/verify",
            body={"verification_id": verification_id, "verification_code": code},
        )
        if not isinstance(data, dict):
            raise SyncBackendError("invalid_verification_response")
        token = str(data.get("verification_token", "")).strip()
        if not token:
            raise SyncBackendError("invalid_verification_code")
        return token

    def login_with_verification_token(self, verification_token: str, account: str) -> AuthSession:
        self._require_config()
        account = normalize_phone(account) or account.strip()
        if not verification_token or not account:
            raise SyncBackendError("empty_verification")
        data = self._request(
            "POST",
            f"{self.api_base}/auth/v1/signin",
            body={"verification_token": verification_token},
        )
        return self._session_from_auth_response(data, account)

    def signup(self, phone: str, password: str, verification_token: str) -> AuthSession:
        """手机号+验证码+密码注册新用户。"""
        self._require_config()
        account = normalize_phone(phone)
        if not account or not password or not verification_token:
            raise SyncBackendError("empty_credentials")
        data = self._request(
            "POST",
            f"{self.api_base}/auth/v1/signup",
            body={
                "phone_number": account,
                "verification_token": verification_token,
                "password": password,
            },
        )
        return self._session_from_auth_response(data, account)

    def _session_from_auth_response(self, data: Any, account: str) -> AuthSession:
        if not isinstance(data, dict):
            raise SyncBackendError("invalid_login_response")
        session = self.auth.set_session(
            user_id=str(data.get("sub", "")),
            account=account,
            access_token=str(data.get("access_token", "")),
            refresh_token=str(data.get("refresh_token", "")),
            expires_in=float(data.get("expires_in", 7200)),
        )
        self.upsert_user_profile(account)
        return session

    def refresh_session(self) -> AuthSession:
        session = self.auth.session
        if session is None or not session.refresh_token:
            raise SyncBackendError("not_logged_in")
        data = self._request(
            "POST",
            f"{self.api_base}/auth/v1/token",
            body={
                "grant_type": "refresh_token",
                "refresh_token": session.refresh_token,
            },
        )
        if not isinstance(data, dict):
            raise SyncBackendError("invalid_refresh_response")
        self.auth.update_tokens(
            access_token=str(data.get("access_token", "")),
            refresh_token=str(data.get("refresh_token", session.refresh_token)),
            expires_in=float(data.get("expires_in", 7200)),
        )
        refreshed = self.auth.session
        if refreshed is not None:
            self.upsert_user_profile(refreshed.account)
        return refreshed  # type: ignore[return-value]

    def ensure_token(self) -> str:
        session = self.auth.session
        if session is None:
            raise SyncBackendError("not_logged_in")
        if session.is_expired:
            session = self.refresh_session()
        return session.access_token

    def find_documents(
        self,
        collection: str,
        filter_obj: dict[str, Any],
        *,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """条件查询文档（GET ?query=…，非 documents:find）。"""
        self._require_config()
        token = self.ensure_token()
        query = json.dumps(filter_obj, separators=(",", ":"), ensure_ascii=False)
        qs = urllib.parse.urlencode(
            {"limit": str(max(1, min(limit, 1000))), "query": query}
        )
        url = f"{self._collection_base(collection)}/documents?{qs}"
        data = self._request("GET", url, token=token)
        return self._extract_documents(data)

    def _write_query(
        self,
        collection: str,
        doc_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """构造满足安全规则子集的 PATCH query（须含 user_id / assigner_id 等）。"""
        session = self.auth.session
        user_id = str(session.user_id).strip() if session else ""
        query: dict[str, Any] = {"_id": doc_id}
        if collection == TASK_ASSIGNMENTS:
            assigner_id = str(payload.get("assigner_id", "") or "").strip()
            assignee_id = str(payload.get("assignee_id", "") or "").strip()
            if assigner_id == user_id:
                query["assigner_id"] = user_id
            elif assignee_id == user_id:
                query["assignee_id"] = user_id
            elif assigner_id:
                query["assigner_id"] = assigner_id
            elif assignee_id:
                query["assignee_id"] = assignee_id
        else:
            owner_id = str(payload.get("user_id", "") or user_id).strip()
            if owner_id:
                query["user_id"] = owner_id
        return query

    def put_document(self, collection: str, doc_id: str, payload: dict[str, Any]) -> None:
        """写入或更新文档：PATCH（按 query 更新）失败则 POST 插入。"""
        self._require_config()
        token = self.ensure_token()
        doc_id = str(doc_id or "").strip()
        if not doc_id:
            raise SyncBackendError("empty_document_id")
        doc = dict(payload)
        doc["_id"] = doc_id
        url = f"{self._collection_base(collection)}/documents"
        query = self._write_query(collection, doc_id, doc)
        patch_result = self._request(
            "PATCH",
            url,
            body={"query": query, "data": doc},
            token=token,
        )
        matched = 0
        if isinstance(patch_result, dict):
            try:
                matched = int(patch_result.get("matched", 0) or 0)
            except (TypeError, ValueError):
                matched = 0
        if matched > 0:
            return
        self._request("POST", url, body={"data": [doc]}, token=token)

    def upsert_user_profile(self, phone: str) -> None:
        session = self.auth.session
        if session is None:
            return
        normalized = normalize_phone(phone) or normalize_phone(session.account)
        if not normalized:
            return
        local_digits = phone_local_digits(normalized)
        self.put_document(
            USER_PROFILES,
            session.user_id,
            {
                "user_id": session.user_id,
                "phone": normalized,
                "phone_digits": local_digits,
                "display_name": normalized,
                "updated_at": time.time(),
            },
        )

    def _query_auth_user(self, phone_number: str) -> dict[str, Any] | None:
        """通过 CloudBase Auth 按手机号查注册用户（不依赖 user_profiles 读权限）。"""
        token = self.ensure_token()
        qs = urllib.parse.urlencode({"phone_number": phone_number})
        url = f"{self.api_base}/auth/v1/user/query?{qs}"
        data = self._request("GET", url, token=token)
        if not isinstance(data, dict):
            return None
        items = data.get("data") or []
        if not isinstance(items, list) or not items:
            return None
        user = self._parse_document(items[0])
        user_id = str(user.get("sub") or user.get("user_id") or "").strip()
        if not user_id:
            return None
        return {
            "user_id": user_id,
            "phone": str(user.get("phone_number") or phone_number),
        }

    @staticmethod
    def _profile_user_id(row: dict[str, Any]) -> str:
        for key in ("user_id", "uid", "sub"):
            value = str(row.get(key, "") or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _profile_row_matches(row: dict[str, Any], variants: list[str], local_digits: str) -> bool:
        phone_value = str(row.get("phone", "") or "")
        row_digits = str(row.get("phone_digits", "") or phone_local_digits(phone_value))
        if local_digits and row_digits == local_digits:
            return True
        if phone_value in variants:
            return True
        if phone_value and normalize_phone(phone_value) in variants:
            return True
        return False

    def find_user_by_phone(self, phone: str) -> dict[str, Any] | None:
        """按手机号查找用户：Auth 查询优先，再查 user_profiles。"""
        variants = phone_lookup_variants(phone)
        if not variants:
            return None
        local_digits = phone_local_digits(phone)

        auth_candidates: list[str] = []
        seen_auth: set[str] = set()
        for variant in variants:
            candidate = normalize_phone(variant) or variant
            if candidate.startswith("+") and candidate not in seen_auth:
                seen_auth.add(candidate)
                auth_candidates.append(candidate)

        for candidate in auth_candidates:
            try:
                row = self._query_auth_user(candidate)
            except SyncBackendError:
                row = None
            if row:
                return row

        if local_digits:
            rows = self.find_documents(USER_PROFILES, {"phone_digits": local_digits}, limit=1)
            if rows:
                user_id = self._profile_user_id(rows[0])
                if user_id:
                    row = dict(rows[0])
                    row["user_id"] = user_id
                    return row

        for variant in variants:
            rows = self.find_documents(USER_PROFILES, {"phone": variant}, limit=1)
            if rows:
                user_id = self._profile_user_id(rows[0])
                if user_id:
                    row = dict(rows[0])
                    row["user_id"] = user_id
                    return row
        return None

    def fetch_assignment_changes(self, user_id: str, since: float) -> list[dict[str, Any]]:
        user_id = str(user_id or "").strip()
        if not user_id:
            return []
        merged: dict[str, dict[str, Any]] = {}
        for field in ("assigner_id", "assignee_id"):
            for doc in self.find_documents(TASK_ASSIGNMENTS, {field: user_id}, limit=1000):
                try:
                    updated_at = float(doc.get("updated_at", 0))
                except (TypeError, ValueError):
                    updated_at = 0.0
                if since > 0 and updated_at <= since:
                    continue
                aid = self._assignment_doc_id(doc)
                if aid:
                    merged[aid] = doc
        return list(merged.values())

    def upsert_assignment(self, payload: dict[str, Any]) -> None:
        assignment_id = str(payload["id"])
        body = dict(payload)
        body["id"] = assignment_id
        body.setdefault("assignment_id", assignment_id)
        self.put_document(TASK_ASSIGNMENTS, assignment_id, body)

    def fetch_changes(self, since: float) -> list[dict[str, Any]]:
        session = self.auth.session
        user_id = str(session.user_id).strip() if session else ""
        filter_obj: dict[str, Any] = {"user_id": user_id} if user_id else {}
        docs = self.find_documents(SYNC_COLLECTION, filter_obj, limit=1000)
        rows: list[dict[str, Any]] = []
        for doc in docs:
            if user_id:
                doc_user = str(doc.get("user_id", "") or "").strip()
                if doc_user and doc_user != user_id:
                    continue
            row = self._normalize_sync_row(doc)
            if not row:
                continue
            if since > 0 and row["updated_at"] <= since:
                continue
            rows.append(row)
        return rows

    def upsert_records(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        session = self.auth.session
        user_id = str(session.user_id).strip() if session else ""
        for row in rows:
            collection = str(row["collection"])
            record_id = str(row["record_id"])
            doc_id = self._scoped_doc_id(user_id, collection, record_id)
            payload = {
                "user_id": user_id,
                "record_id": record_id,
                "collection": collection,
                "payload": row.get("payload") or {},
                "updated_at": float(row["updated_at"]),
                "deleted": bool(row.get("deleted", False)),
            }
            self.put_document(SYNC_COLLECTION, doc_id, payload)

    def _extract_documents(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [self._parse_document(item) for item in data if item is not None]
        if not isinstance(data, dict):
            return []
        for key in ("data", "documents", "list", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [self._parse_document(item) for item in value if item is not None]
        if any(k in data for k in ("record_id", "collection", "id", "assignment_id")):
            return [self._parse_document(data)]
        return []

    @staticmethod
    def _decode_ejson(value: Any) -> Any:
        if isinstance(value, list):
            return [CloudBaseClient._decode_ejson(item) for item in value]
        if not isinstance(value, dict):
            return value
        if len(value) == 1:
            if "$numberInt" in value:
                try:
                    return int(value["$numberInt"])
                except (TypeError, ValueError):
                    return value["$numberInt"]
            if "$numberLong" in value:
                try:
                    return int(value["$numberLong"])
                except (TypeError, ValueError):
                    return value["$numberLong"]
            if "$numberDouble" in value:
                try:
                    return float(value["$numberDouble"])
                except (TypeError, ValueError):
                    return value["$numberDouble"]
            if "$oid" in value:
                return str(value["$oid"])
            if "$date" in value:
                return CloudBaseClient._decode_ejson(value["$date"])
        return {key: CloudBaseClient._decode_ejson(val) for key, val in value.items()}

    @staticmethod
    def _parse_document(item: Any) -> dict[str, Any]:
        if isinstance(item, str):
            try:
                parsed = json.loads(item)
                item = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        if not isinstance(item, dict):
            return {}
        doc = CloudBaseClient._decode_ejson(item)
        if not isinstance(doc, dict):
            return {}
        doc = dict(doc)
        if not doc.get("id") and not doc.get("assignment_id"):
            doc_id = doc.get("_id")
            if doc_id is not None and str(doc_id).strip():
                doc["id"] = str(doc_id).strip()
        return doc

    @staticmethod
    def _assignment_doc_id(doc: dict[str, Any]) -> str:
        for key in ("id", "assignment_id", "_id"):
            value = str(doc.get(key, "") or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _normalize_sync_row(doc: dict[str, Any]) -> dict[str, Any] | None:
        record_id = doc.get("record_id")
        collection = doc.get("collection")
        if not record_id or not collection:
            return None
        try:
            updated_at = float(doc.get("updated_at", 0))
        except (TypeError, ValueError):
            updated_at = 0.0
        return {
            "record_id": str(record_id),
            "collection": str(collection),
            "payload": doc.get("payload") or {},
            "updated_at": updated_at,
            "deleted": bool(doc.get("deleted", False)),
        }
