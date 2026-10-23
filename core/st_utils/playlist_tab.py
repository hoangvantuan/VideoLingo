"""Tab "Playlist": read a Playlist, select its videos and follow the Lượt chạy playlist.

The run belongs to the process (``playlist_run.current_run()``), not to the session of a tab,
so a new tab or F5 shows the same progress and controls it. An unfinished run (stopped, or
left by a closed app) shows "Continue" and "End run" and never runs by itself.
"""
import streamlit as st

from core import playlist_run
from translations.translations import translate as t


def _status_labels():
    return {
        playlist_run.WAITING: t("Waiting"),
        playlist_run.RUNNING: t("Running"),
        playlist_run.DONE: t("Done"),
        playlist_run.FAILED: t("Failed"),
        playlist_run.UNAVAILABLE: t("Unavailable"),
    }


def _duration(seconds):
    if seconds is None:
        return ""
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


@st.fragment(run_every=1)
def _run_panel():
    """Progress and controls of the run. Refreshes every second while the run is active."""
    run = playlist_run.current_run()
    if run is None:
        return
    snapshot = run.snapshot()
    active = snapshot.state in ("running", "paused", "stopping")
    busy = active or snapshot.unfinished
    st.subheader(snapshot.title)
    st.progress(snapshot.done / snapshot.total if snapshot.total else 0.0,
                text=f"{snapshot.done}/{snapshot.total}")
    video = snapshot.current_video
    if video:
        step = t(snapshot.current_step) if snapshot.current_step else ""
        icon = "⏸️" if snapshot.state == "paused" else "⏳"
        st.info(f"{icon} {video.index}. {video.title} — {step}")
    if snapshot.state == "paused":
        if snapshot.pause_message:
            st.error(f"⏸️ {t(snapshot.pause_message)}")
        else:
            st.warning(f"⏸️ {t('Paused')}")
        col1, col2 = st.columns(2)
        if col1.button(f"▶️ {t('Resume')}", key="playlist_resume", width="stretch"):
            run.resume()
            st.rerun()
        if col2.button(f"⏹️ {t('Stop')}", key="playlist_stop_paused", width="stretch"):
            run.stop()
            st.rerun()
    elif snapshot.state == "running":
        col1, col2 = st.columns(2)
        if col1.button(f"⏸️ {t('Pause')}", key="playlist_pause", width="stretch"):
            run.pause()
            st.rerun()
        if col2.button(f"⏹️ {t('Stop')}", key="playlist_stop", width="stretch"):
            run.stop()
            st.rerun()
    elif snapshot.state == "stopping":
        st.info(t("Stopping..."))
    elif snapshot.unfinished:
        if snapshot.state == "error":
            st.error(f"❌ {t('Task error')}: {snapshot.error}")
        else:
            st.warning(f"⏹️ {t('Playlist run stopped. The unfinished video is kept in its history folder.')}")
        col1, col2 = st.columns(2)
        if col1.button(f"▶️ {t('Continue')}", key="playlist_continue", width="stretch"):
            try:
                run.start()
            except playlist_run.PlaylistRunError as e:
                message = str(e)
                st.error(t(message))
            else:
                st.rerun()
        if col2.button(f"🏁 {t('End run')}", key="playlist_end", width="stretch"):
            try:
                run.end()
            except playlist_run.PlaylistRunError as e:
                message = str(e)
                st.error(t(message))
            else:
                st.rerun()
    elif snapshot.state == "completed":
        st.success(t("Playlist run completed!"))
    elif snapshot.state == "error":
        st.error(f"❌ {t('Task error')}: {snapshot.error}")

    labels = _status_labels()
    st.dataframe(
        [{"#": v.index, t("Title"): v.title, t("Duration"): _duration(v.duration),
          t("Status"): labels[v.status], t("History folder"): v.folder if v.status == playlist_run.DONE else "",
          t("Failed step"): t(v.failed_step) if v.status == playlist_run.FAILED and v.failed_step else "",
          t("Error"): v.error if v.status == playlist_run.FAILED else ""}
         for v in snapshot.videos if v.selected],
        hide_index=True, width="stretch")

    # The form of a new run follows the end of this one
    if st.session_state.get("_playlist_run_active", busy) != busy:
        st.session_state["_playlist_run_active"] = busy
        st.rerun(scope="app")
    st.session_state["_playlist_run_active"] = busy


def _start_form(playlist):
    st.markdown(f"**{playlist.title}**")
    st.caption(t("Select the videos to process"))
    labels = _status_labels()
    selected = []
    for video in playlist.videos:
        label = f"{video.index}. {video.title}"
        if video.duration is not None:
            label += f" ({_duration(video.duration)})"
        if not video.available:
            label += f" — {labels[playlist_run.UNAVAILABLE]}"
        elif video.done:  # done in an earlier run: not selected, can be selected again
            label += f" — {labels[playlist_run.DONE]}"
        if st.checkbox(label, value=video.available and not video.done, disabled=not video.available,
                       key=f"playlist_pick_{playlist.url}_{video.video_id}_{video.done}") and video.available:
            selected.append(video.video_id)
    scope = st.radio(
        t("Processing scope"), [playlist_run.SUBTITLES, playlist_run.DUBBING], horizontal=True,
        format_func=lambda value: t("Subtitles only") if value == playlist_run.SUBTITLES else t("Subtitles and dubbing"),
        key="playlist_scope")
    if st.button(t("Start playlist"), key="playlist_start", disabled=not selected, width="stretch"):
        try:
            playlist_run.PlaylistRun.create(playlist, selected, scope).start()
        except playlist_run.PlaylistRunError as e:
            message = str(e)
            st.error(t(message))
            return
        st.rerun()


def render():
    st.caption(t("Settings in the sidebar are read at each step: a change during a playlist run applies to the following steps and videos."))
    # A run left unfinished by a closed app is found in history/; it waits for "Continue"
    run = playlist_run.load_unfinished() or playlist_run.current_run()
    if run is not None:
        with st.container(border=True):
            _run_panel()
    if run is not None and (run.snapshot().state in ("running", "paused", "stopping") or run.snapshot().unfinished):
        return

    with st.container(border=True):
        url = st.text_input(t("Playlist or channel URL"), key="playlist_url")
        if st.button(t("Read playlist"), key="playlist_read", width="stretch") and url:
            try:
                with st.spinner(t("Reading playlist...")):
                    st.session_state["_playlist"] = playlist_run.read_playlist(url)
            except Exception as e:
                st.session_state.pop("_playlist", None)
                st.error(f"{t('Read failed')}: {e}")
        playlist = st.session_state.get("_playlist")
        if playlist is not None:
            _start_form(playlist)
