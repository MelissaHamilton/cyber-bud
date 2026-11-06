"""Anonymous browser identity; wait for the browser before opening any database."""
import hashlib
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_browser_identity = components.declare_component(
    "cyberbud_visitor", path=str(Path(__file__).with_name("visitor_identity"))
)


def visitor_id_from_token(token):
    if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token):
        raise ValueError("Invalid browser identity")
    # A database directory name cannot itself be used as a browser credential.
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def get_visitor_id():
    token = _browser_identity(key="cyberbud_browser_identity", default=None)
    if token is None:
        st.caption("Opening your private workspace…")
        st.stop()
    try:
        visitor_id = visitor_id_from_token(token)
    except ValueError:
        st.error("Allow site cookies and refresh to open your private workspace.")
        st.stop()
    # Clear cached conversations too, including state from the old shared database.
    if st.session_state.get("_progress_owner") != visitor_id:
        for key in list(st.session_state):
            if key != "cyberbud_browser_identity":
                del st.session_state[key]
        st.session_state["_progress_owner"] = visitor_id
    return visitor_id
