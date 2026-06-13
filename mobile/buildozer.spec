[app]

title = WALL-E
package.name = walle
package.domain = org.walle.pet

source.dir = .
source.include_exts = py,png,json
source.exclude_dirs = .buildozer,bin,.git,__pycache__

version = 1.0.0

requirements = python3,kivy==2.3.1,plyer

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,VIBRATE,WAKE_LOCK,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.entrypoint = org.kivy.android.PythonActivity
android.app_theme = "@android:style/Theme.NoTitleBar"

[buildozer]

log_level = 2
warn_on_root = 1
