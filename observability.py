# observability.py
from __future__ import annotations
import os, sys, json, time, functools, traceback
from typing import Any, Callable, Optional

# Detecta se Streamlit está disponível
try:
    import streamlit as st  # type: ignore
    _HAS_ST = True
except Exception:
    st = None  # type: ignore
    _HAS_ST = False

RUN_ID_KEY = "_run_id"

def get_run_id() -> str:
    """ID de execução para correlacionar logs."""
    if _HAS_ST:
        if RUN_ID_KEY not in st.session_state:
            st.session_state[RUN_ID_KEY] = str(int(time.time()*1000))
        return str(st.session_state[RUN_ID_KEY])
    # fallback fora do Streamlit
    return os.environ.get("RUN_ID", str(int(time.time()*1000)))

def _stdout_log(level: str, msg: str, **extra: Any) -> None:
    payload = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "level": level,
               "run_id": get_run_id(), "msg": msg, **extra}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stdout, flush=True)

class AppError(Exception):
    """Erros esperados com dica para o usuário."""
    def __init__(self, message: str, *, hint: Optional[str]=None, code: str="APP_ERROR", **ctx: Any):
        super().__init__(message)
        self.hint = hint
        self.code = code
        self.ctx = ctx

def notify_info(text: str) -> None:
    _stdout_log("INFO", text)
    if _HAS_ST: st.info(text)

def notify_success(text: str) -> None:
    _stdout_log("INFO", text, status="success")
    if _HAS_ST: st.success(text)

def notify_warning(text: str) -> None:
    _stdout_log("WARN", text)
    if _HAS_ST: st.warning(text)

def notify_error(text: str, *, exc: Optional[BaseException]=None, step: str="") -> None:
    data = {"step": step}
    if exc:
        data["exc_type"] = type(exc).__name__
        data["exc_msg"] = str(exc)
        data["trace"] = "".join(traceback.format_exception(exc))
    _stdout_log("ERROR", text, **data)
    if _HAS_ST:
        st.error(text)
        if exc:
            st.exception(exc)

def guard(step_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator: loga início/fim; mostra erro na tela (com step/script);
    re-lança AppError como é; outros erros também (para stack aparecer no UI).
    """
    def _decor(fn: Callable[..., Any]) -> Callable[..., Any]:
        mod = fn.__module__
        qual = f"{mod}.{fn.__name__}"
        @functools.wraps(fn)
        def _wrap(*args, **kwargs):
            _stdout_log("INFO", "step_start", step=step_name, func=qual)
            try:
                out = fn(*args, **kwargs)
                _stdout_log("INFO", "step_ok", step=step_name, func=qual)
                return out
            except AppError as ae:
                notify_error(f"[{step_name}] falhou em {qual}: {ae}", exc=ae, step=step_name)
                raise
            except Exception as ex:
                notify_error(f"[{step_name}] erro inesperado em {qual}", exc=ex, step=step_name)
                raise
        return _wrap
    return _decor
