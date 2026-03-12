"""
Batch-convert MP4 files in assets/videos_finales to GIF using moviepy.
Requires: pip install moviepy imageio-ffmpeg
Usage: python scripts/convert_videos_to_gif.py
"""
import os
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.Resize import Resize

SRC_DIR = os.path.join('assets', 'videos_finales')
FPS = 15
WIDTH = 640

for fname in os.listdir(SRC_DIR):
    if not fname.lower().endswith('.mp4'):
        continue
    src = os.path.join(SRC_DIR, fname)
    base = os.path.splitext(fname)[0]
    out = os.path.join(SRC_DIR, base + '.gif')
    print(f'Convirtiendo {src} -> {out}')
    try:
        clip = VideoFileClip(src)
        # resize keeping aspect
        clip_resized = clip.with_effects([Resize(width=WIDTH)])
        clip_resized.write_gif(out, fps=FPS)
        clip.close()
    except Exception as e:
        print('Error convirtiendo', src, e)
