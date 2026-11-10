"""Accès centralisé et tolérant aux secrets Streamlit / variables d'environnement."""

from __future__ import annotations

import os
from typing import Any


def get_secret(key: str, default: Any = None) -> Any:
    """Lit un secret depuis ``st.secrets`` puis l'environnement.

    Ne lève jamais d'exception : l'absence de ``secrets.toml`` est un cas normal
    (mode démo / développement local).
    """
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


def has_secret(key: str) -> bool:
    value = get_secret(key)
    return value is not None and value != ""


SPREADSHEET_NAME = "DB_Dynamic_Hybrid_Coach"
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
