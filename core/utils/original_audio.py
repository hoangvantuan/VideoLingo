"""F10 (custom) — voice-over dubbing: keep the video's own audio quietly under the dubbed voice."""
import subprocess

from rich import print as rprint


def original_volume(load_key):
    """Factor applied to the original audio track; 0 (or a missing key) keeps the upstream merge."""
    try:
        return float(load_key('original_volume') or 0)
    except KeyError:
        return 0.0


def video_has_audio(video_file):
    """The source of the original audio is the video file itself (an SRT input has no extracted audio)."""
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_type',
         '-of', 'csv=p=0', str(video_file)],
        check=True, capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    return bool(probe.stdout.strip())


def mix_original(load_key, video_file):
    """Volume of the original track to mix, or None when the dub is merged as before."""
    volume = original_volume(load_key)
    if volume <= 0:
        return None
    if not video_has_audio(video_file):
        rprint('[yellow]The video has no audio track; exporting the dubbed voice alone.[/yellow]')
        return None
    return volume


def mix_filter(volume, dub_input=1):
    """Original track at a fixed level under the dub; normalize=0 so amix does not halve the dub."""
    return (f'[0:a:0]volume={volume:g}[orig];'
            f'[orig][{dub_input}:a]amix=inputs=2:duration=first:dropout_transition=3:normalize=0[a]')
