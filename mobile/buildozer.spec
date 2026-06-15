[app]

title = WALL-E
package.name = walle
package.domain = org.walle.pet

source.dir = .
source.include_exts = py,png,json,ttf,ttc,otf
source.exclude_dirs = .buildozer,bin,.git,__pycache__

version = 1.2.7

requirements = python3,kivy==2.3.1,plyer,android

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #F5F2ED

# 与 1.0.1 对齐：暂不注册前台 Service（Android 14+ 需 foregroundServiceType，否则易闪退）
android.permissions = INTERNET,VIBRATE,WAKE_LOCK,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.entrypoint = org.kivy.android.PythonActivity
android.app_theme = "@android:style/Theme.NoTitleBar"

[buildozer]

log_level = 2
warn_on_root = 1
