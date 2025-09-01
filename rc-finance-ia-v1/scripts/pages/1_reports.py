import streamlit as st
import traceback
from pathlib import Path
import json
from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT.parent / "reports" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Relatórios", page_icon="📈")
st.markdown("<link rel='stylesheet' href='assets/styles.css'>", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    try:
        st.switch_page("login")
    except Exception:
        st.rerun()
    st.stop()

st.title("Relatórios Dinâmicos")
st.markdown("Gere relatórios personalizados com filtros avançados e visualizações.")

    # Filtros na sidebar
    st.sidebar.header("Filtros do Relatório")

    # Filtro de período
    st.sidebar.subheader("Período")
    today = date.today()
    default_start = today - timedelta(days=30)

    date_range = st.sidebar.date_input(
        "Selecione o período:", value=(default_start, today), key="reports_date_range"
    )

    # Filtro de categorias
    st.sidebar.subheader("Categorias")
    categories = st.sidebar.multiselect(
        "Selecione as categorias:",
        options=[
            "Todas",
            "Alimentação",
            "Transporte",
            "Lazer",
            "Saúde",
            "Salário",
            "Renda Extra",
            "Utilidades",
            "Moradia",
            "Compras",
        ],
        default=["Todas"],
        key="reports_categories",
    )

    # Filtro de contas
    st.sidebar.subheader("Contas")
    accounts = st.sidebar.multiselect(
        "Selecione as contas:",
        options=["Todas", "Conta Corrente", "Poupança", "Cartão de Crédito"],
        default=["Todas"],
        key="reports_accounts",
    )

    # Filtro de tipo de transação
    st.sidebar.subheader("Tipo de Transação")
    transaction_types = st.sidebar.multiselect(
        "Selecione os tipos:",
        options=["Todos", "Receita", "Despesa"],
        default=["Todos"],
        key="reports_transaction_types",
    )

    # Filtro de usuário
    st.sidebar.subheader("👤 Usuário")
    user_filter = st.sidebar.selectbox(
        "Filtrar por usuário:",
        options=["Todos", "Usuário 1", "Usuário 2"],
        key="reports_user_filter",
    )

    # Criar dados baseados nos filtros
    df_filtered = create_sample_data(
        date_range, categories, accounts, transaction_types, user_filter
    )

    # Calcular métricas
    if not df_filtered.empty:
        receitas = df_filtered[df_filtered["Tipo"] == "Receita"]["Valor"].sum()
        despesas = df_filtered[df_filtered["Tipo"] == "Despesa"]["Valor"].sum()
        saldo = receitas - despesas
        total_transacoes = len(df_filtered)
    else:
        receitas = despesas = saldo = total_transacoes = 0

    # Conteúdo principal
    st.subheader("Resumo")

    # Métricas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Receitas",
            f"R$ {receitas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )

    with col2:
        st.metric(
            "Despesas",
            f"R$ {despesas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )

    with col3:
        st.metric(
            "Saldo",
            f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )

    with col4:
        st.metric("Transações", f"{total_transacoes}")

    st.divider()

    # Gráficos dinâmicos
    st.subheader("Visualizações")
    create_charts(df_filtered)

    st.divider()

    # Tabela de dados
    st.subheader("Dados Filtrados")

    if not df_filtered.empty:
        # Formatar dados para exibição
        df_display = df_filtered.copy()
        df_display["Data"] = df_display["Data"].dt.strftime("%d/%m/%Y")
        df_display["Valor"] = df_display["Valor"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Nenhuma transação encontrada com os filtros aplicados.")

    st.divider()

    # Botões de export
    st.subheader("📤 Exportar Dados")

    if not df_filtered.empty:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Exportar CSV", key="export_csv"):
                csv_data = export_to_csv(df_filtered)
                if csv_data:
                    st.download_button(
                        label="⬇️ Baixar CSV",
                        data=csv_data,
                        file_name=f"relatorio_{date.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                    st.success("Arquivo CSV preparado para download!")

        with col2:
            if st.button("Exportar Excel", key="export_excel"):
                excel_data = export_to_excel(df_filtered)
                if excel_data:
                    st.download_button(
                        label="⬇️ Baixar Excel",
                        data=excel_data,
                        file_name=f"relatorio_{date.today().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    st.success("Arquivo Excel preparado para download!")
    else:
        st.info("Nenhum dado disponível para exportar.")

    # Templates
    st.divider()
    st.subheader("Templates de Relatório")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**💾 Salvar Template**")
        template_name = st.text_input("Nome do template:", key="template_name_input")

        if st.button("💾 Salvar Template", key="save_template"):
            if template_name:
                current_filters = {
                    "date_range": (
                        [d.isoformat() for d in date_range]
                        if len(date_range) == 2
                        else []
                    ),
                    "categories": categories,
                    "accounts": accounts,
                    "transaction_types": transaction_types,
                    "user_filter": user_filter,
                }

                if save_template(template_name, current_filters):
                    st.success(f"Arquivo Template \'{template_name}\' salvo com sucesso!")
                else:
                    st.error("❌ Erro ao salvar template.")
            else:
                st.warning("⚠️ Digite um nome para o template.")

    with col2:
        st.write("**📂 Carregar Template**")
        available_templates = list_templates()

        if available_templates:
            selected_template = st.selectbox(
                "Selecione um template:",
                options=available_templates,
                key="template_selector",
            )

            if st.button("📂 Carregar Template", key="load_template"):
                loaded_filters = load_template(selected_template)
                if loaded_filters:
                    st.success(f"Arquivo Template \'{selected_template}\' carregado!")
                    st.info(
                        "🔄 Recarregue a página para aplicar os filtros do template."
                    )
                else:
                    st.error("❌ Erro ao carregar template.")
        else:
            st.info("Nenhum template salvo encontrado.")

    # Informações sobre os filtros aplicados
    st.sidebar.divider()
    st.sidebar.subheader("ℹ️ Filtros Aplicados")
    st.sidebar.write(f"**Período:** {date_range}")
    st.sidebar.write(f"**Categorias:** {', '.join(categories)}")
    st.sidebar.write(f"**Contas:** {', '.join(accounts)}")
    st.sidebar.write(f"**Tipos:** {', '.join(transaction_types)}")
    st.sidebar.write(f"**Usuário:** {user_filter}")


def create_sample_data(
    date_range, categories, accounts, transaction_types, user_filter
):
    """Função para criar dados de exemplo baseados nos filtros"""
    # Dados base
    base_data = {
        "Data": [
            "15/08/2025",
            "14/08/2025",
            "13/08/2025",
            "12/08/2025",
            "11/08/2025",
            "10/08/2025",
            "09/08/2025",
            "08/08/2025",
            "07/08/2025",
            "06/08/2025",
        ],
        "Descrição": [
            "Supermercado",
            "Salário",
            "Combustível",
            "Restaurante",
            "Freelance",
            "Farmácia",
            "Internet",
            "Aluguel",
            "Transporte",
            "Compras",
        ],
        "Categoria": [
            "Alimentação",
            "Salário",
            "Transporte",
            "Alimentação",
            "Renda Extra",
            "Saúde",
            "Utilidades",
            "Moradia",
            "Transporte",
            "Compras",
        ],
        "Tipo": [
            "Despesa",
            "Receita",
            "Despesa",
            "Despesa",
            "Receita",
            "Despesa",
            "Despesa",
            "Despesa",
            "Despesa",
            "Despesa",
        ],
        "Valor": [
            150.00,
            5000.00,
            80.00,
            45.00,
            800.00,
            35.00,
            89.90,
            1200.00,
            25.00,
            120.00,
        ],
        "Conta": [
            "Conta Corrente",
            "Conta Corrente",
            "Cartão de Crédito",
            "Cartão de Crédito",
            "Poupança",
            "Conta Corrente",
            "Conta Corrente",
            "Conta Corrente",
            "Conta Corrente",
            "Cartão de Crédito",
        ],
    }

    df = pd.DataFrame(base_data)
    df["Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y")

    # Aplicar filtros
    if categories and "Todas" not in categories:
        df = df[df["Categoria"].isin(categories)]

    if accounts and "Todas" not in accounts:
        df = df[df["Conta"].isin(accounts)]

    if transaction_types and "Todos" not in transaction_types:
        type_mapping = {"Receita": "Receita", "Despesa": "Despesa"}
        filtered_types = [
            type_mapping.get(t, t) for t in transaction_types if t in type_mapping
        ]
        if filtered_types:
            df = df[df["Tipo"].isin(filtered_types)]

    return df


def export_to_csv(df):
    """Exporta DataFrame para CSV"""
    if df.empty:
        return None

    # Preparar dados para export
    df_export = df.copy()
    df_export["Data"] = df_export["Data"].dt.strftime("%d/%m/%Y")

    # Converter para CSV
    csv_buffer = BytesIO()
    df_export.to_csv(csv_buffer, index=False, encoding="utf-8-sig", sep=";")
    csv_buffer.seek(0)

    return csv_buffer.getvalue()


def export_to_excel(df):
    """Exporta DataFrame para Excel"""
    if df.empty:
        return None

    # Preparar dados para export
    df_export = df.copy()
    df_export["Data"] = df_export["Data"].dt.strftime("%d/%m/%Y")

    # Converter para Excel
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df_export.to_excel(writer, sheet_name="Relatório", index=False)
    excel_buffer.seek(0)

    return excel_buffer.getvalue()


def save_template(template_name, filters):
    """Salva template de filtros"""
    try:
        TEMPLATES_DIR = ROOT.parent / "reports" / "templates"
        template_data = {
            "name": template_name,
            "filters": filters,
            "created_at": date.today().isoformat(),
        }

        template_file = TEMPLATES_DIR / f"{template_name}.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        st.error(f"Erro ao salvar template: {e}")
        return False


def load_template(template_name):
    """Carrega template de filtros"""
    try:
        TEMPLATES_DIR = ROOT.parent / "reports" / "templates"
        template_file = TEMPLATES_DIR / f"{template_name}.json"
        if template_file.exists():
            with open(template_file, "r", encoding="utf-8") as f:
                template_data = json.load(f)
            return template_data.get("filters", {})
        return None
    except Exception as e:
        st.error(f"Erro ao carregar template: {e}")
        return None


def list_templates():
    """Lista templates disponíveis"""
    try:
        TEMPLATES_DIR = ROOT.parent / "reports" / "templates"
        templates = []
        if TEMPLATES_DIR.exists():
            for file in TEMPLATES_DIR.iterdir():
                if file.suffix == ".json":
                    templates.append(file.stem)
        return templates
    except Exception:
        return []


def create_charts(df):
    """Função para criar gráficos dinâmicos"""
    if df.empty:
        st.info("Nenhum dado disponível para gerar gráficos.")
        return

    col1, col2 = st.columns(2)

    with col1:
        # Gráfico de pizza - Distribuição por categoria
        st.subheader("Distribuição por Categoria")
        category_data = df.groupby("Categoria")["Valor"].sum().reset_index()

        if not category_data.empty:
            fig_pie = px.pie(
                category_data,
                values="Valor",
                names="Categoria",
                title="Gastos por Categoria",
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sem dados para o gráfico de categorias.")

    with col2:
        # Gráfico de barras - Receitas vs Despesas
        st.subheader("Receitas vs Despesas")
        type_data = df.groupby("Tipo")["Valor"].sum().reset_index()

        if not type_data.empty:
            colors = {"Receita": "#2E8B57", "Despesa": "#DC143C"}
            fig_bar = px.bar(
                type_data,
                x="Tipo",
                y="Valor",
                title="Comparação Receitas vs Despesas",
                color="Tipo",
                color_discrete_map=colors,
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados para o gráfico de receitas vs despesas.")

    # Gráfico de linha temporal
    st.subheader("Evolução Temporal")
    df_temporal = df.copy()
    df_temporal = df_temporal.sort_values("Data")

    if not df_temporal.empty:
        # Criar dados diários
        daily_data = df_temporal.groupby(["Data", "Tipo"])["Valor"].sum().reset_index()

        fig_line = go.Figure()

        for tipo in daily_data["Tipo"].unique():
            data_tipo = daily_data[daily_data["Tipo"] == tipo]
            color = "#2E8B57" if tipo == "Receita" else "#DC143C"

            fig_line.add_trace(
                go.Scatter(
                    x=data_tipo["Data"],
                    y=data_tipo["Valor"],
                    mode="lines+markers",
                    name=tipo,
                    line=dict(color=color, width=3),
                    marker=dict(size=8),
                )
            )

        fig_line.update_layout(
            title="Evolução das Transações ao Longo do Tempo",
            xaxis_title="Data",
            yaxis_title="Valor (R$)",
            hovermode="x unified",
        )

        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Sem dados para o gráfico temporal.")

try:
    render()
except Exception as e:
    st.error(f"Erro na página Reports: {e}")
    st.code(traceback.format_exc())




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


