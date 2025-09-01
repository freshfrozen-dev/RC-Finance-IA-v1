import streamlit as st

def show_skeleton_metric(w=180, h=22):
    """Exibe um skeleton para métricas"""
    st.markdown(f"<div class='skeleton' style='width:{w}px;height:{h}px'></div>", unsafe_allow_html=True)

def show_skeleton_table(rows=6, cols=5, cell_w=120, cell_h=20, gap=8):
    """Exibe um skeleton para tabelas"""
    html = f"<div style='display:grid;grid-template-columns:{' '.join([f'{cell_w}px' for _ in range(cols)])};gap:{gap}px'>"
    for _ in range(rows * cols):
        html += f"<div class='skeleton' style='height:{cell_h}px'></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def show_banner(kind, text):
    """Exibe um banner de feedback"""
    if kind == "info":
        st.info(text)
    elif kind == "success":
        st.success(text)
    elif kind == "warn":
        st.warning(text)
    else:
        st.error(text)

def action_toast(kind, text):
    """Exibe um toast de ação"""
    if kind == "success":
        st.toast(text, icon="✅")
    elif kind == "info":
        st.toast(text, icon="ℹ️")
    elif kind == "warn":
        st.toast(text, icon="⚠️")
    else:
        st.toast(text, icon="❌")

def with_progress(label, work_fn):
    """Executa uma função com spinner de progresso"""
    with st.spinner(label):
        return work_fn()



def create_metric_card(title, value):
    st.markdown(
        f"""
        <div class="card-bancario">
            <p class="title-secondary">{title}</p>
            <p class="metric-value">{value}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


