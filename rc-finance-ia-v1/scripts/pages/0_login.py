
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
import sqlite3
from pathlib import Path
import os

# Importa componentes UI
from scripts.utils.ui_components import (
    show_banner, action_toast, with_progress
)

DEBUG_LINK = bool(int(os.environ.get("RCF_DEBUG_LINK", "0")))

def _page_exists(rel_path: str) -> bool:
    """Verifica se a página existe a partir do app root atual."""
    try:
        app_root = Path(__file__).resolve().parents[1]
        return (app_root / rel_path).exists()
    except Exception:
        return False

def link_to_dashboard():
    """Renderiza link para o dashboard com o alvo correto baseado no app root."""
    candidates = [
        "ui.py",
        "scripts/ui.py",
    ]
    for target in candidates:
        if _page_exists(target):
            if DEBUG_LINK:
                st.caption(f"(DEBUG_LINK) st.page_link target: {target}")
            try:
                st.page_link(target, label="Ir para Painel", icon=":material/space_dashboard:")
                return
            except Exception as e:
                if DEBUG_LINK:
                    st.caption(f"(DEBUG_LINK) st.page_link falhou para {target}: {e}")
                continue
    st.info("Use a barra lateral para clicar em **Painel**.")

# Importar funções de autenticação do auth.py
from scripts.utils.auth import authenticate_user, get_user, create_user, ensure_default_admin

st.set_page_config(page_title="Login", page_icon="🔑", initial_sidebar_state="expanded")

# Injeção do CSS
st.markdown("<link rel='stylesheet' href='assets/styles.css'>", unsafe_allow_html=True)

# Se já logado, redireciona para o painel
if st.session_state.get("logged_in"):
    try:
        st.switch_page("ui")
    except Exception:
        st.rerun()
    st.stop()

ROOT = Path(__file__).resolve().parents[1]   # scripts/
DB_PATH = (ROOT.parent / "data" / "finance.db").resolve()

# Flag para habilitar/desabilitar o cadastro
ALLOW_SIGNUP = False # Mudar para True para habilitar o cadastro

# Garantir que o usuário admin padrão existe
con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
ensure_default_admin(con)
con.close()



st.markdown('<h1 class="title-primary">Entrar</h1>', unsafe_allow_html=True)

# Login Form
with st.form("login_form"):
    st.markdown('<div class="card-bancario">', unsafe_allow_html=True)
    st.markdown('<h3 class="subtitle">Acesse sua conta</h3>', unsafe_allow_html=True)
    
    email = st.text_input("Email", value="admin@gmail.com", placeholder="Digite seu email")
    senha = st.text_input("Senha", type="password", value="Admin@123", placeholder="Digite sua senha")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        login_submitted = st.form_submit_button("Entrar", type="primary")
    
    st.markdown('</div>', unsafe_allow_html=True)

    if login_submitted:
        try:
            with st.spinner("Entrando..."):
                con = sqlite3.connect(DB_PATH)
                con.row_factory = sqlite3.Row
                user = authenticate_user(con, email, senha)
                con.close()

                row = user
                if not row:
                    st.error("Email ou senha inválidos.")
                    st.stop()
                user = dict(row) if hasattr(row, "keys") else row

                st.session_state.update({
                    "logged_in": True,
                    "user_id": user.get("id") if isinstance(user, dict) else user[0],
                    "user_name": (user.get("name") if isinstance(user, dict) else None) or "Admin",
                    "role": (user.get("role") if isinstance(user, dict) else None) or "member",
                })
                try:
                    st.switch_page("ui")
                except Exception:
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao fazer login: {e}")

# Logout Button
if st.session_state.get("logged_in"):
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    if st.button("Sair", type="secondary"):
        st.session_state.pop("logged_in", None)
        st.session_state.pop("user_id", None)
        st.session_state.pop("role", None)
        action_toast("info", "Saída realizada com sucesso!")
        st.rerun()

# Cadastro Form (condicional)
if ALLOW_SIGNUP:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<h2 class="title-secondary">Não tem conta? Cadastre-se</h2>', unsafe_allow_html=True)
    with st.form("signup_form"):
        st.markdown('<div class="card-bancario">', unsafe_allow_html=True)
        
        new_name = st.text_input("Nome", placeholder="Digite seu nome completo")
        new_email = st.text_input("Email para cadastro", placeholder="Digite seu email")
        new_password = st.text_input("Senha para cadastro", type="password", placeholder="Digite uma senha segura")
        confirm_password = st.text_input("Confirmar Senha", type="password", placeholder="Confirme sua senha")
        signup_submitted = st.form_submit_button("Cadastrar", type="primary")
        
        st.markdown('</div>', unsafe_allow_html=True)

        if signup_submitted:
            if not new_name or not new_email or not new_password or not confirm_password:
                show_banner("error", "Todos os campos são obrigatórios.")
            elif new_password != confirm_password:
                show_banner("error", "As senhas não coincidem.")
            else:
                def do_signup():
                    con = sqlite3.connect(DB_PATH)
                    con.row_factory = sqlite3.Row
                    try:
                        if get_user(con, new_email):
                            return "exists"
                        else:
                            create_user(con, new_name, new_email, new_password, "member", 1)
                            return "success"
                    finally:
                        con.close()
                
                try:
                    result = with_progress("Criando conta...", do_signup)
                    if result == "exists":
                        show_banner("error", "Email já cadastrado.")
                    elif result == "success":
                        show_banner("success", "Cadastro realizado com sucesso! Agora você pode fazer login.")
                        action_toast("success", "Conta criada com sucesso!")
                except Exception as e:
                    show_banner("error", f"Erro ao cadastrar: {e}")

st.caption("Dica: Depois de logar, navegue para **UI**, **Relatórios** ou **Relatórios Simples** pela barra lateral.")




