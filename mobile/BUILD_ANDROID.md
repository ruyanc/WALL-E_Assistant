# WALL-E 安卓版打包说明

桌面版（`PySide6` + Windows）**无法直接**打成 APK，本目录是独立的 **Kivy 移动端** 实现，复用同一套像素动画资源。

## 功能范围（v1）

| 功能 | 安卓版 |
| --- | --- |
| 瓦力动画 | ✅ idle / look / talk / happy |
| 待办清单 | ✅ 增删、完成、三级优先级 |
| 番茄钟 | ✅ 50/10 分钟简易计时 |
| 定时提醒 | ❌ 后续版本 |
| 桌面悬浮 / 系统托盘 | ❌ Android 不支持同等能力 |
| 键鼠联动 | ❌ |

## 1. 本地调试（Windows）

```powershell
cd mobile
..\.venv\Scripts\python.exe prepare_assets.py
..\.venv\Scripts\pip.exe install kivy
..\.venv\Scripts\python.exe main.py
```

## 2. 打包 APK（需 Linux 或 WSL2）

Buildozer **不支持在原生 Windows 上直接打包**，请使用 WSL2 Ubuntu。

> Ubuntu 24.04+ 禁止用系统 `pip` 装包（PEP 668），**必须在虚拟环境里**安装 buildozer。

### 一次性准备

```bash
# 在 WSL 内（必须装 python3-full，否则 venv 里可能没有 pip）
sudo apt update
sudo apt install -y git zip unzip curl openjdk-17-jdk autoconf libtool \
  pkg-config zlib1g-dev libffi-dev libssl-dev python3-venv python3-full

cd /mnt/c/Users/你的用户名/Desktop/WALL-E/mobile
chmod +x setup_wsl.sh
./setup_wsl.sh
```

### 打包

```bash
cd /mnt/c/Users/你的用户名/Desktop/WALL-E/mobile
source .venv-android/bin/activate
python -m buildozer -v android debug
```

### 仍报 `externally-managed-environment`？

说明当前用的仍是**系统 pip**，不是虚拟环境里的 pip。请检查：

```bash
which pip          # 应显示 .../mobile/.venv-android/bin/pip
which python       # 应显示 .../mobile/.venv-android/bin/python
ls .venv-android/bin/pip   # 若不存在，说明 venv 未装好 pip
```

**修复（推荐直接重跑脚本）：**

```bash
cd /mnt/c/Users/ruyan/Desktop/WALL-E/mobile
rm -rf .venv-android
./setup_wsl.sh
```

或始终用虚拟环境 Python 显式调用（不依赖 `pip` 命令）：

```bash
.venv-android/bin/python -m pip install -U pip wheel
.venv-android/bin/python -m pip install "cython<3.1" buildozer
.venv-android/bin/python prepare_assets.py
.venv-android/bin/python -m buildozer -v android debug
```

成功后 APK 位于：

```
mobile/bin/walle-1.0.0-arm64-v8a-debug.apk
```

传到手机安装（需允许「未知来源」）。

## 3. 安装到手机

1. 将 `*.apk` 复制到手机
2. 文件管理器中点击安装
3. 或使用 `adb install bin/*.apk`

## 4. 与桌面版数据

安卓版数据保存在应用私有目录，**不与 Windows 版 `%APPDATA%\WALL-E` 自动同步**。

## 5. 发布版签名

调试 APK 仅供测试。上架应用商店需自行配置 keystore 并执行：

```bash
buildozer android release
```
