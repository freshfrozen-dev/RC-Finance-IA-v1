
import sys
from pathlib import Path

# PATH BOOTSTRAP
# Adiciona o diretório raiz do projeto ao sys.path para que os módulos possam ser encontrados
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import streamlit as st
from datetime import datetime, timedelta
from scripts.utils.db_utils import get_transactions_filtered, init_db
from scripts.utils.export import export_df_csv, export_df_excel
from scripts.utils.ui_components import (
    show_skeleton_table, show_banner, action_toast, with_progress
)

# Inicializa o banco de dados para garantir que a tabela 'transactions' exista
init_db()

def reports_simple_page():
    st.set_page_config(page_title="Relatórios Simples", page_icon="📄", layout="wide")

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
    

    
    st.markdown('<h1 class="title-primary">Relatórios Simples</h1>', unsafe_allow_html=True)

    user_id = st.session_state['user_id']

    # Filtros em duas colunas: período | tipo
    st.markdown('<h2 class="h2">Filtros</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        today = datetime.now().date()
        default_start_date = today - timedelta(days=90)
        date_range = st.date_input(
            "Período",
            value=(default_start_date, today),
            key="date_range_filter"
        )
    
    with col2:
        type_options = {"Todos": None, "Receitas": "income", "Despesas": "expense"}
        selected_type_display = st.selectbox(
            "Tipo",
            options=list(type_options.keys()),
            key="type_filter"
        )
        type_filter = type_options[selected_type_display]

    # Categorias abaixo
    all_transactions_df = get_transactions_filtered(user_id=user_id)
    all_categories = sorted(all_transactions_df['category'].unique().tolist()) if not all_transactions_df.empty else []

    selected_categories = st.multiselect(
        "Categorias",
        options=all_categories,
        default=all_categories,
        key="category_filter"
    )

    date_start = date_range[0].strftime("%Y-%m-%d") if len(date_range) > 0 else None
    date_end = date_range[1].strftime("%Y-%m-%d") if len(date_range) > 1 else None

    # Skeleton loader para tabela
    table_placeholder = st.empty()
    with table_placeholder:
        show_skeleton_table(rows=8, cols=6)
    
    def load_transactions():
        return get_transactions_filtered(
            user_id=user_id,
            date_start=date_start,
            date_end=date_end,
            categories=selected_categories,
            type_filter=type_filter
        )
    
    df_transactions = with_progress("Carregando transações...", load_transactions)
    table_placeholder.empty()

    if df_transactions.empty:
        st.markdown('''
        <div class="empty-state">
            <h3>Nenhuma transação encontrada</h3>
            <p>Não há transações com os filtros selecionados.</p>
            <button class="cta-button" onclick="window.location.href='#'">Importe CSV</button>
        </div>
        ''', unsafe_allow_html=True)
    else:
        # Métricas
        total_income = df_transactions[df_transactions['type'] == 'income']['amount'].sum()
        total_expense = df_transactions[df_transactions['type'] == 'expense']['amount'].sum()
        balance = total_income + total_expense # Despesas são valores negativos, então soma
        num_transactions = len(df_transactions)

        st.markdown('<h2 class="title-secondary">Resumo</h2>', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Receitas", f"R$ {total_income:,.2f}")
        col2.metric("Total de Despesas", f"R$ {total_expense:,.2f}")
        col3.metric("Saldo", f"R$ {balance:,.2f}")
        col4.metric("Quantidade de Transações", num_transactions)

        st.markdown('<h2 class="title-secondary">Transações Detalhadas</h2>', unsafe_allow_html=True)
        st.dataframe(df_transactions, use_container_width=True)

        # Botões de Exportação
        st.markdown('<h2 class="title-secondary">Exportar Dados</h2>', unsafe_allow_html=True)
        col_exp1, col_exp2 = st.columns(2)

        # Exportar para CSV
        def export_csv():
            return export_df_csv(df_transactions)
        
        def export_excel():
            return export_df_excel(df_transactions)

        with col_exp1:
            if st.button("Preparar CSV", type="primary"):
                show_banner("info", "Gerando arquivo CSV...")
                csv_filename, csv_bytes, csv_mime = with_progress("Gerando CSV...", export_csv)
                st.download_button(
                    label="Download CSV",
                    data=csv_bytes,
                    file_name=csv_filename,
                    mime=csv_mime,
                    key="download_csv"
                )
                action_toast("success", "Arquivo CSV pronto para download!")

        with col_exp2:
            if st.button("Preparar Excel", type="primary"):
                show_banner("info", "Gerando arquivo Excel...")
                excel_filename, excel_bytes, excel_mime = with_progress("Gerando Excel...", export_excel)
                st.download_button(
                    label="Download Excel",
                    data=excel_bytes,
                    file_name=excel_filename,
                    mime=excel_mime,
                    key="download_excel"
                )
                action_toast("success", "Arquivo Excel pronto para download!")

# Se este script for executado diretamente (para testes ou como página principal)
if __name__ == "__main__":
    reports_simple_page()





st.markdown(
    """
    <style>
      .rc-mic{position:fixed;right:24px;bottom:24px;z-index:1000}
      .rc-mic>a{display:inline-flex;align-items:center;justify-content:center;
        width:56px;height:56px;border-radius:50%;background:#7C3AED;color:#fff;
        box-shadow:0 8px 24px rgba(0,0,0,.35);text-decoration:none;font-size:24px}
      .rc-mic>a:hover{filter:brightness(1.08)}
    </style>
    <div class="rc-mic"><a href="/voz" target="_self" title="Comandos de Voz">🎤</a></div>
    """,
    unsafe_allow_html=True,
)


