# =========================
# Sistema Appolari Turbo V3.2
# =========================
from __future__ import annotations

import io
import os
import sys
import time
from typing import Any, Callable

import pandas as pd
import streamlit as st

# observabilidade opcional (guard + notify_error com fallback seguro)
try:
    from observability import guard, notify_error  # type: ignore
except Exception:
    def guard(_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def _decor(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn
        return _decor

    def notify_error(_step: str, exc: BaseException | None = None, **_kw: Any) -> None:
        return None

from script_principal_turbo import processar_pdf
from price_search import buscar_precos

# =========================
# Constantes
# =========================
DEFAULT_FILTRO_MINIMO = 0.70  # 70%

# =========================
# Configuração da página
# =========================
st.set_page_config(
    page_title="Sistema Appolari Turbo",
    page_icon="⚙️",
    layout="wide",
)

# =========================
# Injeção mínima de CSS
# =========================
if "ui_injetada" not in st.session_state:
    st.markdown(
        """
        <style>
          .site-content { margin: 0 auto; }
          header { margin: .75rem 0; }
          main { margin-bottom: 1rem; }
          footer { padding-bottom: 1.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state.ui_injetada = True

# =========================
# Estado inicial persistente
# =========================
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "rodar" not in st.session_state:
    st.session_state.rodar = False
if "log" not in st.session_state:
    st.session_state.log = []
if "df_itens" not in st.session_state:
    st.session_state.df_itens = None
if "resultado" not in st.session_state:
    st.session_state.resultado = None

# =========================
# Título e diagnóstico rápido
# =========================
st.title("Sistema Appolari Turbo v3.2")
with st.expander("Diagnóstico rápido (pode recolher)", expanded=False):
    st.write("Python:", sys.version.split()[0])
    st.json({"cwd": os.getcwd(), "time": time.strftime("%Y-%m-%d %H:%M:%S")})

# =========================
# Interface principal
# =========================
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.getvalue()
    st.success("✅ PDF carregado com sucesso!")

filtro_min = st.slider(
    "Filtro mínimo de similaridade (%)",
    min_value=50,
    max_value=90,
    value=int(DEFAULT_FILTRO_MINIMO * 100),
    help="Itens com score abaixo disso são descartados na busca de preço.",
) / 100.0

if st.button("▶️ Rodar Sistema Appolari", type="primary"):
    if st.session_state.pdf_bytes:
        st.session_state.rodar = True
        st.session_state.log = []
    else:
        st.warning("Envie um PDF antes de rodar.")

# =========================
# Execução principal
# =========================
if st.session_state.rodar:
    try:
        st.info("⏳ Lendo PDF e extraindo itens…")
        df = processar_pdf(io.BytesIO(st.session_state.pdf_bytes))

        if df is None or df.empty:
            st.warning("⚠️ Nenhum item encontrado no PDF.")
            st.session_state.rodar = False
            st.stop()

        st.session_state.log.append(f"[{time.strftime('%H:%M:%S')}] Itens extraídos: {len(df)}")

        # Garante colunas obrigatórias
        if "QUANT PESQ (1)" not in df.columns:
            df["QUANT PESQ (1)"] = 1
        if "Status" not in df.columns:
            df["Status"] = "OK"

        st.info("🔎 Pesquisando preços e fontes…")
        valores_medios, mercados, fontes = buscar_precos(df, similaridade_minima=filtro_min)
        df["Valor médio do produto"] = valores_medios
        df["Descrição localidade / Mercado"] = mercados
        df["Fontes"] = fontes

        st.info("📊 Gerando planilha Excel…")
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Cotacao_Final")
        output_excel.seek(0)

        st.success("✅ Processamento concluído com sucesso!")
        st.dataframe(df, use_container_width=True, height=420)
        st.download_button(
            "📥 Baixar planilha gerada",
            data=output_excel,
            file_name="cotacao_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        notify_error("execucao_app", exc=e)
        st.error("❌ Falha no processamento. Veja detalhes abaixo.")
        st.exception(e)
        st.session_state.log.append(f"[{time.strftime('%H:%M:%S')}] ERRO: {repr(e)}")

    finally:
        st.session_state.rodar = False

else:
    st.info("Envie um PDF e clique em **Rodar Sistema Appolari** para começar.")
