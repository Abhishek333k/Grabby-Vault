"""
Quality / format presets for yt-dlp.

Why this exists:
- Plain `best` or loose `bestvideo+bestaudio` often picks tiny HLS ladders (e.g. 360p)
  or video-only DASH streams that fail to merge → blurry / no audio.
- We prefer: highest resolution within cap + separate best audio + ffmpeg merge,
  with H.264/AAC + MP4 when possible for maximum player compatibility.
"""

# Sort key: resolution first, then prefer widely-compatible codecs/containers.
# See: https://github.com/yt-dlp/yt-dlp#sorting-formats
DEFAULT_FORMAT_SORT = [
    "res",           # highest resolution
    "fps",           # higher fps when tied
    "hdr:1",         # prefer HDR when available (optional quality win)
    "vcodec:h264",   # H.264 plays everywhere
    "acodec:m4a",    # AAC audio
    "ext:mp4:m4a",   # MP4/M4A containers
    "size",
    "br",
    "asr",
    "proto",
]

# bv* = best video including ones with audio; +ba = best audio; /b = single-file fallback
# height filters apply to video; audio still attaches via +ba
def _height_format(max_height: int | None) -> str:
    """
    Build a robust format string.
    Order of attempts:
      1) best video (with height cap) + best audio
      2) best single-file progressive under height cap
      3) absolute best available (last-resort, never leave empty-handed)
    """
    if max_height is None:
        # Uncapped "best quality"
        return (
            "bv*+ba/"
            "b/"
            "best"
        )
    h = max_height
    return (
        f"bv*[height<=?{h}]+ba/"
        f"b[height<=?{h}]/"
        f"wv*[height<=?{h}]+ba/"
        f"w[height<=?{h}]/"
        f"bv*+ba/b/best"
    )


# UI-facing presets: (label, format_id used internally)
QUALITY_PRESETS = [
    {
        "id": "best",
        "label": "Best available",
        "format": _height_format(None),
        "audio_only": False,
        "merge": "mp4",
    },
    {
        "id": "2160",
        "label": "4K (2160p)",
        "format": _height_format(2160),
        "audio_only": False,
        "merge": "mp4",
    },
    {
        "id": "1440",
        "label": "1440p",
        "format": _height_format(1440),
        "audio_only": False,
        "merge": "mp4",
    },
    {
        "id": "1080",
        "label": "1080p (Recommended)",
        "format": _height_format(1080),
        "audio_only": False,
        "merge": "mp4",
    },
    {
        "id": "720",
        "label": "720p",
        "format": _height_format(720),
        "audio_only": False,
        "merge": "mp4",
    },
    {
        "id": "480",
        "label": "480p",
        "format": _height_format(480),
        "audio_only": False,
        "merge": "mp4",
    },
    {
        "id": "audio_mp3",
        "label": "Audio only (MP3)",
        "format": "ba/b",
        "audio_only": True,
        "merge": None,
        "audio_codec": "mp3",
        "audio_quality": "192",
    },
    {
        "id": "audio_m4a",
        "label": "Audio only (M4A / AAC)",
        "format": "ba/b",
        "audio_only": True,
        "merge": None,
        "audio_codec": "m4a",
        "audio_quality": "0",  # best VBR for m4a in yt-dlp
    },
]

# Default preset id for the quality dialog
DEFAULT_PRESET_ID = "1080"

# Used when UI still passes a raw format string (legacy / playwright)
LEGACY_DEFAULT_FORMAT = _height_format(None)

PRESET_BY_ID = {p["id"]: p for p in QUALITY_PRESETS}
PRESET_BY_FORMAT = {p["format"]: p for p in QUALITY_PRESETS}


def resolve_preset(format_str: str | None) -> dict:
    """
    Resolve a UI selection (preset id OR raw yt-dlp format string) to a preset dict.
    """
    if not format_str:
        return PRESET_BY_ID[DEFAULT_PRESET_ID]

    if format_str in PRESET_BY_ID:
        return PRESET_BY_ID[format_str]

    if format_str in PRESET_BY_FORMAT:
        return PRESET_BY_FORMAT[format_str]

    # Legacy strings from older UI builds
    legacy_map = {
        "bestvideo+bestaudio/best": PRESET_BY_ID["best"],
        "bestvideo[height<=2160]+bestaudio/best": PRESET_BY_ID["2160"],
        "bestvideo[height<=1080]+bestaudio/best": PRESET_BY_ID["1080"],
        "bestvideo[height<=720]+bestaudio/best": PRESET_BY_ID["720"],
        "bestaudio/best": PRESET_BY_ID["audio_mp3"],
        "best": PRESET_BY_ID["best"],
    }
    if format_str in legacy_map:
        return legacy_map[format_str]

    # Unknown raw format: treat as custom video merge
    return {
        "id": "custom",
        "label": "Custom",
        "format": format_str,
        "audio_only": False,
        "merge": "mp4",
    }
