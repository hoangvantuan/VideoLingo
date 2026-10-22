"""F10 — voice-over dubbing: the original audio stays quietly under the dubbed voice.

FFmpeg is not run: subprocess.run is replaced, so the tests read the commands built
by the merge step (the video's audio track is reported by a fake ffprobe).
"""
import subprocess
from types import SimpleNamespace

import pytest


def _merge(tmp_path, monkeypatch, *, volume=None, has_background=False, video_has_audio=True):
    from core import _1_ytdlp, _12_dub_to_vid as merge

    monkeypatch.chdir(tmp_path)
    (tmp_path / 'output').mkdir()
    if has_background:
        (tmp_path / 'output/background.mp3').write_bytes(b'')
    config = {'burn_subtitles': False, 'ffmpeg_gpu': False}
    if volume is not None:
        config['original_volume'] = volume
    commands = []

    def run(cmd, *args, **kwargs):
        commands.append(cmd)
        stdout = 'audio\n' if cmd[0] == 'ffprobe' and video_has_audio else ''
        return SimpleNamespace(returncode=0, stdout=stdout, stderr='')

    def load_key(key):
        return config[key]  # KeyError for a missing key, like the real load_key

    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.setattr(_1_ytdlp, 'is_audio_only_input', lambda: False)
    monkeypatch.setattr(merge, 'find_video_files', lambda: 'output/source.mp4')
    monkeypatch.setattr(merge, '_BACKGROUND_AUDIO_FILE', 'output/background.mp3')
    monkeypatch.setattr(merge, 'normalize_dub_audio', lambda source, target: None)
    monkeypatch.setattr(merge, 'load_key', load_key)
    merge.merge_video_audio()
    return [cmd for cmd in commands if cmd[0] == 'ffmpeg'][0]


def _option(cmd, name):
    return cmd[cmd.index(name) + 1]


def _inputs(cmd):
    return [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '-i']


# Commands of the merge before F10, written out by hand.
LEGACY_WITH_BACKGROUND = [
    'ffmpeg', '-y', '-i', 'output/source.mp4', '-i', 'output/background.mp3',
    '-i', 'output/normalized_dub.wav',
    '-filter_complex', '[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=3[a]',
    '-map', '0:v:0', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
    'output/output_dub.mp4',
]
LEGACY_DUB_ONLY = [
    'ffmpeg', '-y', '-i', 'output/source.mp4', '-i', 'output/normalized_dub.wav',
    '-map', '0:v:0', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
    'output/output_dub.mp4',
]


@pytest.mark.parametrize('volume', [None, 0, 0.0])
@pytest.mark.parametrize('has_background', [True, False])
def test_off_keeps_the_previous_command(tmp_path, monkeypatch, volume, has_background):
    cmd = _merge(tmp_path, monkeypatch, volume=volume, has_background=has_background)

    assert cmd == (LEGACY_WITH_BACKGROUND if has_background else LEGACY_DUB_ONLY)


def test_on_mixes_the_original_track_at_the_configured_level(tmp_path, monkeypatch):
    cmd = _merge(tmp_path, monkeypatch, volume=0.25)

    assert _inputs(cmd) == ['output/source.mp4', 'output/normalized_dub.wav']
    assert _option(cmd, '-filter_complex') == (
        '[0:a:0]volume=0.25[orig];'
        '[orig][1:a]amix=inputs=2:duration=first:dropout_transition=3:normalize=0[a]')
    assert cmd[cmd.index('-map', cmd.index('-map') + 1) + 1] == '[a]'


def test_on_with_demucs_background_ignores_the_background(tmp_path, monkeypatch):
    cmd = _merge(tmp_path, monkeypatch, volume=0.25, has_background=True)

    assert 'output/background.mp3' not in _inputs(cmd)
    assert _inputs(cmd) == ['output/source.mp4', 'output/normalized_dub.wav']
    assert '[0:a:0]volume=0.25[orig]' in _option(cmd, '-filter_complex')


def test_on_without_an_audio_track_exports_the_dub_alone(tmp_path, monkeypatch, capsys):
    cmd = _merge(tmp_path, monkeypatch, volume=0.25, has_background=False, video_has_audio=False)

    assert cmd == LEGACY_DUB_ONLY
    assert 'no audio track' in capsys.readouterr().out
