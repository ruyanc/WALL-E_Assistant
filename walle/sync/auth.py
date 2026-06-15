"""登录会话持久化。"""



from __future__ import annotations



import json

import time

from dataclasses import dataclass

from pathlib import Path

from typing import Any



from pathlib import Path
from typing import Any


def _default_auth_path() -> Path:
    from ..config import AUTH_PATH

    return AUTH_PATH





@dataclass

class AuthSession:

    user_id: str

    account: str

    access_token: str

    refresh_token: str

    expires_at: float



    @property

    def is_expired(self) -> bool:

        return time.time() >= self.expires_at - 60



    @property

    def phone(self) -> str:

        return self.account



    @property

    def email(self) -> str:

        return self.account





class AuthManager:

    def __init__(self, auth_path: Path | None = None) -> None:

        self._auth_path = auth_path or _default_auth_path()

        self._session: AuthSession | None = None

        self.load()



    @property

    def session(self) -> AuthSession | None:

        return self._session



    @property

    def is_logged_in(self) -> bool:

        return self._session is not None



    @property

    def phone(self) -> str | None:

        return self._session.account if self._session else None



    @property

    def email(self) -> str | None:

        return self.phone



    def load(self) -> None:

        self._session = None

        if not self._auth_path.exists():

            return

        try:

            raw = json.loads(self._auth_path.read_text(encoding="utf-8-sig"))

            account = str(raw.get("account") or raw.get("email") or raw.get("phone") or "")

            self._session = AuthSession(

                user_id=str(raw["user_id"]),

                account=account,

                access_token=str(raw["access_token"]),

                refresh_token=str(raw.get("refresh_token", "")),

                expires_at=float(raw.get("expires_at", 0)),

            )

        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):

            self._session = None



    def save(self) -> None:

        if self._session is None:

            if self._auth_path.exists():

                try:

                    self._auth_path.unlink()

                except OSError:

                    pass

            return

        payload = {

            "user_id": self._session.user_id,

            "account": self._session.account,

            "access_token": self._session.access_token,

            "refresh_token": self._session.refresh_token,

            "expires_at": self._session.expires_at,

        }

        try:

            self._auth_path.parent.mkdir(parents=True, exist_ok=True)

            self._auth_path.write_text(

                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",

                encoding="utf-8",

            )

        except OSError:

            pass



    def set_session(

        self,

        *,

        user_id: str,

        account: str,

        access_token: str,

        refresh_token: str,

        expires_in: float,

    ) -> AuthSession:

        session = AuthSession(

            user_id=user_id,

            account=account,

            access_token=access_token,

            refresh_token=refresh_token,

            expires_at=time.time() + expires_in,

        )

        self._session = session

        self.save()

        return session



    def set_session_from_supabase(self, data: dict[str, Any], account: str) -> AuthSession:

        user = data.get("user") or {}

        return self.set_session(

            user_id=str(user.get("id", "")),

            account=account,

            access_token=str(data.get("access_token", "")),

            refresh_token=str(data.get("refresh_token", "")),

            expires_in=float(data.get("expires_in", 3600)),

        )



    def update_tokens(

        self,

        *,

        access_token: str,

        refresh_token: str | None = None,

        expires_in: float = 3600,

    ) -> None:

        if self._session is None:

            return

        self._session.access_token = access_token

        if refresh_token:

            self._session.refresh_token = refresh_token

        self._session.expires_at = time.time() + expires_in

        self.save()



    def logout(self) -> None:

        self._session = None

        self.save()


