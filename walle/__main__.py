"""支持 `python -m walle` 运行。"""

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
