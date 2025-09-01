# PATH BOOTSTRAP
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
from pathlib import Path
import sqlite3, io
import importlib
from datetime import date
try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("rc-finance-ia")
import traceback

from scripts.utils.speech_to_text import transcrever_audio
from scripts.utils.voice_command_parser import parse_command
from scripts.utils.voice_intents_exec import execute_intent
from scripts.utils.ui_components import (
    show_banner, action_toast, with_progress, show_empty_state, load_custom_css
)

ROOT = Path(__file__).resolve().parents[1] # scripts/
DB_PATH = (ROOT.parent / "data" / "finance.db").resolve()

st.set_page_config(page_title="Voz", page_icon="🎤")

# Injeção do CSS
st.markdown("<link rel=\'stylesheet\' href=\'assets/styles.css\'>", unsafe_allow_html=True)

# Gate de login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    try:
        st.switch_page("login")  # label da página de login
    except Exception:
        st.rerun()                # fallback seguro
    st.stop()

st.markdown('<h1 class="title-primary">🎙️ Comandos de Voz</h1>', unsafe_allow_html=True)

# 2. Entrada de áudio
st.markdown('<h2 class="title-secondary">Entrada de Áudio</h2>', unsafe_allow_html=True)
st.markdown('<div class="card-bancario">', unsafe_allow_html=True)
audio_file = st.file_uploader("Faça upload de um arquivo de áudio (.wav, .mp3, .m4a)", type=["wav", "mp3", "m4a"])

if audio_file:
    st.audio(audio_file, format=audio_file.type)

    # 3. Transcrever
    if st.button("Transcrever", type="primary"):
        try:
            with st.spinner("Transcrevendo áudio..."):
                transcribed_text = transcrever_audio(audio_file.read())
                st.session_state.transcribed_text = transcribed_text
                st.toast("Áudio transcrito com sucesso!", icon="✅")
        except Exception as e:
            st.error(f"Erro na transcrição: {e}")

st.markdown('</div>', unsafe_allow_html=True)

if 'transcribed_text' in st.session_state and st.session_state.transcribed_text:
    st.markdown('<h2 class="title-secondary">Texto Transcrito</h2>', unsafe_allow_html=True)
    st.markdown('<div class="card-bancario">', unsafe_allow_html=True)
    st.text_area("", value=st.session_state.transcribed_text, height=150, key="transcribed_text_area")

    # 4. Interpretar comando
    if st.button("Interpretar Comando", type="primary"):
        try:
            with st.spinner("Interpretando comando..."):
                intent_name, intent_obj = parse_command(st.session_state.transcribed_text, hoje=date.today())
                st.session_state.intent_name = intent_name
                st.session_state.intent_obj = intent_obj
                st.toast("Comando interpretado!", icon="✅")
        except Exception as e:
            st.error(f"Erro na interpretação: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

if 'intent_name' in st.session_state and st.session_state.intent_name:
    st.markdown('<h2 class="title-secondary">Intenção Detectada</h2>', unsafe_allow_html=True)
    st.markdown('<div class="card-bancario">', unsafe_allow_html=True)
    st.write(f"**Nome da Intenção:** {st.session_state.intent_name}")
    st.json(st.session_state.intent_obj)

    # 5. Executar
    if st.button("Confirmar e Executar", type="primary"):
        def do_execution():
            return execute_intent(st.session_state.intent_name, st.session_state.intent_obj, user_id=st.session_state.user_id)
        
        try:
            result = with_progress("Executando comando...", do_execution)
            if result.get("status") == "ok":
                show_banner("success", result.get("message"))
                action_toast("success", "Comando executado com sucesso!")
                if result.get("download"):
                    dl = result["download"]
                    st.download_button("Baixar arquivo gerado", data=dl["bytes"], file_name=dl["filename"], mime=dl["mime"])
            else:
                show_banner("error", result.get("message"))
        except Exception as e:
            show_banner("error", f"Erro na execução: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# 6. Histórico compacto (últimos 5 comandos)
st.markdown('<h2 class="h2">Histórico de Comandos</h2>', unsafe_allow_html=True)
if 'command_history' not in st.session_state:
    st.session_state.command_history = []

if 'intent_name' in st.session_state and st.session_state.intent_name:
    if st.button("Adicionar ao Histórico", type="secondary"):
        command = {
            "text": st.session_state.transcribed_text[:50] + "..." if len(st.session_state.transcribed_text) > 50 else st.session_state.transcribed_text,
            "intent_name": st.session_state.intent_name
        }
        st.session_state.command_history.insert(0, command)
        if len(st.session_state.command_history) > 5:
            st.session_state.command_history.pop()
        st.toast("Comando adicionado ao histórico!", icon="ℹ️")

if st.session_state.command_history:
    st.markdown("**Últimos 5 comandos:**")
    for i, cmd in enumerate(st.session_state.command_history):
        with st.container():
            st.markdown(f"**{i+1}.** {cmd['text']}")
            st.markdown(f"<span class='badge badge-info'>{cmd['intent_name']}</span>", unsafe_allow_html=True)
            st.divider()
else:
    st.markdown('''
    <div class="empty-state">
        <h3>Histórico vazio</h3>
        <p>Nenhum comando no histórico ainda.</p>
    </div>
    ''', unsafe_allow_html=True)




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


