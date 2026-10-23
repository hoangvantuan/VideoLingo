import os
import shutil

from core.utils.models import _AUDIO_DONE_MARKER, _AUDIO_SEGS_DIR, _AUDIO_TMP_DIR


def delete_dubbing_files():
    # The raw TTS clips in output/audio/tmp are skipped when they exist, so they
    # must go too: otherwise a new voice or TTS method reuses the old clips.
    files_to_delete = [
        os.path.join("output", "dub.wav"),
        os.path.join("output", "dub.mp3"),
        os.path.join("output", "normalized_dub.wav"),
        os.path.join("output", "dub_src.srt"),
        os.path.join("output", "output_dub.mp4"),
        _AUDIO_DONE_MARKER,
    ]

    for file_path in files_to_delete:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {str(e)}")
        else:
            print(f"File not found: {file_path}")

    for folder in (_AUDIO_SEGS_DIR, _AUDIO_TMP_DIR):
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"Deleted folder and contents: {folder}")
            except Exception as e:
                print(f"Error deleting folder {folder}: {str(e)}")
        else:
            print(f"Folder not found: {folder}")

if __name__ == "__main__":
    delete_dubbing_files()
