[app]

# Nombre que se verá bajo el icono en el teléfono
title = Galeria TikTok

# Identificador interno (minúsculas, sin espacios ni guiones)
package.name = galeriatiktok
package.domain = org.robinho

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
# MUY IMPORTANTE: no meter el venv ni los videos de prueba dentro del APK
source.exclude_dirs = venv,videos,bin,.buildozer,.github,__pycache__

version = 0.1

requirements = python3,kivy,ffpyplayer

orientation = portrait
fullscreen = 1

# Permisos para leer los videos del teléfono
android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_VIDEO

# Solo 64 bits: compila más rápido y funciona en casi todos los teléfonos actuales
android.archs = arm64-v8a

# Acepta la licencia del SDK automáticamente (necesario en la nube)
android.accept_sdk_license = True

android.allow_backup = True


[buildozer]

log_level = 2
warn_on_root = 1
