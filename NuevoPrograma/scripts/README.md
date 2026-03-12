Conversion de MP4 a GIF

Opciones:

1) Usar ffmpeg (recomendado, rápido y control de calidad)
- Asegúrate de tener `ffmpeg` en el PATH.
- Ejecuta desde la raíz del proyecto en PowerShell:
  .\scripts\convert_videos_to_gif.ps1

2) Usar Python + moviepy (si no quieres ffmpeg o no está instalado globalmente)
- Instala dependencias:
  pip install moviepy imageio-ffmpeg
- Ejecuta:
  python scripts/convert_videos_to_gif.py

Notas:
- Los GIFs se crearán junto a los MP4 en `assets/videos_finales` con la misma base de nombre.
- Los GIFs suelen ser más pesados que MP4; ajusta `WIDTH` y `FPS` en los scripts para reducir tamaño.
