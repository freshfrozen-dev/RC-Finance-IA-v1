
import streamlit as st
import sys
from pathlib import Path

# PATH BOOTSTRAP
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from scripts.utils import db_utils
from scripts.utils import auth
from scripts.utils import export
from scripts.utils.ui_components import (
    show_banner, action_toast, with_progress
)
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Metas Financeiras", page_icon="🎯")
st.markdown("<link rel='stylesheet' href='assets/styles.css'>", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    try:
        st.switch_page("login")
    except Exception:
        st.rerun()
    st.stop()

user_id = st.session_state['user_id']

st.markdown('<h1 class="title-primary">Metas Financeiras</h1>', unsafe_allow_html=True)

# Layout com colunas
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<h2 class="title-secondary">Criar/Editar Meta</h2>', unsafe_allow_html=True)
    with st.form("goal_form", clear_on_submit=True):
        st.markdown('<div class="card-bancario">', unsafe_allow_html=True)
        
        goal_id = st.session_state.get("editing_goal_id", None)
        
        name = st.text_input("Nome da Meta", value=st.session_state.get("editing_goal_name", ""), placeholder="Ex: Viagem para Europa")
        target_amount = st.number_input("Valor Alvo", min_value=0.0, value=st.session_state.get("editing_goal_target_amount", 0.0))
        due_date_str = st.date_input("Data Limite (Opcional)", value=st.session_state.get("editing_goal_due_date", None), format="YYYY-MM-DD")
        
        submitted = st.form_submit_button("Salvar Meta" if goal_id else "Criar Meta", type="primary")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if submitted:
            if name and target_amount > 0:
                def save_goal():
                    if goal_id:
                        db_utils.update_goal(goal_id, user_id, name=name, target_amount=target_amount, due_date=str(due_date_str) if due_date_str else None)
                        return "updated"
                    else:
                        db_utils.create_goal(user_id, name, target_amount, str(due_date_str) if due_date_str else None)
                        return "created"
                
                try:
                    result = with_progress("Salvando meta...", save_goal)
                    if result == "updated":
                        show_banner("success", f"Meta '{name}' atualizada com sucesso!")
                        action_toast("success", "Meta atualizada!")
                    else:
                        show_banner("success", f"Meta '{name}' criada com sucesso!")
                        action_toast("success", "Meta criada!")
                    
                    # Limpar estado de edição
                    for key in ["editing_goal_id", "editing_goal_name", "editing_goal_target_amount", "editing_goal_due_date"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar meta: {e}")
            else:
                st.warning("Por favor, preencha o nome e o valor alvo da meta.")

with col2:
    st.header("Aportar em Meta")
    goals_df = db_utils.list_goals(user_id)
    if not goals_df.empty:
        goal_names = goals_df["name"].tolist()
        selected_goal_name = st.selectbox("Selecione a Meta para Aportar", goal_names)
        
        if selected_goal_name:
            selected_goal = goals_df[goals_df["name"] == selected_goal_name].iloc[0]
            st.write(f"**Meta:** {selected_goal['name']}")
            st.write(f"**Valor Alvo:** R$ {selected_goal['target_amount']:.2f}")
            st.write(f"**Aportado:** R$ {selected_goal['funded_amount']:.2f}")
            
            progress_val = db_utils.progress(selected_goal)
            st.progress(progress_val)
            st.write(f"Progresso: R$ {selected_goal['funded_amount']:.2f} / R$ {selected_goal['target_amount']:.2f} ({progress_val*100:.1f}%) ")

            amount_to_fund = st.number_input("Valor do Aporte/Estorno", value=0.0, format="%.2f")
            if st.button("Aportar/Estornar"):
                try:
                    db_utils.fund_goal(selected_goal["id"], user_id, amount_to_fund)
                    st.success(f"Aporte/Estorno de R$ {amount_to_fund:.2f} realizado com sucesso na meta '{selected_goal_name}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao aportar/estornar: {e}")
    else:
        st.info("Nenhuma meta cadastrada ainda.")

st.markdown("---")
st.markdown('<h2 class="h2">Minhas Metas</h2>', unsafe_allow_html=True)

if not goals_df.empty:
    # Calcular progresso e ordenar
    goals_df["progress_pct"] = goals_df.apply(lambda row: round(db_utils.progress(row) * 100, 1), axis=1)
    goals_df["due_date"] = goals_df["due_date"].fillna("2099-12-31")  # Para ordenação
    
    # Ordenar por due_date asc e progress_pct desc
    goals_df = goals_df.sort_values(["due_date", "progress_pct"], ascending=[True, False])
    
    # Exibir como cards com progress bars
    for _, goal in goals_df.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{goal['name']}**")
                progress_val = goal['progress_pct'] / 100
                st.progress(progress_val)
                st.caption(f"R$ {goal['funded_amount']:.2f} / R$ {goal['target_amount']:.2f} ({goal['progress_pct']:.1f}%)")
            
            with col2:
                if goal['due_date'] != "2099-12-31":
                    st.markdown(f"<span class='badge badge-info'>Até {goal['due_date']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='badge'>Sem prazo</span>", unsafe_allow_html=True)
            
            with col3:
                if goal['progress_pct'] >= 100:
                    st.markdown("<span class='badge badge-success'>Concluída</span>", unsafe_allow_html=True)
                elif goal['progress_pct'] >= 50:
                    st.markdown("<span class='badge badge-warning'>Em progresso</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='badge'>Iniciada</span>", unsafe_allow_html=True)
            
            st.divider()

    # Ações de exclusão com confirmação melhorada
    st.markdown('<h3 class="h2">Excluir Meta</h3>', unsafe_allow_html=True)
    
    col_del1, col_del2 = st.columns(2)
    with col_del1:
        goal_to_delete_id = st.number_input("ID da Meta para Excluir", min_value=1, format="%d")
    
    with col_del2:
        confirm_delete = st.checkbox(f"Confirmar exclusão da meta ID {goal_to_delete_id}?")
    
    if st.button("Excluir Meta Selecionada", type="secondary"):
        if goal_to_delete_id and confirm_delete:
            try:
                if db_utils.delete_goal(goal_to_delete_id, user_id):
                    st.success(f"Meta ID {goal_to_delete_id} excluída com sucesso.")
                    st.rerun()
                else:
                    st.error("Meta não encontrada ou não pertence ao usuário.")
            except Exception as e:
                st.error(f"Erro ao excluir meta: {e}")
        else:
            st.warning("Por favor, selecione um ID e confirme a exclusão.")

    # Exportar CSV
    st.markdown("--- ")
    st.subheader("Exportar Metas")
    csv_filename, csv_data, csv_mimetype = export.export_df_csv(display_df)
    st.download_button(
        label="Exportar Metas (CSV)",
        data=csv_data,
        file_name=csv_filename,
        mime=csv_mimetype,
    )
else:
    st.info("Nenhuma meta cadastrada ainda.")







st.markdown("--- ")
st.header("Sugestão de Alocação Simples")

if not goals_df.empty:
    available_balance = st.number_input("Saldo disponível para alocar", min_value=0.0, value=0.0)
    
    allocation_strategy = st.selectbox(
        "Estratégia de Alocação",
        ["Proporcional ao gap", "Equal split", "Prazo primeiro"]
    )

    if st.button("Gerar Sugestão de Alocação"):
        if available_balance > 0:
            goals_in_progress = goals_df[goals_df["funded_amount"] < goals_df["target_amount"]].copy()
            
            if not goals_in_progress.empty:
                goals_in_progress["remaining_gap"] = goals_in_progress["target_amount"] - goals_in_progress["funded_amount"]
                
                suggested_allocation = pd.DataFrame(columns=["Meta", "Valor Sugerido"])
                
                if allocation_strategy == "Proporcional ao gap":
                    total_gap = goals_in_progress["remaining_gap"].sum()
                    if total_gap > 0:
                        goals_in_progress["allocation"] = (goals_in_progress["remaining_gap"] / total_gap) * available_balance
                    else:
                        goals_in_progress["allocation"] = 0
                
                elif allocation_strategy == "Equal split":
                    num_goals = len(goals_in_progress)
                    if num_goals > 0:
                        goals_in_progress["allocation"] = available_balance / num_goals
                    else:
                        goals_in_progress["allocation"] = 0

                elif allocation_strategy == "Prazo primeiro":
                    goals_in_progress["due_date_dt"] = pd.to_datetime(goals_in_progress["due_date"], errors='coerce')
                    goals_in_progress = goals_in_progress.sort_values(by="due_date_dt", na_position='last')
                    
                    allocated_so_far = 0.0
                    for index, row in goals_in_progress.iterrows():
                        amount_to_allocate = min(row["remaining_gap"], (available_balance - allocated_so_far) / (len(goals_in_progress) - goals_in_progress.index.get_loc(index)))
                        goals_in_progress.loc[index, "allocation"] = amount_to_allocate
                        allocated_so_far += amount_to_allocate

                # Ajustar alocação para não exceder o gap restante
                goals_in_progress["allocation"] = goals_in_progress.apply(lambda row: min(row["allocation"], row["remaining_gap"]), axis=1)
                
                # Distribuir o restante se a soma das alocações for menor que o saldo disponível
                total_allocated = goals_in_progress["allocation"].sum()
                if total_allocated < available_balance:
                    remaining_to_distribute = available_balance - total_allocated
                    # Redistribuir proporcionalmente aos gaps restantes
                    total_gap_after_initial = goals_in_progress["remaining_gap"].sum() - goals_in_progress["allocation"].sum()
                    if total_gap_after_initial > 0:
                        goals_in_progress["allocation"] += (goals_in_progress["remaining_gap"] - goals_in_progress["allocation"]) / total_gap_after_initial * remaining_to_distribute
                        goals_in_progress["allocation"] = goals_in_progress.apply(lambda row: min(row["allocation"], row["remaining_gap"]), axis=1)

                suggested_allocation = goals_in_progress[goals_in_progress["allocation"] > 0][["name", "allocation"]]
                suggested_allocation = suggested_allocation.rename(columns={"name": "Meta", "allocation": "Valor Sugerido"})
                suggested_allocation["Valor Sugerido"] = suggested_allocation["Valor Sugerido"].map("R$ {:.2f}".format)

                if not suggested_allocation.empty:
                    st.subheader("Sugestão de Distribuição:")
                    st.dataframe(suggested_allocation, use_container_width=True)
                    
                    if st.button("Aplicar Sugestão de Alocação"):
                        try:
                            for index, row in goals_in_progress.iterrows():
                                if row["allocation"] > 0:
                                    db_utils.fund_goal(row["id"], user_id, row["allocation"])
                            st.success("Sugestão de alocação aplicada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao aplicar sugestão de alocação: {e}")
                else:
                    st.info("Nenhuma meta em andamento para alocar o saldo disponível.")
            else:
                st.info("Nenhuma meta em andamento para alocar o saldo disponível.")
        else:
            st.warning("Por favor, insira um saldo disponível maior que zero.")
else:
    st.info("Nenhuma meta cadastrada para sugerir alocação.")


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

