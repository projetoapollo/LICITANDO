# observability.py
from __future__ import annotations

import os
import time
import functools
from typing import Optional, Callable, Any

# Detecta se Streamlit está disponível
try:
    import streamlit as st
    _HAS_ST = True
except Exception:  # pragma: no cover
    st = None  # type: ignore[assignment]
    _HAS_ST = False

_RUN_ID_KEY = "_run_id"


def get_run_id() -> str:
    """ID de execução para correlacionar logs."""
    if _HAS_ST:
        if _RUN_ID_KEY not in st.session_state:
            st.session_state[_RUN_ID_KEY] = str(int(time.time() * 1000))
        return str(st.session_state[_RUN_ID_KEY])
    # fallback fora do Streamlit
    return os.environ.get("RUN_ID", str(int(time.time() * 1000)))


def _stdout_log(level: str, msg: str, *, step: str = "", func: str = "") -> None:
    print(f"[{level}] run={get_run_id()} step={step} func={func} - {msg}")


def notify_error(
    text: str,
    *args: Any,
    exc: Optional[BaseException] = None,
    step: str = "",
    **kwargs: Any,
) -> None:
    """Notifica erro no Streamlit (se houver) e no stdout."""
    if _HAS_ST:
        try:
            st.error(text)
        except Exception:
            pass
    _stdout_log("ERROR", text, step=step)


def guard(step_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator no-op com logging simples."""
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        qual = f"{fn.__module__}.{fn.__name__}"

        @functools.wraps(fn)
        def _wrap(*args: Any, **kwargs: Any):
            _stdout_log("INFO", "step_start", step=step_name, func=qual)
            try:
                return fn(*args, **kwargs)
            except BaseException as e:
                notify_error(f"{qual} failed: {e}", exc=e, step=step_name)
                raise
            finally:
                _stdout_log("INFO", "step_end", step=step_name, func=qual)

        return _wrap
    return _decorator
