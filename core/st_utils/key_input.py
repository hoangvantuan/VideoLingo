"""Custom (#21): the sidebar box of a key, see "Key trong .env" in CUSTOM.md.

A key whose config.yaml value is a ${VAR} reference shows an empty box and the name of its variable, never its
value; a key typed there is written to .env under VAR and config.yaml keeps the reference. Any other key is a
masked box that saves to config.yaml as before.
"""

import os

import streamlit as st

from core.utils import env_keys
from core.utils.config_utils import update_key


def key_input(label, key, widget_key=None, help=None, placeholder=None):
    """The box of `key`; returns the key in use ("" when none)."""
    stored = env_keys.raw(key, "")
    var = env_keys.variable(stored)
    if var is None:
        stored = "" if stored is None else str(stored)  # YAML reads a digits-only key as int
        entered = st.text_input(label, value=stored, type="password", key=widget_key, help=help,
                                placeholder=placeholder)
        if entered != stored:
            update_key(key, entered, add_missing=True)
        return entered
    entered = st.text_input(label, value="", type="password", key=widget_key, help=help,
                            placeholder=f"Lấy từ .env: {var}. Nhập key mới để thay")
    st.caption(f"Lấy từ .env: {var}")
    if entered and entered != os.environ.get(var):
        env_keys.set_env(var, entered)
    return entered or os.environ.get(var, env_keys.reference(stored)[1] or "")
