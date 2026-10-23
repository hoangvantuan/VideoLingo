"""Move every file of output/ into a chosen history folder without deleting what it holds.

The history save of upstream (`onekeycleanup.cleanup`) names the folder after the video and
replaces a folder of the same name. A Lượt chạy playlist moves the unfinished work of a video
into its own folder more than once, so files of an earlier move have to stay there.
"""
import os
import shutil
from pathlib import Path


def merge_output(destination, source="output"):
    """Move the files of `source` (with `log/`, `gpt_log/` and other folders) into `destination`.

    A file of the same name in `destination` is replaced, every other file there is kept.
    `source` is removed once it is empty.
    """
    source, destination = Path(source), Path(destination)
    if not source.exists():
        return
    for folder, _dirs, files in os.walk(source):
        target = destination / Path(folder).relative_to(source)
        target.mkdir(parents=True, exist_ok=True)
        for name in files:
            if (target / name).is_dir():
                shutil.rmtree(target / name)
            shutil.move(os.path.join(folder, name), target / name)
    for folder, _dirs, _files in sorted(os.walk(source), key=lambda entry: len(entry[0]), reverse=True):
        try:
            os.rmdir(folder)
        except OSError:
            pass
