# 🤖 WALL-E Desktop Pet · User Guide

> A desktop companion inspired by **WALL-E** from *WALL·E* (**Windows / macOS**).
> Pixel-art animations: blinking, looking around, waving, cheering, and more.
> Manage **to-dos**, **notes**, and **reminders**, plus a **Pomodoro timer** for focus and breaks.
> Switch the UI between **简体中文** and **English**.

> 中文版说明：[操作手册.md](操作手册.md)

---

## Table of Contents

1. [Features](#1-features)
2. [Quick Start](#2-quick-start)
3. [Install & Uninstall](#3-install--uninstall)
4. [Desktop Pet Controls](#4-desktop-pet-controls)
5. [To-Do List & Priority](#5-to-do-list--priority)
6. [Notes](#6-notes)
7. [Reminders](#7-reminders)
8. [Pomodoro & Language](#8-pomodoro--language)
9. [Full-Screen Break](#9-full-screen-break)
10. [Keyboard & Mouse Activity](#10-keyboard--mouse-activity)
11. [System Tray Menu](#11-system-tray-menu)
12. [Settings & Data Location](#12-settings--data-location)
13. [Run from Source / Rebuild](#13-run-from-source--rebuild)
14. [FAQ](#14-faq)
15. [Other Platforms](#15-other-platforms)

---

## 1. Features

| Feature | Description |
| --- | --- |
| 🐾 Desktop pet | Pixel WALL-E floating on desktop; transparent, draggable, resizable, always on top |
| 👀 Eye backing | White backing inside the lenses, scales with WALL-E |
| 💡 Priority bulbs | Red / blue / green bulbs above the head for pending to-dos; click to view |
| 📋 To-do list | Card layout, three priority levels, square checkbox to complete |
| 📝 Notes | Multiple short notes in the control panel; auto-save on edit |
| ⏰ Reminders | Once / daily / weekdays / weekly; bubble notification at due time |
| ⏱️ Pomodoro | Default 50 min work / 10 min break / 3 cycles; customizable |
| 🔔 Break warning | Bubble **2 minutes** before each break |
| 🛌 Full-screen break | WALL-E fills the screen with countdown and tips |
| ⌨️🖱️ Activity link | Different animations when typing, moving, or clicking (Windows only) |
| 🔔 System tray | Stays in tray; closing the panel does not quit the app |
| 🌐 UI language | Switch 简体中文 / English in the control panel |
| 📦 Windows installer | Portable exe; MSI or `install.bat` for per-user install |
| 🍎 macOS installer | Run `build_mac.sh` on Mac to build DMG; drag into Applications |

---

## 2. Quick Start

### Option A: Run directly (simplest)

1. Double-click `dist\WALL-E.exe` (or the desktop shortcut after install).
2. WALL-E appears at the **bottom-right** of the desktop; an icon also shows in the system tray.
3. **Click** WALL-E or the tray icon → open the **Control Panel**.

### Option B: Install on Windows (recommended for daily use)

1. Run `build.bat` to produce `dist\WALL-E.exe` and `dist\WALL-E.msi` (if not built yet).
2. Install using either:
   - `install.bat` — **quick install** (copy exe) or **MSI wizard**; optional startup; copies user guides to the install folder;
   - or double-click `dist\WALL-E.msi` and follow the wizard.
3. Launch **WALL-E Assistant** from the desktop shortcut.

### Option B2: Install on macOS (DMG)

1. On a Mac, run `./build_mac.sh` (see [BUILD_MAC.md](BUILD_MAC.md)).
2. Share or open `dist/WALL-E.dmg`.
3. Drag **WALL-E** into **Applications**.
4. If macOS blocks an unsigned app: right-click the app → **Open**, or allow it under **Privacy & Security**.

> macOS data lives in `~/Library/Application Support/WALL-E`. It does **not** sync with Windows automatically.

### Option C: Run from source (developers)

```powershell
.\.venv\Scripts\python.exe run.py
```

See [Section 13](#13-run-from-source--rebuild).

---

## 3. Install & Uninstall

### Install (Windows)

| Step | Action |
| --- | --- |
| 1 | Run `build.bat` (developers) |
| 2 | Run `install.bat` (optional MSI wizard), or double-click `dist\WALL-E.msi` |
| 3 | App installs to `%LOCALAPPDATA%\Programs\WALL-E` |
| 4 | Desktop shortcut created; quick install includes `USER_GUIDE.md` and `操作手册.md`; optional startup |

### Install (macOS DMG)

| Step | Action |
| --- | --- |
| 1 | Run `./build_mac.sh` on Mac |
| 2 | Open `dist/WALL-E.dmg`, drag the app to Applications |
| 3 | Launch WALL-E from Launchpad or Applications |

### Uninstall (Windows)

Run `uninstall.bat`:

- Closes running WALL-E
- Removes the install folder and shortcuts
- Removes startup entry

> 💡 Uninstall does **not** delete to-dos, notes, reminders, or settings (stored under `%APPDATA%\WALL-E`). Delete that folder manually for a full reset.

### Upgrade

```powershell
.\build.bat          # rebuild exe + msi
.\install.bat        # overwrite install (or copy dist\WALL-E.exe manually)
```

---

## 4. Desktop Pet Controls

| Action | Effect |
| --- | --- |
| **Drag with left button** | Move (position is remembered) |
| **Drag bottom-right corner** | Resize WALL-E |
| **Ctrl + scroll wheel** | Resize WALL-E |
| **Single click** | Open control panel |
| **Double click** | Open control panel |
| **Right click** | Menu (panel / Pomodoro / break / zoom / quit) |
| **Click priority bulb** | Bubble shows task and priority |
| **Speech bubble** | Focus start, break warning, reminders, etc. |

Size can also be adjusted on the **Pomodoro** tab slider; saved as `pet_size` in `settings.json`.

---

## 5. To-Do List & Priority

### Control Panel · 📋 To-Do

Four tabs: **To-Do**, **Notes**, **Reminders**, **Pomodoro**.

**Add a task**

- Type in the input box, choose **High / Medium / Low** from the dropdown, press Enter or **Add**.

**Card layout**

- Left: **square checkbox** + **priority color bar** (red / blue / green)
- Center: task text (wraps for long text)
- Bottom-right: **priority dropdown** (editable anytime)

**Complete & delete**

- Click the square → checkmark, strikethrough, dimmed text
- **Double-click** a card → delete
- Footer: **Clear completed** / **Clear all**

**First-run samples**

If `todos.json` does not exist, three sample tasks are created (wording follows UI language):

| Task (EN) | Priority |
| --- | --- |
| Meeting | High (red) |
| Weekly report | Medium (blue) |
| Pick up package | Low (green) |

| 任务（中文） | 优先级 |
| --- | --- |
| 开会 | 高级（红） |
| 交周报 | 中级（蓝） |
| 取快递 | 低级（绿） |

### Priority bulbs

When there are **pending** tasks, bulbs appear above WALL-E’s head:

| Color | Priority |
| --- | --- |
| 🔴 Red | High |
| 🔵 Blue | Medium (default) |
| 🟢 Green | Low |

Click a bulb → bubble shows e.g. `[High] task text` (label varies by priority).

---

## 6. Notes

Control Panel → **📝 Notes**:

- Add **multiple** short notes, each with its own text box.
- Type above and press **Add note** or Enter.
- Edits **auto-save** after ~0.5 s; or tap **Save all**.
- **×** on the right deletes one note.
- Data: `%APPDATA%\WALL-E\notes.json` (legacy `notes.txt` migrates on first launch).

---

## 7. Reminders

### Add in control panel

Open **⏰ Reminders** and fill the form:

| Field | Description |
| --- | --- |
| **Text** | e.g. “Drink water”, “Rest” |
| **Time** | HH:mm (keyboard input; no spin arrows) |
| **Repeat** | Daily / weekdays / Mon–Sun / once (pick date) |
| **Date** | Shown for “once”; calendar popup |

Press **Add reminder** or Enter in the text field. Select an item below and **Delete selected** to remove.

**First-run samples**

| Reminder (EN) | Time | Repeat |
| --- | --- | --- |
| Drink water | 10:00 | Daily |
| Rest | 22:00 | Daily |

### When due

- WALL-E **speech bubble** with the reminder text.
- **System notification** in the tray area.
- Optional sound (same toggle as break sound on the Pomodoro tab).

---

## 8. Pomodoro & Language

Control Panel → **⏱️ Pomodoro**:

### Defaults

| Setting | Default | Range |
| --- | --- | --- |
| Work | **50** min | 1–180 |
| Break | **10** min | 1–120 |
| Cycles | **3** | 1–12 |
| Break sound | On | On / off |

Flow: **50 min work → 10 min break**, repeat **3** times.

Work / break / cycles accept **direct keyboard input** (spin buttons hidden).

### 2-minute break warning

When **2 minutes** remain in a work session, WALL-E shows a bubble and plays the talk animation.

### Buttons

| Button | Action |
| --- | --- |
| ▶ Start | Begin full cycle from round 1 |
| ☕ Break | Start break immediately |
| ■ Stop | Stop timer; return to idle |

Use the **WALL-E size** slider on the same page (synced with desktop resize).

### UI language

Find **Language** on the Pomodoro tab:

| Option | Description |
| --- | --- |
| 简体中文 | Chinese UI (default) |
| English | English UI |

Changes apply immediately: tabs, tray menu, bubbles, full-screen break text, etc. Saved in `settings.json` as `language` (`zh` / `en`).

> Your to-do, reminder, and note **content is not translated**—only UI chrome and system messages.

---

## 9. Full-Screen Break

1. **Break starts**: WALL-E enlarges full-screen, semi-transparent overlay, countdown, relaxation tips.
2. **Break ends**: Overlay closes; next work round or all cycles done.
3. **End early**: Click **I'm rested — end early** or press **Esc**.
4. **Start break early**: Control panel / right-click menu / tray **Rest Now**.

---

## 10. Keyboard & Mouse Activity

WALL-E reacts to input (**Windows only**, global monitoring). Paused during full-screen break:

| Your action | Animation |
| --- | --- |
| Typing | Talk `talk` |
| Moving mouse | Look `look` |
| Clicking | Wave `wave` (once) |
| ~2 s idle | Idle `idle` |

---

## 11. System Tray Menu

Right-click the tray icon:

- Open Control Panel
- Show / Hide Pet
- ▶ Start Pomodoro
- ☕ Rest Now
- ■ Stop Timer
- Quit

> Closing the control panel does **not** quit the app. Use **Quit** in the tray to exit.

---

## 12. Settings & Data Location

| OS | Data folder |
| --- | --- |
| Windows | `%APPDATA%\WALL-E\` |
| macOS | `~/Library/Application Support/WALL-E/` |

| File | Contents |
| --- | --- |
| `settings.json` | Pomodoro, pet position/size, sound, `language`, etc. |
| `todos.json` | To-do list with priorities |
| `notes.json` | Notes |
| `reminders.json` | Reminders |

Deleting these files resets defaults (Pomodoro → 50/10/3; sample to-dos/reminders recreated).

---

## 13. Run from Source / Rebuild

### Requirements

| Platform | Requirement |
| --- | --- |
| Windows | Windows 10/11 |
| macOS | macOS 11+ (for DMG build) |
| All | Python 3.10+ (tested with 3.12) |

### First-time setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### Run

```powershell
.\.venv\Scripts\python.exe run.py
```

### Windows build + install

```powershell
.\build.bat       # dist\WALL-E.exe + dist\WALL-E.msi
.\install.bat     # quick install or MSI wizard; copies guides
```

MSI only (exe must exist):

```powershell
.\build_msi.bat
```

Manual build:

```powershell
.\.venv\Scripts\python.exe make_icon.py
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean WALL-E.spec
.\.venv\Scripts\python.exe scripts\build_msi.py
```

**Windows output:**

- `dist\WALL-E.exe` — portable single-file build
- `dist\WALL-E.msi` — v1.1.0 installer

> With **WiX Toolset**, `build_msi.bat` produces a full MSI with desktop shortcut; otherwise the Python `msilib` fallback is used.

### macOS build (DMG)

```bash
chmod +x build_mac.sh scripts/build_dmg.sh
./build_mac.sh
```

Output: `dist/WALL-E.app`, `dist/WALL-E.dmg`. See [BUILD_MAC.md](BUILD_MAC.md).

### Project layout

```
WALL-E/
├─ run.py
├─ build.bat / build_msi.bat / install.bat / uninstall.bat   Windows
├─ build_mac.sh / BUILD_MAC.md / WALL-E-mac.spec             macOS
├─ USER_GUIDE.md          This guide (English)
├─ 操作手册.md             User guide (Chinese)
├─ mobile/操作手册.md      Mobile (Chinese)
└─ walle/
   ├─ app.py / i18n.py / control_panel.py / pet_window.py / ...
```

### Headless smoke test

```powershell
.\.venv\Scripts\python.exe smoke_test.py
```

---

## 14. FAQ

**Q: Double-clicking exe does nothing?**  
A: Check the **bottom-right** of the screen and the **system tray**. Right-click tray → **Show/Hide Pet**.

**Q: SmartScreen blocked the app?**  
A: Click **More info → Run anyway**. The app runs fully offline.

**Q: Pomodoro is not 50/10/3?**  
A: Check `%APPDATA%\WALL-E\settings.json`, or delete it to restore defaults.

**Q: Start at login?**  
A: Choose `Y` during `install.bat`, or add a shortcut to `shell:startup`.

**Q: Move data to another PC?**  
A: Copy the entire `%APPDATA%\WALL-E` folder.

**Q: Upgraded but features unchanged?**  
A: Run `build.bat` and `install.bat` again, then restart WALL-E.

**Q: Reset sample to-dos/reminders?**  
A: Delete `todos.json` or `reminders.json` under the data folder and restart.

**Q: exe vs msi?**  
A: exe runs portably; msi installs to the user folder. Same app. `install.bat` can launch the MSI wizard if `dist\WALL-E.msi` exists.

**Q: Switch to Chinese UI?**  
A: Control Panel → **Pomodoro** → **Language** → 简体中文. Or set `"language": "zh"` in `settings.json`.

**Q: How to install on Mac?**  
A: Use `dist/WALL-E.dmg` (build on Mac with `build_mac.sh`; DMG cannot be built on Windows).

**Q: Sync data between Mac and Windows?**  
A: Not automatic. Manually copy JSON files from each platform’s data folder (see Section 12).

---

## 15. Other Platforms

| Platform | Documentation |
| --- | --- |
| Android (user) | [mobile/操作手册.md](mobile/操作手册.md) (Chinese) |
| macOS build | [BUILD_MAC.md](BUILD_MAC.md) |
| Android build | [mobile/BUILD_ANDROID.md](mobile/BUILD_ANDROID.md) |
| Chinese desktop guide | [操作手册.md](操作手册.md) |

---

🎬 *“WALL-E…” — May this little robot help you work well and rest well!*
