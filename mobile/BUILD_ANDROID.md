# WALL-E 安卓版打包说明

桌面版（`PySide6` + Windows / macOS）**无法直接**打成 APK，本目录是独立的 **Kivy 移动端** 实现，复用 `walle/sync/` 与同一套像素动画资源。

## 功能范围（v1.2）

| 功能 | 安卓版 |
| --- | --- |
| 待办清单 | ✅ 四子页（个人待办 / 派给我的 / 我派出 / 归档）；分区、时间、优先级修改 |
| **同步状态** | ✅ 待办页显示同步状态与重试 |
| 记事本 | ✅ 多条备忘 |
| 定时提醒 | ✅ 每天/工作日等；后台前台 Service + 系统通知 |
| 番茄钟 | ✅ 可配置工作/休息/轮数；wall-clock 持久化，锁屏/后台继续 |
| **CloudBase 同步** | ✅ 授权码 + 手机号登录；与 Windows / macOS 同步 |
| **跨账号派发** | ✅ 与桌面一致；派发说明、通知跳转子页 |
| **暂停自动同步** | ✅ 账号页切换 |
| 瓦力桌面动画 / 信封旗子 | ❌ 无悬浮宠物；派发用系统通知 |
| 桌面悬浮 / 系统托盘 | ❌ Android 不支持 |
| 界面语言 | 中文为主（桌面支持中/英切换） |

## 1. 本地调试（Windows）

```powershell
cd mobile
..\.venv\Scripts\python.exe prepare_assets.py
..\.venv\Scripts\pip.exe install kivy plyer
..\.venv\Scripts\python.exe main.py
```

## 2. 打包 APK（需 Linux 或 WSL2）

Buildozer **不支持在原生 Windows 上直接打包**，请使用 WSL2 Ubuntu。

> Ubuntu 24.04+ 禁止用系统 `pip` 装包（PEP 668），**必须在虚拟环境里**安装 buildozer。

### 一次性准备

```bash
# 在 WSL 内（必须装 python3-full，否则 venv 里可能没有 pip）
sudo apt update
sudo apt install -y git zip unzip curl rsync openjdk-17-jdk autoconf libtool \
  pkg-config zlib1g-dev libffi-dev libssl-dev python3-venv python3-full

cd /mnt/c/Users/你的用户名/Desktop/WALL-E/mobile
python3 prepare_sync.py
chmod +x setup_wsl.sh build_wsl_native.sh
./setup_wsl.sh
```

### 打包（推荐：WSL 原生目录，更快更小）

项目在 `/mnt/c/...` 上编译很慢。推荐 rsync 到 WSL 的 ext4 目录再构建：

```bash
cd /mnt/c/Users/你的用户名/Desktop/WALL-E/mobile
./build_wsl_native.sh
```

脚本会同步源码到 `~/WALL-E-mobile`（排除 `.buildozer`、`bin`、`.venv-android`），在 ext4 上执行 buildozer，最后把 APK 拷回 `mobile/bin/`。

当前仅打包 **arm64-v8a** 单架构（主流 64 位手机），APK 更小、编译更快。

### 打包（本目录直接构建）

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

或始终用虚拟环境 Python 显式调用：

```bash
.venv-android/bin/python -m pip install -U pip wheel
.venv-android/bin/python -m pip install "cython<3.1" buildozer
.venv-android/bin/python prepare_assets.py
.venv-android/bin/python -m buildozer -v android debug
```

成功后 APK 位于：

```
mobile/bin/walle-1.1.0-arm64-v8a-debug.apk
```

传到手机安装（需允许「未知来源」）。首次启动会请求**通知权限**；有提醒或番茄钟运行时会保持**前台 Service**，以便后台/锁屏可靠触发。

## 3. 安装到手机

1. 将 `*.apk` 复制到手机
2. 文件管理器中点击安装
3. 或使用 `adb install bin/*.apk`

## 4. 与桌面版数据（CloudBase 同步）

填写相同 **授权码** 并用 **同一手机号** 登录后，待办/记事/提醒/番茄钟设置可与 **Windows / macOS** 合并；跨账号任务派发与桌面一致（接受不写入个人待办）。

未登录时数据仅保存在应用私有目录。

用户说明：[mobile/操作手册.md](操作手册.md) · 桌面说明：[操作手册.md](../操作手册.md)

## 5. Gradle 下载失败（SSL / dl.google.com）

若在最后一步 `gradlew assembleDebug` 报错，例如 `SSLHandshakeException` 或无法访问 `dl.google.com`，说明 **Gradle 拉取 Google Maven 依赖失败**（与 NDK 下载问题相同）。此时 C/Python 编译通常已完成，只差 APK 打包。

**修复：** 配置阿里云镜像后重跑即可（`setup_wsl.sh` 已自动安装）：

```bash
mkdir -p ~/.gradle/init.d
cp /mnt/c/Users/ruyan/Desktop/WALL-E/mobile/gradle/china-mirror.gradle ~/.gradle/init.d/
python -m buildozer -v android debug
```

## 6. 发布版签名

调试 APK 仅供测试。上架应用商店需自行配置 keystore 并执行：

```bash
buildozer android release
```

## 7. 构建缓存（`.buildozer`）与清理

`mobile/.buildozer/` 存放 Buildozer 下载的 **SDK/NDK** 与 **python-for-android 编译缓存**（体积可达数 GB），不是源码，**可随时完全删除**。

| 操作 | 说明 |
| --- | --- |
| 删除影响 | 不影响源码与已装到手机上的应用；仅下次打包需重新下载/编译 |
| Windows 清理 | 项目根目录运行 `clean_build_artifacts.bat` |
| 彻底删除（推荐） | WSL：`rm -rf /mnt/c/.../WALL-E/mobile/.buildozer` |

`mobile/bin/*.apk` 为调试/发布产物，已在 `.gitignore` 中忽略；清理脚本会删除 `bin/`，需重新打包后才有 APK。

`build_wsl_native.sh` 同步到 `~/WALL-E-mobile` 时会自动排除 `.buildozer`、`bin`、`.venv-android`。

完整说明见 [GUIDE/BUILD_ARTIFACTS.md](../GUIDE/BUILD_ARTIFACTS.md)。
