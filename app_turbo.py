# app_turbo.py
import os
import streamlit as st

# ==============================
# CONFIGURAÇÕES INICIAIS
# ==============================
st.set_page_config(
    page_title="Appolari Turbo IA",
    layout="centered",
    page_icon="🧠",
)

st.title("🛠️ Sistema Appolari Turbo V3.2")
st.success("Aplicação carregada com sucesso! ✅")

# ==============================
# IMPORTAÇÃO DO MÓDULO PRINCIPAL
# ==============================
processamento_disponivel = False
processar_pdf = None

try:
    # O script_principal_turbo.py precisa estar no mesmo repositório
    from script_principal_turbo import processar_pdf  # type: ignore
    processamento_disponivel = True
except Exception as e:
    processamento_disponivel = False
    st.warning("⚠️ Módulo principal não encontrado no servidor Render.")
    with st.expander("Detalhe técnico (para depuração)"):
        st.code(repr(e), language="python")

st.divider()

# ==============================
# INTERFACE PRINCIPAL
# ==============================
uploaded_file = st.file_uploader(
    "📄 Envie o PDF de cotação",
    type=["pdf"],
    help="Envie o arquivo PDF que contém a cotação para processarmos.",
)

if uploaded_file is not None:
    st.success("✅ PDF carregado com sucesso!")

    if not processamento_disponivel:
        st.error("O módulo `script_principal_turbo.py` não pôde ser carregado nesta instância Render.")
        st.info("Verifique se o arquivo existe no repositório e se o import está correto.")
    else:
        # Só mostra o botão quando podemos de fato processar
        if st.button("▶️ Rodar Sistema Appolari"):
            try:
                with st.spinner("⏳ Processando... aguarde alguns instantes..."):
                    # Espera-se que processar_pdf(retorne) (df, output_excel_bytes) OU (df, path_arquivo)
                    saida = processar_pdf(uploaded_file)

                # Normaliza a saída para suportar diferentes formatos
                df = None
                output_data = None
                output_name = "cotacao_final.xlsx"

                if isinstance(saida, tuple) and len(saida) >= 2:
                    df, output = saida[0], saida[1]
                    # Caso o segundo item seja bytes ou caminho de arquivo
                    if isinstance(output, (bytes, bytearray)):
                        output_data = output
                    elif isinstance(output, str) and os.path.exists(output):
                        # Lê o arquivo como bytes
                        with open(output, "rb") as fh:
                            output_data = fh.read()
                        # Tenta usar o nome do arquivo real
                        output_name = os.path.basename(output) or output_name
                    else:
                        # Se for outro tipo qualquer, tenta converter para bytes se possível
                        try:
                            output_data = bytes(output)
                        except Exception:
                            output_data = None
                else:
                    # Se a função devolver apenas bytes/arquivo
                    if isinstance(saida, (bytes, bytearray)):
                        output_data = saida
                    elif isinstance(saida, str) and os.path.exists(saida):
                        with open(saida, "rb") as fh:
                            output_data = fh.read()
                        output_name = os.path.basename(saida) or output_name

                st.success("✅ Processamento concluído com sucesso!")

                if df is not None:
                    st.dataframe(df, use_container_width=True)

                if output_data:
                    st.download_button(
                        "⬇️ Baixar planilha gerada",
                        data=output_data,
                        file_name=output_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.info(
                        "O processamento terminou, mas não recebi um conteúdo de planilha para download. "
                        "Confira a função `processar_pdf` para garantir que ela retorne os bytes do Excel ou o caminho do arquivo."
                    )

            except Exception as e:
                st.error("❌ Erro ao processar.")
                with st.expander("Ver detalhes do erro"):
                    st.code(repr(e), language="python")

else:
    st.info("📥 Envie um arquivo PDF para começar.")

st.divider()
st.caption("Desenvolvido por Pai Appolari e Filho Coop 💚")
