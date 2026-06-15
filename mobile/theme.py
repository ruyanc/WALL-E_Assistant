"""移动端配色：浅色底 + 分区色调 + 圆角控件。"""

from __future__ import annotations

# 页面基底
BG = (0.96, 0.95, 0.93, 1)
BG_ELEVATED = (0.99, 0.98, 0.96, 1)
SURFACE = (1.0, 0.99, 0.97, 1)
SURFACE_WARM = (1.0, 0.97, 0.93, 1)
CARD = (1.0, 1.0, 0.99, 1)
CARD_BORDER = (0.90, 0.87, 0.82, 1)
CARD_SHADOW = (0.14, 0.12, 0.10, 0.07)

# 各功能页顶部色带（柔和渐变区）
PAGE_TODO_TINT = (0.96, 0.90, 0.80, 1)
PAGE_NOTES_TINT = (0.88, 0.92, 0.98, 1)
PAGE_REMIND_TINT = (0.90, 0.95, 0.92, 1)
PAGE_TIMER_TINT = (0.98, 0.91, 0.84, 1)
PAGE_ACCOUNT_TINT = (0.94, 0.90, 0.96, 1)

# 品牌金
ACCENT = (0.64, 0.42, 0.14, 1)
ACCENT_LIGHT = (0.96, 0.88, 0.74, 1)
# 瓦力吉祥物底（欢迎页 / 大号瓦力，浅色而非金色）
MASCOT_BG = (0.99, 0.98, 0.96, 1)
ACCENT_SOFT = (0.86, 0.72, 0.50, 1)
ACCENT_TEXT = (1.0, 1.0, 0.98, 1)

# 正文（输入框使用纯黑，避免 Android 上显示为白字）
TEXT = (0.20, 0.18, 0.16, 1)
INPUT_TEXT = (0.0, 0.0, 0.0, 1)
TEXT_SECONDARY = (0.44, 0.41, 0.37, 1)
TEXT_MUTED = (0.58, 0.54, 0.50, 1)
TEXT_DONE = (0.64, 0.60, 0.56, 1)
HINT = (0.52, 0.49, 0.45, 1)

# 导航与分段
NAV_IDLE = (0.94, 0.93, 0.90, 1)
NAV_ACTIVE_BG = (0.99, 0.94, 0.86, 1)
NAV_BORDER = (0.90, 0.88, 0.84, 1)
SEGMENT_TRACK = (0.93, 0.91, 0.88, 1)

# 输入框
INPUT_BG = (1.0, 1.0, 0.99, 1)
INPUT_BORDER = (0.84, 0.81, 0.76, 1)
INPUT_FOCUS_BORDER = (0.72, 0.58, 0.38, 1)
HINT_INPUT = (0.60, 0.57, 0.52, 1)

# 语义按钮
BTN_SUCCESS = (0.28, 0.55, 0.42, 1)
BTN_SUCCESS_TEXT = (1.0, 1.0, 0.98, 1)
BTN_DANGER = (0.76, 0.38, 0.34, 1)
BTN_DANGER_TEXT = (1.0, 0.98, 0.96, 1)
BTN_NEUTRAL = (0.94, 0.92, 0.88, 1)
BTN_NEUTRAL_TEXT = TEXT

# 横幅
BANNER_BG = (0.99, 0.96, 0.91, 0.97)
BANNER_BORDER = ACCENT_SOFT
BANNER_TEXT = TEXT

# 优先级
PRIORITY_COLORS = {
    2: (0.86, 0.36, 0.30, 1),
    1: (0.26, 0.52, 0.78, 1),
    0: (0.26, 0.64, 0.46, 1),
}

# 圆角（dp，在 layout / ui_widgets 中与 dp() 配合）
CARD_RADIUS = 14
BTN_RADIUS = 12
BTN_RADIUS_SM = 10
INPUT_RADIUS = 10
BTN_PRESS_FACTOR = 0.86
