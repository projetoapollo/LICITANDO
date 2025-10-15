# app_turbo.py
import os
import sys
from io import BytesIO
import streamlit as st
import pandas as pd

# ========= CONFIG =========
DEFAULT_FILTRO_MINIMO = 0.70  # 70%
LOGO_CAMINHO = "static/logo_apolari.png"  # coloque sua logo aqui

# ========= AJUDANTES VISUAIS =========
def tocar_ping() -> None:
    """Toca um 'ping' leve quando o processamento terminar."""
    beep_b64 = (
        "UklGRmQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAEQAAABkZGRkZGZmZmZm"
        "ZmdnZ2dnZ2ZmZmZmZGRkZGRkZGRkZGRkZGRkZmdnZ2dnZ2dnZ2ZmZmZmZGRkZGRkZGRkZGRkZGRk"
    )
    html = f"""
    <audio autoplay style="display:none">
      <source src="data:audio/wav;base64,{beep_b64}" type="audio/wav">
    </audio>
    """
    st.markdown(html, unsafe_allow_html=True)


# ---- Barra de progresso simples ----
class BarraProgresso:
    def __init__(self, total_passos: int = 4):
        self.total = max(1, int(total_passos))
        self.atual = 0
        self._bar = st.progress(0, text="Iniciando...")

    def step(self, msg: str):
        self.atual += 1
        pct = int((self.atual / self.total) * 100)
        pct = min(max(pct, 0), 100)
        # ATUALIZAÇÃO correta na Streamlit 1.37: use .progress() (não .update())
        self._bar.progress(pct, text=f"{msg} ({pct}%)")


# ========= LAYOUT INICIAL =========
st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="🧠")

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

# ========= IMPORTS DOS MÓDULOS DO PROJETO =========
from script_principal_turbo import processar_pdf      # retorna DataFrame base
from price_search import buscar_precos                # retorna (valores_medios, mercados, fontes)

st.divider()

# ========= INTERFACE PRINCIPAL =========
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])

# Slider do filtro de similaridade (50% a 90%, padrão 70%)
filtro_min = (
    st.slider(
        "Filtro mínimo de similaridade (%)",
        min_value=50,
        max_value=90,
        value=int(DEFAULT_FILTRO_MINIMO * 100),
        help="Itens com score abaixo disso são descartados na busca de preço.",
    )
    / 100.0
)

btn = st.button("▶️ Rodar Sistema Appolari", type="primary")

if uploaded_file is not None:
    st.success("✅ PDF carregado com sucesso!")

if btn and uploaded_file is not None:
    barra = BarraProgresso(total_passos=4)

    try:
        # ===== 1) LER / PARSEAR PDF =====
        barra.step("Lendo PDF e extraindo itens...")
        # Pega os bytes e garante um buffer "zerado"
        file_bytes = uploaded_file.getvalue()
        df = processar_pdf(BytesIO(file_bytes))

        # Se por algum motivo vier vazio, tenta novamente
        if df is None or df.empty:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
            df = processar_pdf(BytesIO(file_bytes))

        if df is None or df.empty:
            st.warning("Nenhum item encontrado no PDF.")
            st.stop()

        # ===== 2) GARANTIR COLUNAS =====
        barra.step("Preparando colunas…")
        # QUANT PESQ (1) sempre = 1, para pesquisa de preço unitário
        if "QUANT PESQ (1)" not in df.columns:
            df["QUANT PESQ (1)"] = 1

        # Status default
        if "Status" not in df.columns:
            df["Status"] = "OK"

        # ===== 3) BUSCAR PREÇOS =====
        barra.step("Pesquisando preços e fontes…")
        valores_medios, mercados, fontes = buscar_precos(df, min_score=filtro_min)
        df["Valor médio do produto"] = valores_medios
        df["Descrição localidade / Mercado"] = mercados
        df["Fontes"] = fontes

        # ===== 4) GERAR EXCEL =====
        barra.step("Gerando planilha Excel…")
        output_excel = BytesIO()
        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Cotacao_Final")

            # tenta inserir a logo na planilha
            try:
                from openpyxl.drawing.image import Image as XLImage

                ws = writer.book["Cotacao_Final"]
                if os.path.exists(LOGO_CAMINHO):
                    img = XLImage(LOGO_CAMINHO)
                    ws.add_image(img, "A1")
            except Exception:
                # se não conseguir, segue sem a imagem
                pass

        output_excel.seek(0)

        st.success("✅ Processamento concluído com sucesso!")
        st.dataframe(df, use_container_width=True, height=420)

        st.download_button(
            "📥 Baixar planilha gerada",
            data=output_excel,
            file_name="cotacao_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        tocar_ping()

    except Exception as e:
        st.error("❌ Erro ao processar.")
        st.exception(e)
else:
    st.info("Envie um PDF e clique em **Rodar Sistema Appolari** para começar.")
