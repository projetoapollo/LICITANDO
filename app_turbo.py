# app_turbo.py
import os
import sys
from io import BytesIO
import streamlit as st
import pandas as pd

# ---------------- Config ----------------
DEFAULT_FILTRO_MINIMO = 0.70   # 70%
LOGO_CAMINHO = "static/logo_apolari.png"  # se existir, vai no Excel

st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="🧠")

# ---------------- Cabeçalho ----------------
col_logo, col_titulo = st.columns([1, 5])
with col_logo:
    if os.path.exists(LOGO_CAMINHO):
        st.image(LOGO_CAMINHO, use_container_width=True)
with col_titulo:
    st.title("Sistema Appolari Turbo V3.2")
    st.success("Aplicação carregada com sucesso! ✅")

with st.expander("Diagnóstico rápido (pode recolher)"):
    st.write("Python:", sys.version.split()[0])
    st.code(
        {k: os.environ[k] for k in ("PYTHONUNBUFFERED", "STREAMLIT_SERVER_HEADLESS") if k in os.environ},
        language="json",
    )

# ---------------- Módulos do projeto ----------------
from script_principal_turbo import processar_pdf   # retorna DataFrame base
from price_search import buscar_precos             # retorna (valores_medios, mercados, fontes)

st.divider()

# ---------------- UI principal ----------------
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"], key="pdf_upload")

filtro_min = st.slider(
    "Filtro mínimo de similaridade (%)",
    min_value=50, max_value=90, value=int(DEFAULT_FILTRO_MINIMO * 100),
    help="Itens com score abaixo disso são descartados na busca de preço.",
) / 100.0

btn = st.button("▶️ Rodar Sistema Appolari", type="primary")

if uploaded_file is not None:
    st.success("✅ PDF carregado com sucesso!")

# Placeholders estáveis (evita removeChild)
ph_status = st.empty()
ph_progress = st.empty()
ph_table = st.empty()
ph_download = st.empty()

def set_progress(step: int, total: int, label: str):
    pct = int(max(0, min(100, (step / total) * 100)))
    # usamos sempre o mesmo placeholder
    ph_progress.progress(pct, text=f"{label} ({pct}%)")

if btn and uploaded_file is not None:
    TOTAL = 4
    try:
        with st.status("Iniciando…", state="running") as status:
            # 1) Ler/parsear PDF
            set_progress(1, TOTAL, "Lendo PDF e extraindo itens")
            status.write("📄 Etapa 1/4 — lendo PDF…")
            df = processar_pdf(uploaded_file)

            if df is None or df.empty:
                ph_progress.progress(25, text="Lendo PDF e extraindo itens (25%)")
                st.warning("Nenhum item encontrado no PDF.")
                status.update(label="Processo encerrado", state="error")
                st.stop()

            # 2) Garantir coluna QUANT PESQ (1)
            set_progress(2, TOTAL, "Preparando colunas")
            status.write("🧰 Etapa 2/4 — preparando colunas…")
            if "QUANT PESQ (1)" not in df.columns:
                df["QUANT PESQ (1)"] = 1

            # 3) Buscar preços e fontes
            set_progress(3, TOTAL, "Pesquisando preços e fontes")
            status.write("🔎 Etapa 3/4 — pesquisando preços…")
            valores_medios, mercados, fontes = buscar_precos(df, min_score=filtro_min)
            df["Valor médio do produto"] = valores_medios
            df["Descrição localidade / Mercado"] = mercados
            df["Fontes"] = fontes
            if "Status" not in df.columns:
                df["Status"] = "OK"

            # 4) Gerar Excel
            set_progress(4, TOTAL, "Gerando planilha Excel")
            status.write("📦 Etapa 4/4 — gerando Excel…")
            output_excel = BytesIO()
            with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Cotacao_Final")
                try:
                    from openpyxl.drawing.image import Image as XLImage
                    ws = writer.book["Cotacao_Final"]
                    if os.path.exists(LOGO_CAMINHO):
                        img = XLImage(LOGO_CAMINHO)
                        ws.add_image(img, "A1")
                except Exception:
                    pass
            output_excel.seek(0)

            # Mostrar resultado
            ph_table.dataframe(df, use_container_width=True, height=420)
            ph_download.download_button(
                "📥 Baixar planilha gerada",
                data=output_excel,
                file_name="cotacao_final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            status.update(label="✅ Processamento concluído!", state="complete")

    except Exception as e:
        # não removemos nada do DOM; só atualizamos conteúdo
        st.error("❌ Erro ao processar.")
        st.exception(e)
elif btn and uploaded_file is None:
    st.info("Envie um PDF e clique em **Rodar Sistema Appolari** para começar.")
