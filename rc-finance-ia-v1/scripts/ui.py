
# --- PATH BOOTSTRAP (mantém imports "from scripts...." funcionando) ---
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
# tenta raiz 1 ou 2 níveis acima (ui.py vs pages/*.py)
for _root in (_THIS.parents[1], _THIS.parents[2] if len(_THIS.parents) > 2 else _THIS.parents[1]):
    if (_root / "scripts").exists():
        _root_str = str(_root)
        if _root_str not in sys.path:
            sys.path.insert(0, _root_str)
        break
# ----------------------------------------------------------------------


import streamlit as st
from pathlib import Path
import traceback
import sys
import os
import contextlib
from io import StringIO, BytesIO
from datetime import date, datetime, timedelta
import pandas as pd
from sqlite_utils import Database
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json
import time
import tempfile
import hashlib

# Importações dos módulos utilitários
from scripts.utils.db_utils import salvar_transacao, get_db, init_db, insert_transaction, bulk_insert_transactions
from scripts.utils.export import export_df_csv, export_df_excel
from scripts.utils.projections_simple import monthly_aggregate, forecast_balance
from scripts.utils.allocation import Goal, compute_scores, allocate, update_weights
from scripts.utils.importers import parse_csv, parse_ofx
from scripts.utils.ui_components import (
    show_skeleton_metric, show_skeleton_table,
    show_banner, action_toast, with_progress, create_metric_card
)
# Paths com pathlib
ROOT = Path(__file__).resolve().parent.parent.parent # RC-Finance-IA/
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "finance.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Adiciona o diretório raiz do projeto ao sys.path para importações relativas
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Inicializa o banco de dados
init_db()

# --- Configuração do Streamlit ---
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

# Injeção do CSS
st.markdown("<link rel='stylesheet' href='assets/styles.css'>", unsafe_allow_html=True)

# Inicialização do estado de login (apenas uma vez)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Gate de login
if not st.session_state.get("logged_in"):
    try:
        st.switch_page("0_login")
    except Exception:
        st.stop()

if st.session_state.get("__go_to") == "ui":
    st.session_state.pop("__go_to", None)


# --- Estilo ---
HIDE_FOOTER = """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
"""
st.markdown(HIDE_FOOTER, unsafe_allow_html=True)

def _row_to_id(row: dict) -> int:
    """Gera ID único baseado no conteúdo da transação usando MD5"""
    key = f'{row["type"]}|{row["description"]}|{row["amount"]:.2f}|{row["category"]}|{row["date"]}'
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:12], 16)

