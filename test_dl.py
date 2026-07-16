import yt_dlp
import os

url = "https://py.damfantom10.store/cdn/092e3d2d14736a0ad5386790d18cb7b11a029a5778ea3b09ef229d663183ccc9ba72297dfc19b1b0d597493fa1f71c7e97d8efc68b882167f4d32423?t.m3u8"
opts = {
    'ffmpeg_location': os.path.abspath('bin'),
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'format': 'best',
    'merge_output_format': 'mkv',
    'noplaylist': True,
    'writethumbnail': True,
    'writesubtitles': True,
    'subtitleslangs': ['en'],
    'postprocessors': [
        {'key': 'FFmpegEmbedSubtitle'},
        {'key': 'FFmpegMetadata'},
    ],
    'impersonate': 'chrome',
}

try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
except Exception as e:
    print(f"Error type: {type(e)}")
    print(f"Error str: '{str(e)}'")
    if hasattr(e, 'msg'):
        print(f"Error msg: '{e.msg}'")
    if hasattr(e, 'exc_info'):
        print(f"Exc info: {e.exc_info}")
