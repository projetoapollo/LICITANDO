# app_turbo.py
import os
import sys
import time
from io import BytesIO

import streamlit as st
import pandas as pd

# =========================
# Configurações / Constantes
# =========================
DEFAULT_FILTRO_MINIMO = 0.70          # 70%
LOGO_CAMINHO = "static/logo_apolari.png"  # se existir, coloca no topo/Excel

st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="🧠")

# ====== Funções visuais utilitárias ======
def tocar_ping():
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


def header():
    left, right = st.columns([1, 5])
    with left:
        if os.path.exists(LOGO_CAMINHO):
            st.image(LOGO_CAMINHO, use_container_width=True)
    with right:
        st.title("Sistema Appolari Turbo V3.2")
        st.success("Aplicação carregada com sucesso! ✅")


def diagnostico():
    with st.expander("Diagnóstico rápido (pode recolher)"):
        st.write("Python:", sys.version.split()[0])
        st.code(
            {k: os.environ[k] for k in ("PYTHONUNBUFFERED", "STREAMLIT_SERVER_HEADLESS") if k in os.environ},
            language="json",
        )


# ====== Estado de sessão robusto ======
if "run_id" not in st.session_state:
    st.session_state.run_id = 0
if "ultimo_df" not in st.session_state:
    st.session_state.ultimo_df = None
if "ultimo_excel" not in st.session_state:
    st.session_state.ultimo_excel = None


# ====== UI principal ======
header()
diagnostico()
st.divider()

uploaded = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])

filtro_min = (
    st.slider(
        "Filtro mínimo de similaridade (%)",
        min_value=50,
        max_value=90,
        value=int(DEFAULT_FILTRO_MINIMO * 100),
        help="Itens com score abaixo disso são descartados.",
    )
    / 100.0
)

rodar = st.button("▶️ Rodar Sistema Appolari", type="primary")

if uploaded is not None:
    st.success("✅ PDF carregado com sucesso!")

# ====== Execução ======
if rodar:
    if uploaded is None:
        st.warning("Envie um PDF antes de rodar.")
        st.stop()

    # incrementa ID para este run
    st.session_state.run_id += 1
    this_run = st.session_state.run_id

    # Lê bytes do arquivo imediatamente (para o buffer não “sumir” num rerun)
    try:
        pdf_bytes = uploaded.getvalue()
        if not pdf_bytes:
            st.error("O arquivo PDF veio vazio. Tente reenviar.")
            st.stop()
    except Exception as e:
        st.error("Falha ao ler o PDF.")
        st.exception(e)
        st.stop()

    # Painel de status persistente
    with st.status("Iniciando...", expanded=True) as status:
        try:
            status.update(label="Lendo PDF e extraindo itens...", state="running")
            # Import adiado só na hora de rodar (evita custo em reruns)
            from script_principal_turbo import processar_pdf

            # Passo o conteúdo em BYTES — seu parser pode receber bytes
            df = processar_pdf(BytesIO(pdf_bytes))
            if df is None or df.empty:
                status.update(
                    label="Nenhum item encontrado no PDF.",
                    state="warning",
                )
                st.stop()

            # Garante coluna solicitada
            if "QUANT PESQ (1)" not in df.columns:
                df["QUANT PESQ (1)"] = 1

            status.update(label="Pesquisando preços e fontes...", state="running")
            from price_search import buscar_precos

            # ATENÇÃO: a sua função usa o nome do parâmetro 'similaridade_minima'
            valores_medios, mercados, fontes = buscar_precos(
                df, similaridade_minima=filtro_min
            )
            df["Valor médio do produto"] = valores_medios
            df["Descrição localidade / Mercado"] = mercados
            df["Fontes"] = fontes
            if "Status" not in df.columns:
                df["Status"] = "OK"

            status.update(label="Gerando planilha Excel...", state="running")
            output_excel = BytesIO()
            with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Cotacao_Final")
                # Tenta inserir logo (se existir)
                try:
                    from openpyxl.drawing.image import Image as XLImage

                    ws = writer.book["Cotacao_Final"]
                    if os.path.exists(LOGO_CAMINHO):
                        img = XLImage(LOGO_CAMINHO)
                        ws.add_image(img, "A1")
                except Exception:
                    pass
            output_excel.seek(0)

            # Guarda no estado para reapresentar sem rerodar
            st.session_state.ultimo_df = df
            st.session_state.ultimo_excel = output_excel.getvalue()

            status.update(label="Processamento concluído com sucesso!", state="complete")
            st.success("✅ Pronto!")

        except Exception as e:
            status.update(label="Falha no processamento.", state="error")
            st.error("❌ Erro ao processar. Veja os detalhes abaixo:")
            st.exception(e)
            st.stop()

    # Renderiza resultados ao fim (mesmo se a página rerender)
    if st.session_state.ultimo_df is not None:
        st.dataframe(st.session_state.ultimo_df, use_container_width=True, height=420)
        st.download_button(
            "📥 Baixar planilha gerada",
            data=st.session_state.ultimo_excel,
            file_name="cotacao_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        tocar_ping()

# Se não clicou em rodar mas já tem resultado em memória, mostra
elif st.session_state.ultimo_df is not None:
    st.info("Último resultado processado nesta sessão:")
    st.dataframe(st.session_state.ultimo_df, use_container_width=True, height=420)
    st.download_button(
        "📥 Baixar última planilha gerada",
        data=st.session_state.ultimo_excel,
        file_name="cotacao_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    # topo do arquivo
from observability import guard, AppError

@guard("extrair_itens_pdf")
def processar_pdf(pdf_stream) -> "pd.DataFrame":
    # ... SE já existe a função com esse nome, só adicione o @guard acima dela.
    # Exemplo de validação amigável:
    import pandas as pd
    df = _sua_logica_que_cria_df(pdf_stream)  # placeholder
    if df is None or df.empty:
        raise AppError("Nenhum item encontrado no PDF.",
                       hint="Confira se o PDF tem tabela legível.",
                       code="EMPTY_PDF")
    # garanta colunas base se desejar
    return df


