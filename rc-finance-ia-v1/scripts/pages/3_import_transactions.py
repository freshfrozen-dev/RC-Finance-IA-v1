
import sys
from pathlib import Path

# PATH BOOTSTRAP
# Adiciona o diretório raiz do projeto ao sys.path para que os módulos possam ser encontrados
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import streamlit as st
from scripts.utils.db_utils import bulk_insert_transactions
from scripts.utils.importers import parse_csv, parse_ofx
from scripts.utils.ui_components import action_toast

def import_transactions_page():
    st.set_page_config(page_title="Importar Transações", page_icon="⬆️", layout="wide")

    # Gate de login
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if not st.session_state["logged_in"]:
        try:
            st.switch_page("login")
        except Exception:
            st.rerun()
        st.stop()

    # Injeção do CSS
    st.markdown("<link rel='stylesheet' href='assets/styles.css'>", unsafe_allow_html=True)

    st.title("Importar Transações")

    user_id = st.session_state['user_id']

    st.write("Selecione um arquivo CSV ou OFX para importar suas transações.")

    uploaded_file = st.file_uploader("Escolha um arquivo", type=["csv", "ofx"])

    if uploaded_file is not None:
        file_details = {"filename": uploaded_file.name, "filetype": uploaded_file.type, "filesize": uploaded_file.size}
        st.write(file_details)

        file_content = uploaded_file.getvalue().decode("utf-8")

        transactions_to_insert = []
        if uploaded_file.type == "text/csv":
            transactions_to_insert = parse_csv(file_content)
        elif uploaded_file.type == "application/x-ofx": # MIME type comum para OFX
            try:
                transactions_to_insert = parse_ofx(file_content)
                if not transactions_to_insert:
                    st.warning("Não foi possível processar o arquivo OFX. Verifique se a biblioteca 'ofxparse' está instalada e o arquivo é válido.")
            except ImportError:
                st.warning("A biblioteca 'ofxparse' não está instalada. A importação de OFX não está disponível.")
            except Exception as e:
                st.error(f"Erro ao importar OFX: {e}")
                transactions_to_insert = []
        else:
            st.error("Formato de arquivo não suportado.")

        if transactions_to_insert:
            st.write(f"Encontradas {len(transactions_to_insert)} transações para importar.")
            
            # Adicionar user_id a cada transação
            for t in transactions_to_insert:
                t['user_id'] = user_id

            # Exibir prévia das transações
            st.subheader("Prévia das Transações")
            st.dataframe(transactions_to_insert)

            if st.button("Confirmar Importação"):
                try:
                    with st.spinner("Importando transações..."):
                        result = bulk_insert_transactions(user_id, transactions_to_insert)
                    st.success(
                        f"Importação concluída! Inseridas: {result['inserted']}, Duplicadas: {result['duplicates']}, Falhas: {result['failed']}"
                    )
                    st.toast("Importação realizada com sucesso!", icon="✅")
                except Exception as e:
                    st.error(f"Erro ao importar transações: {e}")
        elif uploaded_file.type != "text/csv" and uploaded_file.type != "application/x-ofx":
            st.error("Nenhuma transação válida encontrada no arquivo ou formato não suportado.")

import_transactions_page()

st.markdown(
    """
    <style>
      .rc-mic{position:fixed;right:24px;bottom:24px;z-index:1000}
      .rc-mic>a{display:inline-flex;align-items:center;justify-content:center;
        width:56px;height:56px;border-radius:50%;background:#7C3AED;color:#fff;
        box-shadow:0 8px 24px rgba(0,0,0,.35);text-decoration:none;font-size:24px}
      .rc-mic>a:hover{filter:brightness(1.08)}
    </style>
    <div class=\"rc-mic\"><a href=\"/voz\" target=\"_self\" title=\"Comandos de Voz\">🎤</a></div>
    """,
    unsafe_allow_html=True,
)

