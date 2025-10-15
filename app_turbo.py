# app_turbo.py
import os, sys
from io import BytesIO
import streamlit as st
import pandas as pd

# =========================
# Configurações gerais
# =========================
DEFAULT_FILTRO_MINIMO = 0.70   # 70%
LOGO_CAMINHO = "static/logo_apolari.png"

st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="🧠")

# =========================
# Observabilidade mínima
# =========================
def notify_success(msg: str):
    st.success(msg)

def notify_error(msg: str, exc: Exception | None = None, step: str | None = None):
    cab = f"❌ {msg}"
    if step:
        cab += f" | etapa: {step}"
    st.error(cab)
    if exc is not None:
        st.exception(exc)

# =========================
# Barra de progresso simples
# =========================
class BarraProgresso:
    def __init__(self, total_passos: int = 4):
        self.total = max(1, int(total_passos))
        self.atual = 0
        self._bar = st.progress(0, text="Iniciando...")

    def step(self, msg: str):
        self.atual += 1
        pct = int((self.atual / self.total) * 100)
        pct = min(max(pct, 0), 100)
        # ATUALIZAÇÃO CORRETA (sem .update)
        self._bar.progress(pct, text=f"{msg} ({pct}%)")

# =========================
# “Ping” final
# =========================
def tocar_ping():
    beep_b64 = (
        "UklGRmQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAEQAAABkZGRkZGZmZmZm"
        "ZmdnZ2dnZ2ZmZmZmZGRkZGRkZGRkZGRkZGRkZmdnZ2dnZ2dnZ2ZmZmZmZGRkZGRkZGRkZGRkZGRk"
    )
    st.markdown(
        f"""<audio autoplay style="display:none">
        <source src="data:audio/wav;base64,{beep_b64}" type="audio/wav">
        </audio>""",
        unsafe_allow_html=True,
    )

# =========================
# Cabeçalho
# =========================
col_logo, col_titulo = st.columns([1, 5])
with col_titulo:
    st.title("Sistema Appolari Turbo V3.2")
    st.success("Aplicação carregada com sucesso! ✅")

with st.expander("Diagnóstico rápido (pode recolher)"):
    st.write("Python:", sys.version.split()[0])
    st.code(
        {k: os.environ[k] for k in ("PYTHONUNBUFFERED", "STREAMLIT_SERVER_HEADLESS") if k in os.environ},
        language="json",
    )

# =========================
# Imports dos módulos do projeto
# =========================
from script_principal_turbo import processar_pdf   # -> DataFrame
from price_search import buscar_precos             # -> (valores_medios, mercados, fontes)

st.divider()

# =========================
# UI principal
# =========================
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])

filtro_min = st.slider(
    "Filtro mínimo de similaridade (%)",
    min_value=50, max_value=90, value=int(DEFAULT_FILTRO_MINIMO * 100),
    help="Itens com score abaixo disso são descartados na busca de preço."
) / 100.0

btn = st.button("▶️ Rodar Sistema Appolari", type="primary")

if uploaded_file is not None:
    st.success("✅ PDF carregado com sucesso!")

# =========================
# Botão — pipeline completo
# =========================
if btn and uploaded_file is not None:
    try:
        barra = BarraProgresso(total_passos=4)

        # 1) Ler e parsear PDF
        barra.step("Lendo PDF e extraindo itens...")
        df = processar_pdf(uploaded_file)
        if df is None or df.empty:
            st.warning("Nenhum item encontrado no PDF.")
            st.stop()

        # 2) Garantir coluna de quantidade de pesquisa (1)
        barra.step("Preparando colunas...")
        if "QUANT PESQ (1)" not in df.columns:
            df["QUANT PESQ (1)"] = 1

        # 3) Buscar preços (nome do parâmetro CORRETO: similaridade_minima)
        barra.step("Pesquisando preços e fontes...")
        valores_medios, mercados, fontes = buscar_precos(
            df, similaridade_minima=filtro_min
        )
        df["Valor médio do produto"] = valores_medios
        df["Descrição localidade / Mercado"] = mercados
        df["Fontes"] = fontes
        if "Status" not in df.columns:
            df["Status"] = "OK"

        # 4) Gerar Excel com logo
        barra.step("Gerando planilha Excel...")
        output_excel = BytesIO()
        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Cotacao_Final")
            # Tenta inserir a logo; se falhar, segue o jogo
            try:
                from openpyxl.drawing.image import Image as XLImage
                ws = writer.book["Cotacao_Final"]
                if os.path.exists(LOGO_CAMINHO):
                    ws.add_image(XLImage(LOGO_CAMINHO), "A1")
            except Exception:
                pass
        output_excel.seek(0)

        # Sucesso FINAL (não usar finally para isso)
        st.dataframe(df, use_container_width=True, height=420)
        st.download_button(
            "📥 Baixar planilha gerada",
            data=output_excel,
            file_name="cotacao_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        notify_success("Pipeline concluído com sucesso.")
        tocar_ping()

    except Exception as e:
        # AQUI 'e' EXISTE — não dá NameError
        notify_error("Falha no processamento.", exc=e, step="app")
        st.stop()

elif btn and uploaded_file is None:
    st.warning("Envie um PDF antes de rodar.")
else:
    st.info("Envie um PDF e clique em **Rodar Sistema Appolari** para começar.")
