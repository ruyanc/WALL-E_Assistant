"""WALL-E 桌面宠物 启动入口。

双击或在命令行运行此文件即可启动应用。
"""

import sys
from pathlib import Path

# 确保可以从源码目录直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent))

from walle.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
