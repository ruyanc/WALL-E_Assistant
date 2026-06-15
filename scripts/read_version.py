"""读取 walle.__version__（供打包脚本使用）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "walle" / "__init__.py").read_text(encoding="utf-8")
match = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", text)
if not match:
    raise SystemExit("无法在 walle/__init__.py 中解析 __version__")
print(match.group(1))
if __name__ == "__main__":
    sys.exit(0)
