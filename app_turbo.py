# app_turbo.py
import os, sys, io, time
import streamlit as st
import pandas as pd
from io import BytesIO

# ===== Config =====
DEFAULT_FILTRO_MINIMO = 0.70   # 70%
LOGO_CAMINHO = "static/logo_apolari.png"  # opcional (pasta static/)

# ===== Estado de sessão (evita “sumir” quando reroda) =====
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "rodar" not in st.session_state:
    st.session_state.rodar = False
if "log" not in st.session_state:
    st.session_state.log = []

# ===== Helpers visuais =====
def tocar_ping():
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

class BarraProgresso:
    def __init__(self, total_passos:int=4):
        self.total = max(1, int(total_passos))
        self.atual = 0
        self._bar = st.progress(0, text="Iniciando...")

    def step(self, msg:str):
        self.atual += 1
        pct = int((self.atual / self.total) * 100)
        pct = min(max(pct, 0), 100)
        self._bar.progress(pct, text=f"{msg} ({pct}%)")

# ===== Layout inicial =====
st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="🧠")
st.title("Sistema Appolari Turbo V3.2")
st.success("Aplicação carregada com sucesso! ✅")

with st.expander("Diagnóstico rápido (pode recolher)", expanded=False):
    st.write("Python:", sys.version.split()[0])
    st.json({k: os.environ.get(k) for k in ("PYTHONUNBUFFERED","STREAMLIT_SERVER_HEADLESS")})
    if st.session_state.log:
        st.code("\n".join(st.session_state.log))

# ===== Import dos módulos da casa =====
from script_principal_turbo import processar_pdf
from price_search import buscar_precos  # assinatura: (df, similaridade_minima=0.7)

st.divider()

# ===== UI principal =====
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.getvalue()
    st.success("✅ PDF carregado com sucesso!")

filtro_min = st.slider(
    "Filtro mínimo de similaridade (%)",
    min_value=50, max_value=90, value=int(DEFAULT_FILTRO_MINIMO * 100),
    help="Itens com score abaixo disso são descartados na busca de preço."
) / 100.0

if st.button("▶️ Rodar Sistema Appolari", type="primary"):
    if st.session_state.pdf_bytes:
        st.session_state.rodar = True
        st.session_state.log = []
    else:
        st.warning("Envie um PDF antes de rodar.")

# ===== EXECUÇÃO =====
if st.session_state.rodar:
    barra = BarraProgresso(total_passos=4)
    try:
        barra.step("Lendo PDF e extraindo itens…")
        df = processar_pdf(io.BytesIO(st.session_state.pdf_bytes))
        if df is None or df.empty:
            st.warning("Nenhum item encontrado no PDF.")
            st.session_state.rodar = False
            st.stop()

        st.session_state.log.append(f"[{time.strftime('%H:%M:%S')}] Itens extraídos: {len(df)}")

        barra.step("Preparando colunas…")
        if "QUANT PESQ (1)" not in df.columns:
            df["QUANT PESQ (1)"] = 1
        if "Status" not in df.columns:
            df["Status"] = "OK"

        barra.step("Pesquisando preços e fontes…")
        valores_medios, mercados, fontes = buscar_precos(df, similaridade_minima=filtro_min)
        df["Valor médio do produto"] = valores_medios
        df["Descrição localidade / Mercado"] = mercados
        df["Fontes"] = fontes

        barra.step("Gerando planilha Excel…")
        output_excel = BytesIO()
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
        tocar_ping()
    except Exception as e:
        st.error("❌ Falha no processamento. Veja detalhes abaixo.")
        st.exception(e)
        st.session_state.log.append(f"[{time.strftime('%H:%M:%S')}] ERRO: {repr(e)}")
    finally:
        st.session_state.rodar = False
else:
    st.info("Envie um PDF e clique em **Rodar Sistema Appolari** para começar.")
