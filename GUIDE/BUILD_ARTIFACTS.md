# 构建缓存与版本库说明

本文说明 WALL-E 项目中**哪些文件纳入 Git 追踪**、**哪些是中间产物可删**，以及如何用 `clean_build_artifacts.bat` 一键清理。

---

## 设计原则

| 纳入版本库 | 不纳入版本库（本地可再生） |
| --- | --- |
| 源码（`walle/`、`mobile/*.py`、`scripts/`） | `build/`（PyInstaller / WiX / DMG 中间目录） |
| 配置与打包定义（`*.spec`、`installer/`、`buildozer.spec`） | `__pycache__/`、`*.pyc`、`.pytest_cache/` 等 |
| 依赖清单（`requirements*.txt`） | `.venv/`、`mobile/.venv-android/` |
| 文档与 `GUIDE/` | `tools/wix/`（首次构建时自动下载） |
| 动画等资源（`walle/assets/`） | `assets/walle.ico`、`mobile/assets/fonts/` 等**脚本生成**资源 |
| **分发安装包**（见下表） | `mobile/.buildozer/`、`mobile/bin/*.apk`、`usr/` |

完整规则见项目根目录 [`.gitignore`](../.gitignore)。

---

## `dist/` 目录策略

`dist/` 默认**全部忽略**，仅**白名单**保留可分发的安装文件：

| 文件 | 平台 | 是否追踪 |
| --- | --- | --- |
| `WALL-E.exe` | Windows 便携版 | ✅ |
| `WALL-E.msi` | Windows 安装包 | ✅ |
| `WALL-E.dmg` | macOS 磁盘镜像 | ✅ |
| `WALL-E-*.dmg` | 带版本号 DMG | ✅ |
| `WALL-E.app` | macOS 应用包（打 DMG 的中间产物） | ❌ |
| `WALL-E-build-temp.msi` 等临时文件 | 构建残留 | ❌ |

---

## 一键清理：`clean_build_artifacts.bat`

项目根目录运行：

```bat
clean_build_artifacts.bat          REM 结束时暂停
clean_build_artifacts.bat silent   REM 静默（适合脚本/CI）
```

**会删除：**

- `build/`、`tools/wix/`、`usr/`
- `mobile/.buildozer/`、`mobile/bin/`、`mobile/walle/`（打包前复制的 sync 副本）
- `mobile/.venv-android/`、`mobile/.gradle/`
- 生成的图标与字体（`assets/walle.ico`、`mobile/assets/icon.png` 等）
- 全项目 `__pycache__/`、`*.pyc`、`*.egg-info`（跳过 `.git`、`.venv`、`.buildozer`）

**会保留：**

- `dist/WALL-E.exe`、`dist/WALL-E.msi`、`dist/WALL-E.dmg`、`dist/WALL-E-*.dmg`
- 全部源码与 `.venv`（开发虚拟环境不删）

清理后重新构建：

```bat
build.bat                    REM Windows 桌面端
mobile\BUILD_ANDROID.md      REM Android（WSL / buildozer）
```

---

## 常见中间目录说明

| 路径 | 内容 | 可否删除 |
| --- | --- | --- |
| `build/` | PyInstaller 解包目录、WiX `.wixobj`、`dmg-staging` | ✅ 随时可删 |
| `dist/WALL-E.app` | macOS 应用包，用于封装 DMG | ✅ 可删（保留 `.dmg` 即可分发） |
| `tools/wix/` | WiX 3.14 工具链缓存 | ✅ 可删（下次 `build_msi.bat` 会再下载） |
| `mobile/.buildozer/` | Android SDK/NDK、python-for-android 编译缓存 | ✅ **可完全删除**（见下节） |
| `mobile/bin/` | 已生成的 `*.apk` | ✅ 可删（需重新打包 APK） |
| `mobile/walle/` | `prepare_sync.py` 复制的同步模块 | ✅ 可删（打包前会再生成） |
| `.venv/` | 桌面开发虚拟环境 | ⚠️ 一般不删；用 `requirements-dev.txt` 可重建 |

---

## `mobile/.buildozer/` 详解

这是 **Buildozer 打 Android APK 的本地构建缓存**，不是源码，也不是应用运行数据。

典型内容包括：

- 下载的 Android SDK / NDK
- Python-for-Android 交叉编译树（Kivy、依赖库的 `.so` / `.o`）
- Gradle 中间产物

**可以完全删除。** 删除后不影响桌面端与移动端源码；仅下次打 APK 时需重新下载与编译（耗时显著增加）。

### 删除方式

**Windows（路径过长时可能删不干净）：**

```bat
clean_build_artifacts.bat
```

**WSL（推荐，可彻底删除）：**

```bash
rm -rf /mnt/c/Users/你的用户名/Desktop/WALL-E/mobile/.buildozer
```

---

## 相关文档

| 文档 | 说明 |
| --- | --- |
| [操作手册.md](../操作手册.md) | 桌面版用户与开发者说明 |
| [USER_GUIDE.md](../USER_GUIDE.md) | 英文用户指南 |
| [BUILD_MAC.md](../BUILD_MAC.md) | macOS DMG 打包 |
| [mobile/BUILD_ANDROID.md](../mobile/BUILD_ANDROID.md) | Android APK 打包 |
| [mobile/操作手册.md](../mobile/操作手册.md) | 手机版说明 |

---

*最后更新：2026-06-15*
