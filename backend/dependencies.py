from session_store import SessionStore


_session_store = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store
