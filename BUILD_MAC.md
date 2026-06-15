# WALL-E macOS 打包说明

在 **macOS** 上生成分发用的 `.app` 与 `.dmg` 安装镜像（版本号读取 `walle/__version__`，当前 **v1.2.0**，含中英文界面与 CloudBase 同步）。

用户使用说明：[操作手册.md](操作手册.md)（中文）· [USER_GUIDE.md](USER_GUIDE.md)（English）

## 环境要求

- macOS 11+（Apple Silicon 或 Intel 均可）
- Python 3.10+
- Xcode 命令行工具（`xcode-select --install`）

## 一键打包（Mac 本机）

```bash
cd /path/to/WALL-E
chmod +x build_mac.sh scripts/build_dmg.sh
./build_mac.sh
```

产物：

| 文件 | 说明 |
| --- | --- |
| `dist/WALL-E.app` | macOS 应用程序包 |
| `dist/WALL-E.dmg` | 磁盘镜像（固定名，便于文档引用） |
| `dist/WALL-E-{版本}.dmg` | 带版本号的磁盘镜像（如 `WALL-E-1.2.0.dmg`） |

DMG 内含 app、「应用程序」快捷方式，以及操作手册 / CloudBase 配置说明。

用户双击 DMG，将 WALL-E 拖入 Applications 即可安装。

## 无 Mac 时（Windows 用户）

DMG **无法在 Windows 上直接生成**（依赖 `hhiutil` 与 macOS 目标 `.app`）。

**方式 A — 运行 `build_mac.bat`**

在 Windows 项目根目录双击或运行 `build_mac.bat`，按提示操作。

**方式 B — GitHub Actions 云端构建**

仓库已配置 workflow `build-macos-dmg.yml`：

```bash
gh workflow run build-macos-dmg.yml
```

或在 GitHub 网页 **Actions → build-macos-dmg → Run workflow**。完成后在 Artifacts 下载 `WALL-E-macOS-dmg`（内含 DMG 文件）。

推送 `main` 分支且改动涉及 `walle/` 等路径时也会自动构建。

## 首次运行提示

未签名的应用可能提示「无法验证开发者」。可在 **系统设置 → 隐私与安全性** 中点击「仍要打开」，或右键 app 选择「打开」。

正式对外分发建议配置 Apple Developer 证书并对 app / dmg 进行 `codesign` 与公证（notarization）。

## 与 Windows 版差异

| 项目 | macOS | Windows |
| --- | --- | --- |
| 安装包 | DMG | exe / MSI |
| 数据目录 | `~/Library/Application Support/WALL-E` | `%APPDATA%\WALL-E` |
| 键鼠联动 | 暂不支持 | 支持 |
| CloudBase 同步 | ✅ 与 Windows 相同（授权码 + 手机号） | ✅ Windows / macOS / Android |
| 任务派发 | ✅ 四子页、分区、信封/旗子徽章 | 同左（Android 为通知跳转） |
| 退出程序 | 保存本地数据后快速退出（不长时间阻塞同步） | 同左 |
| 工作台名称 | 同 Windows | 中文：**瓦力桌面助手**；英文：**WALL-E Assistant** |
| 界面语言 | 番茄钟页可切换中/英 | 同左 |

## 仅重新生成 DMG

若已有 `dist/WALL-E.app`：

```bash
bash scripts/build_dmg.sh
```

## 构建缓存与版本库

| 路径 | 说明 | Git 追踪 |
| --- | --- | --- |
| `dist/WALL-E.dmg`、`dist/WALL-E-*.dmg` | 可分发的安装镜像 | ✅ |
| `dist/WALL-E.app` | 打 DMG 用的应用包（中间产物） | ❌ |
| `build/dmg-staging/` | DMG 封装临时目录 | ❌ |

Windows 上一键清理（保留 `dist` 中的 exe/msi/dmg）：

```bat
clean_build_artifacts.bat
```

详见 [GUIDE/BUILD_ARTIFACTS.md](GUIDE/BUILD_ARTIFACTS.md)。
