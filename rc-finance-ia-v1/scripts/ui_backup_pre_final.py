from utils.ai_classifier import classify_transaction
import pandas as pd
import matplotlib.pyplot as plt
from sqlite_utils import Database
from datetime import date
import time
import streamlit as st


# 1. Conexão e configuração
db = Database(DB_PATH)
st.set_page_config(page_title="RC-Finance-IA", layout="wide")
st.sidebar.title("Menu")
page = st.sidebar.radio("Escolha", ["Transações", "Metas", "Dashboard"])

# 2. Transações
if page == "Transações":
    st.header("📄 Transações")
    st.dataframe(list(db["transactions"].rows))
    st.subheader("Editar transação")
    selected_id = st.selectbox("Escolha o ID da transação", [row["id"] for row in db["transactions"].rows])
    selected = db["transactions"].get(selected_id)

    with st.form("editar_transacao"):
        new_desc = st.text_input("Nova descrição", value=selected["description"])
        new_amount = st.number_input("Novo valor", value=selected["amount"])
        new_cat = st.text_input("Nova categoria", value=selected["category"])
        submitted = st.form_submit_button("Atualizar")

    if submitted:
        db["transactions"].update(selected_id, {
            "description": new_desc,
            "amount": new_amount,
            "category": new_cat
        })
        st.success("Atualizado com sucesso!")
        st.rerun()

# 3. Metas
elif page == "Metas":
    st.header("🎯 Metas")
    aba = st.radio("Gerenciar", ["Visualizar", "Cadastrar", "Importar", "Exportar"])
    if aba == "Visualizar":
        st.dataframe(list(db["goals"].rows))
        st.subheader("Editar transação")
    selected_id = st.selectbox("Escolha o ID da transação", [row["id"] for row in db["transactions"].rows])
    selected = db["transactions"].get(selected_id)

    with st.form("editar_transacao"):
        new_desc = st.text_input("Nova descrição", value=selected["description"])
        new_amount = st.number_input("Novo valor", value=selected["amount"])
        new_cat = st.text_input("Nova categoria", value=selected["category"])
        submitted = st.form_submit_button("Atualizar")
        st.subheader("Editar transação")
        selected_id = st.selectbox("Escolha o ID da transação", [row["id"] for row in db["transactions"].rows])
        selected = db["transactions"].get(selected_id)

with st.form("editar_transacao"):
    new_desc = st.text_input("Nova descrição", value=selected["description"])
    new_amount = st.number_input("Novo valor", value=selected["amount"])
    new_cat = st.text_input("Nova categoria", value=selected["category"])
    submitted = st.form_submit_button("Atualizar")

if submitted:
    db["transactions"].update(selected_id, {
        "description": new_desc,
        "amount": new_amount,
        "category": new_cat
    })
    st.success("Atualizado com sucesso!")
    st.rerun()

    if submitted:
        db["transactions"].update(selected_id, {
            "description": new_desc,
            "amount": new_amount,
            "category": new_cat
        })
        st.success("Atualizado com sucesso!")
        st.rerun()
    elif aba == "Cadastrar":
        st.info("Funcionalidade em construção")
    elif aba == "Importar":
        uploaded_file = st.file_uploader("Escolha um arquivo CSV ou JSON", type=["csv", "json"])

        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".json"):
                    df = pd.read_json(uploaded_file)

                st.write("Pré-visualização:", df.head())

                if st.button("Importar dados"):
                    for row in df.to_dict(orient="records"):
                        db["goals"].insert(row)
                    st.success("Importação concluída com sucesso!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar: {e}")
                st.subheader("OCR de imagem")
                ocr_file = st.file_uploader("Envie uma imagem ou PDF", type=["png", "jpg", "jpeg"])

                if ocr_file:
                    with open("temp_ocr.png", "wb") as f:
                        f.write(ocr_file.read())
                    from utils.ocr_reader import extract_text_from_image
                    texto_extraido = extract_text_from_image("temp_ocr.png")
                    st.text_area("Texto extraído:", texto_extraido, height=200)
    elif aba == "Exportar":
        st.info("Funcionalidade em construção")
        selected_id = st.selectbox("Escolha o ID da transação", [row["id"] for row in db["transactions"].rows])
        selected = db["transactions"].get(selected_id)

# 4. Dashboard
elif page == "Dashboard":
    st.header("📈 Dashboard Financeiro")
    df = pd.DataFrame(list(db["transactions"].rows))
    st.subheader
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        daily = df.groupby(df.index.date)['amount'].sum()
        fig, ax = plt.subplots()
        ax.plot(daily.index, daily.values)
        ax.set_title('Fluxo de Caixa Diário')
        ax.set_ylabel('Valor (R$)')
        st.pyplot(fig)
    if st.button("📊 Sugestões de Metas IA"):
        st.header("🔮 Sugestões Inteligentes de Alocação")
        st.info("Funcionalidade em construção")
    else:
        st.info("Sem transações para gerar o gráfico.")