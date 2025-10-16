# app_turbo.py
# -------------------------------
# App Streamlit: LICITANDO Turbo
# Fluxo: PDF -> parser -> busca preços -> Excel (com logo) -> download
# -------------------------------

from __future__ import annotations

import os
import time
from io import BytesIO
from typing import Optional, Tuple, List

import streamlit as st
import pandas as pd

# Imports "da casa" DEVEM ficar no topo (corrige E402 no CI)
from script_principal_turbo import processar_pdf
from price_search import buscar_precos  # assinatura: (df, min_score=0.7)

# Tentar utilitários de observabilidade (opcional)
try:
    from observability import notify_error  # type: ignore
except Exception:  # fallback no-op
    def notify_error(msg: str, exc: Optional[BaseException] = None) -> None:
        st.error(msg)
        if exc:
            st.exception(exc)

# Excel (openpyxl) e imagem (logo)
try:
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
except Exception as _exc:
    notify_error(
        "Pacote 'openpyxl' não encontrado. Verifique seu requirements.txt (openpyxl).",
        _exc,
    )
    raise

# Caminhos padrão
LOGO_CAMINHO = "static/logo_apolari.png"
CATALOGO_ARQ = "data/catalogo_precos.csv"

# --------------------------------------------------------------------
# Compat: Streamlit < 1.22.0 (st.divider não existe nessas versões)
# --------------------------------------------------------------------
def safe_divider() -> None:
    if hasattr(st, "divider"):
        st.divider()
    else:
        st.markdown("---")


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _garante_colunas_minimas(df: pd.DataFrame) -> pd.DataFrame:
    """Garante as colunas que o fluxo precisa após o parser."""
    colunas_necessarias = [
        "Código PDF",
        "Descrição resumida PDF",
        "Unidade",
        "Quantidade",
    ]
    for c in colunas_necessarias:
        if c not in df.columns:
            df[c] = ""

    # força coluna QUANT PESQ (1) = 1
    if "QUANT PESQ (1)" not in df.columns:
        df["QUANT PESQ (1)"] = 1

    return df


def _gerar_excel(df_final: pd.DataFrame, logo_path: str = LOGO_CAMINHO) -> bytes:
    """
    Gera um Excel em memória com aba 'Cotacao_Final' e aplica logo (se existir).
    Retorna bytes do arquivo .xlsx.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotacao_Final"

    # escreve cabeçalhos
    ws.append(list(df_final.columns))

    # escreve linhas
    for _, row in df_final.iterrows():
        ws.append(list(row.values))

    # tenta inserir logo
    try:
        if logo_path and os.path.exists(logo_path):
            img = XLImage(logo_path)
            # posiciona a logo no canto superior (A1) sem quebrar o layout
            ws.add_image(img, "A1")
    except Exception as exc:
        # não falha o app por causa de logo
        notify_error("Não foi possível aplicar a logo ao Excel (seguimos sem logo).", exc)

    # salva em bytes
    buff = BytesIO()
    wb.save(buff)
    buff.seek(0)
    return buff.read()


def _aplicar_ping() -> None:
    """Toca um 'ping' simples ao finalizar (se disponível)."""
    try:
        # 440 Hz senoide rápida embutida (opcionalmente você pode usar st.audio de um arquivo)
        import numpy as np

        sr = 22050
        t = np.linspace(0, 0.15, int(sr * 0.15), endpoint=False)
        wave = 0.2 * np.sin(2 * np.pi * 880 * t)  # 880 Hz
        st.audio(wave, sample_rate=sr)
    except Exception:
        # como fallback, um celebrate visual
        st.balloons()


# --------------------------------------------------------------------
# UI
# --------------------------------------------------------------------
st.set_page_config(page_title="LICITANDO Turbo", page_icon="⚡", layout="wide")
st.title("⚡ Sistema Appolari Turbo V3.2")
st.caption("PDF → Itens → Busca de preços → Excel com logo")

safe_divider()

with st.sidebar:
    st.header("Configurações")
    sim_pct = st.slider("Filtro mínimo de similaridade (%)", min_value=50, max_value=90, value=70, step=1)
    min_score = sim_pct / 100.0
    st.write(f"Similaridade mínima: **{sim_pct}%**")

arquivo_pdf = st.file_uploader("Envie o PDF (um arquivo)", type=["pdf"])

col1, col2 = st.columns([1, 3])
with col1:
    iniciar = st.button("🚀 Processar")
with col2:
    st.info(
        "Fluxo: **ler PDF → preparar colunas → pesquisar preços → gerar Excel**.\n"
        "Ao final você poderá **baixar** a planilha.",
        icon="ℹ️",
    )

safe_divider()

barra = st.progress(0, text="Aguardando…")

# --------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------
if iniciar:
    if not arquivo_pdf:
        st.warning("Envie um PDF para começar.", icon="⚠️")
    else:
        try:
            etapa = "Lendo PDF"
            barra.progress(5, text=f"{etapa}…")
            time.sleep(0.1)

            # 1) Parser PDF -> DataFrame base
            df_base = processar_pdf(arquivo_pdf)
            if not isinstance(df_base, pd.DataFrame) or df_base.empty:
                raise RuntimeError("Parser retornou DataFrame vazio.")

            # 2) Garante colunas
            etapa = "Preparando colunas"
            barra.progress(25, text=f"{etapa}…")
            df_base = _garante_colunas_minimas(df_base)

            # 3) Busca de preços
            etapa = "Pesquisando preços"
            barra.progress(55, text=f"{etapa} (catálogo interno: {CATALOGO_ARQ})…")
            valores, mercados, fontes = buscar_precos(df_base, min_score=min_score)

            # 4) Monta DF final para Excel
            etapa = "Gerando Excel"
            barra.progress(80, text=f"{etapa}…")

            df_out = df_base.copy()
            # nomes seguindo seu resumo
            df_out["Valor médio do produto"] = valores
            df_out["Mercado"] = mercados
            df_out["Fontes"] = fontes

            xlsx_bytes = _gerar_excel(df_out, LOGO_CAMINHO)

            barra.progress(100, text="Concluído!")
            _aplicar_ping()

            st.success("Planilha gerada com sucesso! Faça o download abaixo.", icon="✅")
            st.download_button(
                label="⬇️ Baixar Excel (Cotacao_Final.xlsx)",
                data=xlsx_bytes,
                file_name="Cotacao_Final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except Exception as exc:
            notify_error("Ops! Ocorreu um erro durante o processamento.", exc)
        finally:
            time.sleep(0.05)
