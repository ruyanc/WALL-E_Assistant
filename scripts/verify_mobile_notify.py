"""验证移动端通知与横幅能力（桌面可运行）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MOBILE = Path(__file__).resolve().parents[1] / "mobile"
sys.path.insert(0, str(MOBILE))

from notify_util import notify, verify_notification_capabilities  # noqa: E402


def main() -> int:
    caps = verify_notification_capabilities()
    print(json.dumps(caps, ensure_ascii=False, indent=2))
    result = notify("WALL-E", "通知能力自检：应用内横幅应出现在窗口顶部", urgent=True)
    print("notify result:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
