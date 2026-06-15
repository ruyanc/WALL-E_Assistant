"""HTTPS 请求工具（PyInstaller 打包后需 certifi 根证书，尤其 macOS .app）。"""

from __future__ import annotations

import os
import ssl
import sys
import urllib.request
from pathlib import Path
from typing import IO

_ssl_context: ssl.SSLContext | None = None


def _certifi_cafile() -> str | None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "certifi" / "cacert.pem"  # type: ignore[attr-defined]
        if bundled.is_file():
            return str(bundled)
    try:
        import certifi

        path = certifi.where()
        return path if Path(path).is_file() else None
    except ImportError:
        return None


def install_ssl_certificates() -> None:
    """应用启动时调用，为 urllib 配置 CA 证书链。"""
    global _ssl_context
    cafile = _certifi_cafile()
    if cafile:
        os.environ.setdefault("SSL_CERT_FILE", cafile)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
        _ssl_context = ssl.create_default_context(cafile=cafile)
    else:
        _ssl_context = ssl.create_default_context()


def ssl_context() -> ssl.SSLContext:
    if _ssl_context is None:
        install_ssl_certificates()
    return _ssl_context or ssl.create_default_context()


def urlopen(req: urllib.request.Request, *, timeout: float = 25) -> IO[bytes]:
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
