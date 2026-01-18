[app]
title = Fokus
package.name = fokus
package.domain = org.rh

source.dir = .
source.include_exts = py,png,jpg,kv,ttf

version = 1.0

requirements = python3,kivy,plyer,matplotlib

orientation = portrait
fullscreen = 1

android.permissions = VIBRATE,RECEIVE_BOOT_COMPLETED

icon.filename = icon.png
presplash.filename = splash.png

android.api = 33
android.minapi = 24

[buildozer]
log_level = 2
warn_on_root = 1