def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza DataFrame para o schema padrão"""
    map_cols = {
        "Data": "date",
        "Descricao": "description",
        "Descrição": "description",
        "Valor": "amount",
        "Categoria": "category",
        "Tipo": "type",
    }
    df = df.rename(columns=map_cols)
    obrig = ["type", "description", "amount", "category", "date"]
    missing = [c for c in obrig if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    df["description"] = df["description"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()
    df["date"] = df["date"].astype(str).str.strip()
    return df


@st.cache_data(ttl=30)
def get_user_transactions(user_id):
    """Carrega transações do usuário com cache"""
    db = get_db()
    if "transactions" in db.table_names():
        return pd.DataFrame(list(db["transactions"].rows_where("user_id = ?", (user_id,))))
    return pd.DataFrame()

def render_dashboard():
    st.markdown('<h1 class="h1">RC-Finance-IA — Dashboard</h1>', unsafe_allow_html=True)

    user_id = st.session_state["user_id"]

    # Skeletons iniciais para 3 métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        show_skeleton_metric(180, 80)
    with col2:
        show_skeleton_metric(180, 80)
    with col3:
        show_skeleton_metric(180, 80)
    
    # Skeleton para gráfico
    chart_placeholder = st.empty()
    with chart_placeholder:
        show_skeleton_metric(800, 400)

    # Carrega dados com cache
    df = get_user_transactions(user_id)

    # Limpa skeletons e renderiza dados reais
    if df.empty:
        col1.empty()
        col2.empty()
        col3.empty()
        chart_placeholder.empty()
        
        st.markdown('''
        <div class="empty-state">
            <h3>Sem dados financeiros</h3>
            <p>Ainda não há transações para o seu usuário.</p>
            <button class="cta-button" onclick="window.location.href='#'">Importe CSV</button>
        </div>
        ''', unsafe_allow_html=True)
        return

    # Normaliza tipos de dados
    df["type"] = df["type"].astype(str)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # Agregação mensal
    monthly_df = monthly_aggregate(df)

    # Projeção de saldo
    forecast_df = forecast_balance(monthly_df)

    # Métricas gerais
    income = df.loc[df["type"] == "income", "amount"].sum()
    expense = df.loc[df["type"] == "expense", "amount"].sum()
    saldo = float(income - expense)

    f = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Exibe métricas com cards bancários
    with col1:
        create_metric_card("Receitas", f(income))
    with col2:
        create_metric_card("Despesas", f(expense))
    with col3:
        st.markdown(
            f"""
            <div style="display:flex;gap:16px;flex-wrap:wrap">
              <div style="background:linear-gradient(135deg,#1E2230 0%,#111522 60%);
                          border-radius:16px;padding:20px 24px;color:#E6E9EF;min-width:320px;
                          box-shadow:0 12px 32px rgba(0,0,0,.35);position:relative;overflow:hidden">
                <div style="opacity:.22;position:absolute;right:-40px;top:-40px;width:220px;height:220px;
                            border-radius:50%;background:radial-gradient(closest-side,#7C3AED,transparent)"></div>
                <div style="font-size:.9rem;color:#9AA4B2">Saldo principal</div>
                <div style="font-size:2rem;font-weight:700;letter-spacing:.3px;margin:4px 0 12px">R$ {saldo:,.2f}</div>
                <div style="display:flex;justify-content:space-between;color:#9AA4B2">
                  <span>**** **** **** 5423</span>
                  <span>Vál. 12/27</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Gráfico de linha (income/expense/balance)
    st.markdown('<h2 class="title-secondary">Histórico e Projeção de Saldo</h2>', unsafe_allow_html=True)
    
    # Mostra skeleton do gráfico primeiro
    chart_placeholder = st.empty()
    with chart_placeholder:
        show_skeleton_chart(height=400)
    
    time.sleep(0.3)  # Simula carregamento
    
    if not monthly_df.empty:
        chart_placeholder.empty()
        fig, ax = plt.subplots(figsize=(10, 6))
        monthly_df["income"].plot(ax=ax, label="Receita", color="green")
        monthly_df["expense"].plot(ax=ax, label="Despesa", color="red")
        monthly_df["balance"].plot(ax=ax, label="Saldo", color="blue")
        if not forecast_df.empty:
            forecast_df["balance_forecast"].plot(
                ax=ax, label="Projeção de Saldo", linestyle=":", color="blue"
            )
        ax.set_title("Receita, Despesa e Saldo Mensal")
        ax.set_ylabel("Valor (R$)")
        ax.legend()
        st.pyplot(fig)
        plt.close(fig)
    else:
        chart_placeholder.empty()
        show_banner("info", "Dados insuficientes para gerar o histórico mensal.")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Filtros
    st.markdown('<h2 class="title-secondary">Filtros</h2>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if not df.empty:
            dmin = df["date"].min().date()
            dmax = df["date"].max().date()
        else:
            dmin = date.today()
            dmax = date.today()

        sel = st.date_input(
            "Período", value=(dmin, dmax), key="filtro_periodo_dashboard_unique"
        )

    # sel pode ser date único ou (date, date)
    if isinstance(sel, tuple) and len(sel) == 2:
        di, dfim = sel
    elif isinstance(sel, (date, datetime)):
        di = dfim = sel
    else:
        di = dfim = dmin, dmax

    with c2:
        tipo_select = st.selectbox(
            "Filtrar tipo:", ["todos", "income", "expense"], key="filtro_tipo_dashboard"
        )

    # Aplicar filtros de período e tipo
    df_filtered = df[
        (df["date"] >= pd.to_datetime(di)) & (df["date"] <= pd.to_datetime(dfim))
    ]
    if tipo_select != "todos":
        df_filtered = df_filtered[df_filtered["type"] == tipo_select]

    # Gráficos
    if not df_filtered.empty:
        st.markdown('<h2 class="title-secondary">Análises</h2>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Receitas vs Despesas**")
            fig, ax = plt.subplots(figsize=(8, 6))
            income_filtered = df_filtered.loc[
                df_filtered["type"] == "income", "amount"
            ].sum()
            expense_filtered = df_filtered.loc[
                df_filtered["type"] == "expense", "amount"
            ].sum()
            ax.bar(
                ["Receitas", "Despesas"],
                [income_filtered, expense_filtered],
                color=["green", "red"],
                alpha=0.7,
            )
            ax.set_ylabel("Valor (R$)")
            ax.set_title("Receitas vs Despesas")
            st.pyplot(fig)
            plt.close(fig)

        with col2:
            st.write("**Gastos por Categoria**")
            expenses_by_cat = (
                df_filtered[df_filtered["type"] == "expense"]
                .groupby("category")["amount"]
                .sum()
            )
            if not expenses_by_cat.empty and (expenses_by_cat >= 0).all():
                fig, ax = plt.subplots(figsize=(8, 6))
                expenses_by_cat.plot(kind="pie", ax=ax, autopct="%1.1f%%")
                ax.set_ylabel("")
                ax.set_title("Distribuição de Gastos")
                st.pyplot(fig)
                plt.close(fig)
            else:
                show_banner("info", "Nenhuma despesa ou despesas negativas no período selecionado para o gráfico de pizza.")

        # Gráfico de barras (planejado x realizado de metas) - Placeholder, pois não há dados de metas no DF atual
        st.markdown('<h3 class="subtitle">Planejado vs Realizado (Metas)</h3>', unsafe_allow_html=True)
        show_banner("info", "Funcionalidade de metas ainda não implementada. Este gráfico será preenchido quando dados de metas estiverem disponíveis.")
    else:
        show_banner("info", "Nenhuma despesa no período selecionado")


def render_goals():
    st.header("🎯 Metas")
    st.markdown(
        "Aqui você pode definir suas metas financeiras e o sistema irá sugerir como alocar seu saldo livre para alcançá-las."
    )

    user_id = st.session_state["user_id"]
    db = get_db()
    goals_data = []
    if "goals" in db.table_names():
        goals_data = list(db["goals"].rows_where("user_id = ?", (user_id,))) # Filtrar por user_id

    sample_goals = []
    for g_data in goals_data:
        sample_goals.append(Goal(
            id=g_data["id"],
            name=g_data["name"],
            due_date=date.fromisoformat(g_data["due_date"]) if g_data["due_date"] else None,
            target_amount=g_data["target_amount"],
            funded_amount=g_data.get("funded_amount", 0.0),
            # Adicionar outros campos se existirem no DB e forem necessários para Goal
            impact=0.9, # Placeholder
            priority_user=0.8, # Placeholder
            funded_pct=g_data.get("funded_amount", 0.0) / g_data["target_amount"] if g_data["target_amount"] else 0.0,
            stability_hint=0.7 # Placeholder
        ))

    st.subheader("Metas Atuais")
    if sample_goals:
        goals_df = pd.DataFrame([g.__dict__ for g in sample_goals])
        st.dataframe(goals_df)
    else:
        st.info("Nenhuma meta definida para o seu usuário.")

    st.subheader("Simulação de Alocação")
    balance_free = st.number_input(
        "Saldo Livre Disponível para Alocação (R$)",
        min_value=0.0,
        value=1000.0,
        step=100.0,
    )

    # Pesos para o cálculo do score (podem ser configuráveis no futuro)
    weights = {
        "urgency": 0.3,
        "impact": 0.2,
        "priority_user": 0.2,
        "stability": 0.1,
        "funded_pct": 0.2,
    }

    if st.button("Simular Alocação", key="simulate_allocation_btn"):
        if sample_goals:
            scored_goals = compute_scores(sample_goals, date.today(), weights)
            allocation_result = allocate(balance_free, scored_goals)

            if allocation_result:
                st.write("**Plano de Alocação Sugerido:**")
                allocated_df = pd.DataFrame(
                    [
                        {"Meta ID": goal_id, "Valor Alocado": amount}
                        for goal_id, amount in allocation_result.items()
                    ]
                )
                st.dataframe(allocated_df)

                total_allocated_sim = sum(allocation_result.values())
                st.info(f"Total alocado na simulação: R$ {total_allocated_sim:,.2f}")

                if st.button(
                    "Aplicar Alocação (Salvar no Banco)",
                    type="primary",
                    key="apply_allocation_btn",
                ):
                    # Aqui você implementaria a lógica para salvar a alocação no banco de dados
                    # Por exemplo, atualizando o campo \'funded_amount\' das metas
                    st.success(
                        "Alocação aplicada e salva com sucesso! (Funcionalidade de salvamento no DB a ser implementada)"
                    )
            else:
                st.info("Nenhuma alocação sugerida para o saldo livre disponível ou metas.")
        else:
            st.info("Nenhuma meta para simular alocação.")


def render_transactions():
    st.header("Exportar CSV Transações")

    user_id = st.session_state["user_id"]

    # Botão Recarregar
    if st.button(
        "🔄 Recarregar", help="Atualiza a lista e os totais", key="reload_transactions"
    ):
        st.rerun()

    with st.expander("🔎 Diagnóstico do banco"):
        st.write("DB path:", str(DB_PATH))
        db = get_db()
        st.write("Tabela existe:", "transactions" in db.table_names())
        st.write(
            "Total de linhas (seu usuário):",
            (db["transactions"].count_where("user_id = ?", (user_id,)) if "transactions" in db.table_names() else 0),
        )

    # Upload de arquivos
    st.subheader("Importar por Arquivo (CSV, OFX)")
    arquivo = st.file_uploader(
        "Selecione um arquivo", type=["csv", "ofx"], key="uploader_tx_unique"
    )
    enviar = st.button("Processar arquivo", type="primary", key="processar_arquivo_btn")

    if enviar and arquivo is not None:
        start_time = time.perf_counter()
        try:
            nome = (arquivo.name or "").strip().lower()
            file_content = arquivo.getvalue().decode("utf-8")
            transactions_to_insert = []

            # ---------------- CSV ----------------
            if nome.endswith(".csv"):
                transactions_to_insert = parse_csv(file_content)

            # ---------------- OFX ----------------
            elif nome.endswith(".ofx"):
                transactions_to_insert = parse_ofx(file_content)
                if not transactions_to_insert:
                    st.warning("Não foi possível processar o arquivo OFX. Verifique se a biblioteca 'ofxparse' está instalada e o arquivo é válido.")

            if transactions_to_insert:
                # Adicionar user_id a cada transação e inserir em massa
                for t in transactions_to_insert:
                    t["user_id"] = user_id
                
                result = bulk_insert_transactions(user_id, transactions_to_insert)
                st.success(f"Importação concluída em {time.perf_counter() - start_time:.2f}s — Inseridas: {result['inserted']}, Duplicadas: {result['duplicates']}, Falhas: {result['failed']}")
                action_toast("success", "Importação realizada com sucesso!")
            else:
                st.info("Nenhuma transação válida encontrada no arquivo ou formato não suportado.")

        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")
            st.code(traceback.format_exc())

    st.divider()

    # Adicionar Transação Manual
    st.subheader("Adicionar Transação Manualmente")
    with st.form("manual_transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            manual_date = st.date_input("Data", value=date.today())
            manual_description = st.text_input("Descrição")
            manual_amount = st.number_input("Valor", format="%.2f")
        with col2:
            manual_type = st.selectbox("Tipo", ["income", "expense"])
            manual_category = st.text_input("Categoria")

        submitted = st.form_submit_button("Adicionar Transação")
        if submitted:
            if manual_description and manual_amount and manual_category:
                try:
                    insert_transaction(
                        user_id=user_id,
                        date=manual_date.strftime("%Y-%m-%d"),
                        description=manual_description,
                        amount=manual_amount,
                        category=manual_category,
                        type=manual_type
                    )
                    st.success("Transação adicionada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao adicionar transação: {e}")
                    st.code(traceback.format_exc())
            else:
                st.warning("Por favor, preencha todos os campos para adicionar a transação.")

    st.divider()

    # Exibir transações existentes
    st.subheader("Suas Transações")
    db = get_db()
    if "transactions" in db.table_names():
        df_existing_transactions = pd.DataFrame(list(db["transactions"].rows_where("user_id = ? ORDER BY date DESC", (user_id,))))
        if not df_existing_transactions.empty:
            st.dataframe(df_existing_transactions, use_container_width=True)
        else:
            st.info("Nenhuma transação encontrada para o seu usuário.")
    else:
        st.info("Tabela de transações não encontrada.")


def render_voice():
    st.header("🗣️ Voz")
    st.markdown(
        "Aqui você pode interagir com o assistente financeiro por voz. Diga algo como: 'Adicionar uma despesa de 50 reais em alimentação'."
    )

    # Placeholder para o microfone e processamento de voz
    st.warning("Funcionalidade de voz em desenvolvimento.")

    # Exemplo de uso da função de transcrição (apenas para demonstração)
    # if st.button("Gravar Áudio (Exemplo)"):
    #     audio_bytes = st.file_uploader("Upload de áudio (WAV)", type=["wav"])
    #     if audio_bytes:
    #         with st.spinner("Transcrevendo..."):
    #             transcricao = transcrever_audio(audio_bytes.read())
    #             st.write(f"Transcrição: {transcricao}")


# --- Navegação --- (Sidebar)
st.sidebar.title("Navegação")

# Exibir usuário logado
if st.session_state.get("logged_in"):
    user_name = st.session_state.get("user_name", "Usuário")
    st.sidebar.markdown(f"**Usuário:** {user_name}")
    st.sidebar.divider()

# Mapeamento de páginas para funções de renderização
pages = {
    "Dashboard": render_dashboard,
    "Transações": render_transactions,
    "Relatórios Simples": st.Page("pages/2_reports_simple.py", title="Relatórios Simples", icon="Dashboard"),
    "Importar Transações": st.Page("pages/3_import_transactions.py", title="Importar Transações", icon="📥"),
    "Metas": render_goals,
    "Voz": render_voice,
}

# Adiciona a página de login separadamente, pois ela não requer login prévio
login_page = st.Page("pages/0_login.py", title="Login", icon="🔑")

# Se não estiver logado, mostra apenas a página de login
if not st.session_state.get("logged_in"):
    login_page.run()
else:
    # Se logado, mostra as outras páginas
    pg = st.navigation([login_page] + list(pages.values()))
    pg.run()





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




render_dashboard()


