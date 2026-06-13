# WALL-E macOS 打包说明

在 **macOS** 上生成分发用的 `.app` 与 `.dmg` 安装镜像（当前版本 **v1.1.0**，含中英文界面）。

用户使用说明：[操作手册.md](操作手册.md)（中文）· [USER_GUIDE.md](USER_GUIDE.md)（English）

## 环境要求

- macOS 11+（Apple Silicon 或 Intel 均可）
- Python 3.10+
- Xcode 命令行工具（`xcode-select --install`）

## 一键打包

```bash
cd /path/to/WALL-E
chmod +x build_mac.sh scripts/build_dmg.sh
./build_mac.sh
```

产物：

| 文件 | 说明 |
| --- | --- |
| `dist/WALL-E.app` | macOS 应用程序包 |
| `dist/WALL-E.dmg` | 磁盘镜像，内含 app 与「应用程序」文件夹快捷方式 |

用户双击 DMG，将 WALL-E 拖入 Applications 即可安装。

## 首次运行提示

未签名的应用可能提示「无法验证开发者」。可在 **系统设置 → 隐私与安全性** 中点击「仍要打开」，或右键 app 选择「打开」。

正式对外分发建议配置 Apple Developer 证书并对 app / dmg 进行 `codesign` 与公证（notarization）。

## 与 Windows 版差异

| 项目 | macOS | Windows |
| --- | --- | --- |
| 安装包 | DMG | exe / MSI |
| 数据目录 | `~/Library/Application Support/WALL-E` | `%APPDATA%\WALL-E` |
| 键鼠联动 | 暂不支持 | 支持 |
| 界面语言 | 控制台「番茄钟」页可切换中/英 | 同左 |

## 仅重新生成 DMG

若已有 `dist/WALL-E.app`：

```bash
bash scripts/build_dmg.sh
```
