"""Optional local .env loading.

Streamlit Cloud uses ``st.secrets`` and the process environment. A local
``.env`` file is read only when python-dotenv is installed, and it never
overrides variables that are already set.
"""

from __future__ import annotations


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)


load_local_env()
