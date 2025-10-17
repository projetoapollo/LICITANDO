# =========================
# app_turbo.py  (versão revisada)
# =========================
from __future__ import annotations

import io
import os
import sys
import time

import pandas as pd
import streamlit as st

from script_principal_turbo import processar_pdf
from price_search import buscar_precos

# -------------------------
# observabilidade opcional (fallback silencioso)
# -------------------------
try:
    from observability import notify_error  # type: ignore
except Exception:  # pragma: no cover
    def notify_error(_step: str, exc: BaseException | None = None, **_kwargs) -> None:
        # no-op
        return None

# -------------------------
# constantes
# -------------------------
DEFAULT_FILTRO_MINIMO = 0.70  # 70%

# -------------------------
# configuração da página
# -------------------------
st.set_page_config(
    page_title="Sistema Appolari Turbo",
    page_icon="⚙️",
    layout="wide",
)

# -------------------------
# helpers
# -------------------------
def tocar_ping() -> None:
    """Feedback visual rápido ao concluir."""
    try:
        st.toast("Processo concluído!", icon="✅")
    except Exception:
        pass

def set_session_default(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value

# -------------------------
# CSS mínimo (injeta uma vez)
# -------------------------
if "ui_injetada" not in st.session_state:
    st.markdown(
        """
        <style>
          .site-content { margin: 0 auto; }
          header { margin: .75rem 0; }
          main   { margin-bottom: 1rem; }
          footer { padding-bottom: 1.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state.ui_injetada = True

# -------------------------
# estado inicial (preservado entre reruns)
# -------------------------
set_session_default("pdf_bytes", None)
set_session_default("rodar", False)
set_session_default("log", [])
set_session_default("df_itens", None)
set_session_default("resultado", None)
set_session_default("filtro_min", DEFAULT_FILTRO_MINIMO)

# -------------------------
# título + diagnóstico (pode recolher)
# -------------------------
st.title("Sistema Appolari Turbo v3.2")
with st.expander("Diagnóstico rápido (pode recolher)", expanded=False):
    st.write("Python:", sys.version.split()[0])
    st.json({"cwd": os.getcwd(), "time": time.strftime("%Y-%m-%d %H:%M:%S")})

# -------------------------
# UI principal
# -------------------------
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.getvalue()
    st.success("✅ PDF carregado com sucesso!")

filtro_pct = st.slider(
    "Filtro mínimo de similaridade (%)",
    min_value=50,
    max_value=100,
    value=int(st.session_state.filtro_min * 100),
    help="Itens com score abaixo disso são descartados na busca de preço.",
)
st.session_state.filtro_min = filtro_pct / 100.0

if st.button("🚀 Rodar Sistema Appolari", type="primary"):
    if st.session_state.pdf_bytes:
        st.session_state.rodar = True
        st.session_state.log = []
    else:
        st.warning("Envie um PDF antes de rodar.")

# -------------------------
# execução
# -------------------------
if st.session_state.rodar:
    progress = st.progress(0, text="Lendo PDF e extraindo itens...")
    try:
        # 1) ler PDF -> DataFrame
        df = processar_pdf(io.BytesIO(st.session_state.pdf_bytes))
        progress.progress(20, text="PDF lido. Normalizando/checando itens...")

        if df is None or df.empty:
            st.warning("Nenhum item encontrado no PDF.")
            st.session_state.rodar = False
        else:
            st.session_state.log.append(
                f"[{time.strftime('%H:%M:%S')}] Itens extraídos: {len(df)}"
            )
            # garantir colunas opcionais
            if "QUANT PESQ (1)" not in df.columns:
                df["QUANT PESQ (1)"] = 1
            if "Status" not in df.columns:
                df["Status"] = "OK"

            # 2) buscar preços
            progress.progress(55, text="Buscando preços no catálogo...")
            valores_medios, mercados, fontes = buscar_precos(
                df,
                similaridade_minima=st.session_state.filtro_min,
            )

            # 3) montar resultado
            progress.progress(85, text="Montando resultado...")
            df_out = df.copy()
            df_out["Valor médio do produto"] = valores_medios
            df_out["Descrição localidade / Mercado"] = mercados
            df_out["Fontes"] = fontes

            st.session_state.resultado = df_out
            progress.progress(100, text="Concluído!")
            st.success("✅ Processamento concluído com sucesso.")
            tocar_ping()

    except Exception as exc:
        notify_error("execucao_app", exc=exc)
        st.error("❌ Falha no processamento. Detalhes abaixo.")
        st.exception(exc)
        st.session_state.log.append(f"[{time.strftime('%H:%M:%S')}] ERRO: {exc!r}")
    finally:
        st.session_state.rodar = False

# -------------------------
# resultados
# -------------------------
if st.session_state.resultado is not None:
    st.markdown("---")
    st.subheader("Resultado da cotação")
    st.dataframe(st.session_state.resultado, use_container_width=True)

    # download em Excel
    try:
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            st.session_state.resultado.to_excel(
                writer, index=False, sheet_name="Cotacao_Final"
            )
        st.download_button(
            label="📥 Baixar planilha gerada",
            data=bio.getvalue(),
            file_name="cotacao_final.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    except Exception as exc:
        notify_error("gerar_excel", exc=exc)
        st.info("Não foi possível gerar o Excel agora.")

# mensagem inicial
if not st.session_state.pdf_bytes and st.session_state.resultado is None:
    st.info("Envie um PDF e clique em **Rodar Sistema Appolari** para começar.")
