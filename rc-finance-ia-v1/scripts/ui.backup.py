# --- garante que a pasta raiz do projeto está no sys.path ---
import sys
import os
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# === Imports fixos ===
import streamlit as st
import contextlib
from io import StringIO
from datetime import date
import pandas as pd
from sqlite_utils import Database
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json
import time
import tempfile
import hashlib

# --- Paths/banco ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "finance.db"
db = Database(DB_PATH)

# --- Feature flags ---
ENABLE_JSON = False  # JSON import desativado nesta build
ENABLE_OCR = False  # OCR (PNG/JPG) desativado nesta build

# --- Voz (imports defensivos) ---
MIC_OK, MIC_ERR = False, ""
try:
    from streamlit_mic_recorder import mic_recorder

    MIC_OK = True
except Exception as e:
    MIC_ERR = str(e)
    mic_recorder = None

STT_OK, STT_ERR = False, ""
try:
    from scripts.utils.speech_to_text import (
        transcrever_audio,
    )  # def transcrever_audio(path_wav)->str

    STT_OK = True
except Exception as e:
    STT_ERR = str(e)

    def transcrever_audio(_):
        return "Transcrição (demo): teste de áudio."


PARSER_OK, PARSER_ERR = False, ""
try:
    from scripts.utils.voice_command_parser import (
        parse_voice,
    )  # def parse_voice(texto)->dict

    PARSER_OK = True
except Exception as e:
    PARSER_ERR = str(e)

    def parse_voice(txt: str):
        return {
            "type": "expense",
            "description": txt.strip(),
            "amount": 0.0,
            "category": "outros",
            "date": date.today().isoformat(),
        }


def _row_to_id(row: dict) -> int:
    key = f"{row['type']}|{row['description']}|{row['amount']:.2f}|{row['category']}|{row['date']}"
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:12], 16)


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
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


# --- Configuração do Streamlit ---
st.set_page_config(page_title="RC-Finance-IA", layout="wide")

# --- Estilo ---
HIDE_FOOTER = """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
"""
st.markdown(HIDE_FOOTER, unsafe_allow_html=True)


def render_dashboard():
    st.title("📊 Dashboard")
    st.divider()

    # Criar tabela se não existir
    if "transactions" not in db.table_names():
        db["transactions"].create(
            {
                "id": int,
                "type": str,
                "description": str,
                "amount": float,
                "category": str,
                "date": str,
            },
            pk="id",
        )

    # Carrega dados
    df = (
        pd.DataFrame(list(db["transactions"].rows))
        if "transactions" in db.table_names()
        else pd.DataFrame()
    )
    if df.empty:
        st.info(
            "Ainda não há transações. Vá em **Transações** para importar ou usar voz."
        )
        return

    # tipos e datas
    df["type"] = df["type"].astype(str)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # métricas gerais
    income = df.loc[df["type"] == "income", "amount"].sum()
    expense = df.loc[df["type"] == "expense", "amount"].sum()
    saldo = float(income - expense)
    f = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", f(income))
    c2.metric("Despesas", f(expense))
    c3.metric("Saldo", f(saldo))

    st.divider()

    # ---- Filtros (robusto a 1 ou 2 datas) ----
    st.subheader("Filtros")
    c1, c2 = st.columns(2)

    with c1:
        dmin = df["date"].min().date()
        dmax = df["date"].max().date()
        sel = st.date_input(
            "Período",
            value=(dmin, dmax),
            key="filtro_periodo_dashboard_unique",
        )

    # sel pode ser date único ou (date, date)
    from datetime import date as _Date, datetime as _DateTime

    if isinstance(sel, tuple) and len(sel) == 2:
        di, dfim = sel
    elif isinstance(sel, (_Date, _DateTime)):
        di = dfim = sel
    else:
        di, dfim = dmin, dmax  # fallback seguro

    with c2:
        tipo = st.selectbox(
            "Tipo", ["todos", "income", "expense"], index=0, key="tipo_filter_dashboard"
        )

    dfi = df[
        (df["date"] >= pd.to_datetime(str(di)))
        & (df["date"] <= pd.to_datetime(str(dfim)))
    ]
    if tipo != "todos":
        dfi = dfi[dfi["type"] == tipo]

    # ================== Gráfico 1 — Fluxo mensal ==================
    st.subheader("Fluxo mensal (receitas, despesas, saldo)")
    g = dfi.copy()
    g["ym"] = g["date"].dt.to_period("M").astype(str)
    cash = g.pivot_table(
        index="ym", columns="type", values="amount", aggfunc="sum"
    ).fillna(0.0)
    for col in ("income", "expense"):
        if col not in cash.columns:
            cash[col] = 0.0
    cash["saldo"] = cash.get("income", 0.0) - cash.get("expense", 0.0)
    cash = cash.sort_index()

    fig1, ax1 = plt.subplots(figsize=(8, 3))
    cash[["income", "expense", "saldo"]].plot(kind="bar", ax=ax1)
    ax1.set_xlabel("Ano-Mês")
    ax1.set_ylabel("Valor")
    ax1.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    st.pyplot(fig1)

    # ================== Gráfico 2 — Despesas por categoria ==================
    st.subheader("Top categorias (despesas)")
    dexp = dfi[dfi["type"] == "expense"]
    if dexp.empty:
        st.info("Sem despesas no período selecionado.")
    else:
        cat = (
            dexp.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )
        fig2, ax2 = plt.subplots(figsize=(8, 3))
        cat.plot(kind="barh", ax=ax2)
        ax2.invert_yaxis()
        ax2.set_xlabel("Valor")
        ax2.set_ylabel("Categoria")
        plt.tight_layout()
        st.pyplot(fig2)

    st.caption("Dica: ajuste o período para comparar meses e ver picos de gasto.")


def render_voice_section():
    st.subheader("🎤 Entrada por voz (beta)")

    # Status das dependências
    st.write("**Status das dependências:**")
    st.write(f"🎙️ Gravador: {'✅ OK' if MIC_OK else '❌ ' + MIC_ERR}")
    st.write(f"🗣️ Transcrição: {'✅ OK' if STT_OK else '❌ ' + STT_ERR}")
    st.write(f"🧠 Parser: {'✅ OK' if PARSER_OK else '❌ ' + PARSER_ERR}")

    if not MIC_OK:
        st.warning(
            "Gravador não disponível. Você pode digitar diretamente no campo abaixo."
        )

    # Gravação de áudio
    audio_bytes = None
    if MIC_OK:
        audio_data = mic_recorder(
            start_prompt="🎙️ Gravar",
            stop_prompt="⏹️ Parar",
            just_once=True,
            format="wav",
            key="voice_recorder_unique",
        )
        if audio_data:
            if isinstance(audio_data, dict) and "bytes" in audio_data:
                audio_bytes = audio_data["bytes"]
            elif isinstance(audio_data, bytes):
                audio_bytes = audio_data
            else:
                st.warning("Formato inesperado de áudio recebido.")
                audio_bytes = None

    # Transcrição
    transcricao = ""
    if audio_bytes:
        # Salvar áudio temporário
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        try:
            transcricao = transcrever_audio(tmp_path)
            st.success("Áudio transcrito com sucesso!")
        except Exception as e:
            st.error(f"Erro na transcrição: {e}")
            transcricao = "Erro na transcrição"
        finally:
            # Limpar arquivo temporário
            with contextlib.suppress(Exception):
                os.unlink(tmp_path)

    # Campo de texto para edição manual
    texto_final = st.text_area(
        "Transcrição:",
        value=transcricao,
        height=100,
        help="Edite o texto transcrito se necessário",
        key="transcricao_text_area_unique",
    )

    if texto_final.strip():
        # Parse do comando de voz
        try:
            sugestao = parse_voice(texto_final)
        except Exception as e:
            st.error(f"Erro no parser: {e}")
            sugestao = {
                "type": "expense",
                "description": texto_final.strip(),
                "amount": 0.0,
                "category": "outros",
                "date": date.today().isoformat(),
            }

        st.write("**Sugestão do parser:**")
        st.json(sugestao)

        # Formulário de edição
        with st.form("voice_transaction_form", clear_on_submit=True):
            st.write("**Editar transação antes de salvar:**")

            col1, col2 = st.columns(2)
            with col1:
                tipo_edit = st.selectbox(
                    "Tipo",
                    ["income", "expense"],
                    index=0 if sugestao.get("type") == "income" else 1,
                    key="tipo_voice_edit",
                )
                valor_edit = st.number_input(
                    "Valor",
                    value=float(sugestao.get("amount", 0.0)),
                    min_value=0.0,
                    step=0.01,
                    key="valor_voice_edit",
                )

            with col2:
                desc_edit = st.text_input(
                    "Descrição",
                    value=sugestao.get("description", ""),
                    key="desc_voice_edit",
                )
                cat_edit = st.text_input(
                    "Categoria",
                    value=sugestao.get("category", "outros"),
                    key="cat_voice_edit",
                )

            data_edit = st.date_input(
                "Data",
                value=pd.to_datetime(sugestao.get("date", date.today())).date(),
                key="data_voice_edit",
            )

            if st.form_submit_button("💾 Salvar Transação", type="primary"):
                # Criar item editado
                item_editado = {
                    "type": tipo_edit,
                    "description": desc_edit.strip(),
                    "amount": valor_edit,
                    "category": cat_edit.strip(),
                    "date": data_edit.isoformat(),
                }

                # Gerar ID e inserir
                iid = _row_to_id(item_editado)
                try:
                    db["transactions"].insert({"id": iid, **item_editado}, alter=True)
                    st.success(f"Transação salva com ID {iid}")
                    st.rerun()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.warning("Transação duplicada - não foi inserida novamente")
                    else:
                        st.error(f"Erro ao salvar: {e}")

    # Expander para teste do parser (dev)
    with st.expander("🧪 Teste rápido do parser (dev)"):
        teste_frase = st.text_input(
            "Digite uma frase para testar:",
            placeholder="Ex: Gastei 50 reais ontem no mercado",
            key="teste_parser_input",
        )
        if teste_frase:
            try:
                resultado_teste = parse_voice(teste_frase)
                st.code(json.dumps(resultado_teste, indent=2, ensure_ascii=False))
            except Exception as e:
                st.error(f"Erro no teste: {e}")


def render_transactions():
    st.header("📄 Transações")

    # Criar tabela se não existir
    if "transactions" not in db.table_names():
        db["transactions"].create(
            {
                "id": int,
                "type": str,
                "description": str,
                "amount": float,
                "category": str,
                "date": str,
            },
            pk="id",
        )

    # Botão Recarregar
    if st.button(
        "🔄 Recarregar", help="Atualiza a lista e os totais", key="reload_transactions"
    ):
        st.rerun()

    with st.expander("🔎 Diagnóstico do banco"):
        st.write("DB path:", str(DB_PATH))
        st.write("Tabela existe:", "transactions" in db.table_names())
        st.write(
            "Total de linhas:",
            db["transactions"].count if "transactions" in db.table_names() else 0,
        )

    # ===== Upload =====
    st.subheader("Importar por Arquivo (CSV, OFX, PDF)")
    arquivo = st.file_uploader(
        "Selecione um arquivo",
        type=["csv", "ofx", "pdf"],
        key="uploader_tx_unique",
    )
    enviar = st.button("Processar arquivo", type="primary", key="processar_arquivo_btn")

    if enviar and arquivo is not None:
        start_time = time.perf_counter()
        try:
            nome = (arquivo.name or "").strip().lower()

            # ---------------- PDF ----------------
            if nome.endswith(".pdf"):
                try:
                    from scripts.utils.pdf_bank_parser import parse_pdf_statement

                    tmp_path = os.path.join(".", "_upload_tmp.pdf")
                    with open(tmp_path, "wb") as f:
                        f.write(arquivo.getbuffer())
                    dados = parse_pdf_statement(tmp_path)
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                    if dados:
                        ins = dup = 0
                        for item in dados:
                            iid = _row_to_id(item)
                            try:
                                db["transactions"].get(iid)
                                dup += 1
                            except Exception:
                                db["transactions"].insert(
                                    {"id": iid, **item}, alter=True
                                )
                                ins += 1
                        duration = time.perf_counter() - start_time
                        st.success(
                            f"Importação concluída em {duration:.2f}s — Inseridos: {ins} | Duplicados/ignorados: {dup}"
                        )
                        st.rerun()
                    else:
                        st.info(
                            "Não reconheci transações no PDF. (Se for escaneado, trataremos na v1.1 com OCR)."
                        )
                except Exception as e:
                    st.error(f"Erro ao processar PDF: {str(e)}")

            # ---------------- CSV ----------------
            elif nome.endswith(".csv"):
                try:
                    raw = arquivo.getvalue()  # bytes
                    if not raw or not raw.strip():
                        st.error("Arquivo CSV vazio.")
                    else:
                        # detecta encoding comum no Windows/Excel
                        texto = None
                        for enc_try in ("utf-8-sig", "latin-1", "cp1252"):
                            try:
                                texto = raw.decode(enc_try)
                                break
                            except Exception:
                                pass
                        if texto is None:
                            st.error(
                                "Não consegui ler o arquivo. Salve como CSV UTF-8 e tente novamente."
                            )
                        else:
                            # separador: vírgula ou ponto-e-vírgula
                            first = texto.splitlines()[0] if texto.splitlines() else ""
                            sep = ";" if first.count(";") > first.count(",") else ","
                            df = pd.read_csv(StringIO(texto), sep=sep)

                            # normaliza
                            df = _normalize_dataframe(df)

                            inseridos = duplicados = 0
                            tbl = db["transactions"]
                            for _, r in df.iterrows():
                                item = {
                                    "type": str(r["type"]).strip().lower(),
                                    "description": str(r["description"]).strip(),
                                    "amount": float(r["amount"]),
                                    "category": str(r["category"]).strip(),
                                    "date": str(r["date"]).strip(),
                                }
                                iid = _row_to_id(item)
                                try:
                                    tbl.get(iid)
                                    duplicados += 1
                                except Exception:
                                    tbl.insert({"id": iid, **item}, alter=True)
                                    inseridos += 1
                            duration = time.perf_counter() - start_time
                            st.success(
                                f"Importação concluída em {duration:.2f}s — Inseridos: {inseridos} | Duplicados/ignorados: {duplicados}"
                            )
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar CSV: {str(e)}")

            # ---------------- OFX ----------------
            elif nome.endswith(".ofx"):
                try:
                    from scripts.utils.ofx_import import importar_ofx

                    tmp_path = os.path.join(".", "_upload_tmp.ofx")
                    with open(tmp_path, "wb") as f:
                        f.write(arquivo.getbuffer())
                    dados = importar_ofx(tmp_path)
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                    if dados:
                        ins = dup = 0
                        for item in dados:
                            iid = _row_to_id(item)
                            try:
                                db["transactions"].get(iid)
                                dup += 1
                            except Exception:
                                db["transactions"].insert(
                                    {"id": iid, **item}, alter=True
                                )
                                ins += 1
                        duration = time.perf_counter() - start_time
                        st.success(
                            f"Importação concluída em {duration:.2f}s — Inseridos: {ins} | Duplicados/ignorados: {dup}"
                        )
                        st.rerun()
                    else:
                        st.info("Nenhuma transação encontrada no arquivo OFX.")
                except Exception as e:
                    st.error(f"Erro ao processar OFX: {str(e)}")

            # ---------------- Formatos desativados ----------------
            elif nome.endswith(".json"):
                st.warning("Importação JSON desativada nesta build.")
            elif nome.endswith((".png", ".jpg", ".jpeg")):
                st.warning("OCR (PNG/JPG) desativado nesta build.")
            else:
                st.error("Formato de arquivo não suportado.")

        except Exception as e:
            st.error(f"Erro geral no processamento: {str(e)}")

        # ===== Listagem com melhorias =====
        st.subheader("Transações salvas")

        # Filtros
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_texto = st.text_input(
                "Filtrar por texto (descrição/categoria):",
                key="filtro_texto_transactions",
            )
        with col2:
            itens_por_pagina = st.selectbox(
                "Itens por página:", [10, 25, 50], index=1, key="itens_por_pagina"
            )
        with col3:
            st.write("")  # espaçamento

        # Carregar dados
        df = (
            pd.DataFrame(list(db["transactions"].rows))
            if "transactions" in db.table_names()
            else pd.DataFrame()
        )

        if df.empty:
            st.info("Nenhuma transação encontrada.")
            render_voice_section()
            return

        # Aplicar filtro de texto
        if filtro_texto:
            mask = df["description"].astype(str).str.contains(
                filtro_texto, case=False, na=False
            ) | df["category"].astype(str).str.contains(
                filtro_texto, case=False, na=False
            )
            df_filtrado = df[mask]
        else:
            df_filtrado = df.copy()

        total_items = len(df_filtrado)
        if total_items == 0:
            st.info("Nenhuma transação corresponde ao filtro.")
            render_voice_section()
            return

        total_pages = max(1, (total_items + itens_por_pagina - 1) // itens_por_pagina)

        # Controle de página
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pagina_atual = st.number_input(
                f"Página (1-{total_pages}):",
                min_value=1,
                max_value=total_pages,
                value=1,
                key="pagina_atual",
            )

        # Paginação
        start_idx = (pagina_atual - 1) * itens_por_pagina
        end_idx = start_idx + itens_por_pagina
        df_pagina = df_filtrado.iloc[start_idx:end_idx].copy()

        # 🔧 CONVERSÃO CRÍTICA: deixe 'date' como datetime.date p/ DateColumn funcionar
        df_pagina["date"] = pd.to_datetime(df_pagina["date"], errors="coerce").dt.date

        # Adicionar coluna de seleção
        if not df_pagina.empty:
            df_display = df_pagina.copy()
            df_display.insert(0, "Selecionar", False)

            # Editor de dados
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar"),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "type": st.column_config.SelectboxColumn(
                        "Tipo", options=["income", "expense"]
                    ),
                    "description": st.column_config.TextColumn("Descrição"),
                    "amount": st.column_config.NumberColumn(
                        "Valor", min_value=0.0, step=0.01
                    ),
                    "category": st.column_config.TextColumn("Categoria"),
                    # Agora é compatível, pois df_display["date"] é datetime.date
                    "date": st.column_config.DateColumn("Data"),
                },
                hide_index=True,
                key="transactions_editor",
            )

            # Botões de ação
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("✏️ Salvar Edições", key="salvar_edicoes"):
                    try:
                        from datetime import date as _D

                        for idx, row in edited_df.iterrows():
                            if not bool(row["Selecionar"]):
                                continue

                            # Validações básicas
                            if float(row["amount"]) < 0:
                                st.error(f"Valor deve ser >= 0 (linha {idx+1})")
                                continue
                            if str(row["type"]).strip().lower() not in [
                                "income",
                                "expense",
                            ]:
                                st.error(
                                    f"Tipo deve ser 'income' ou 'expense' (linha {idx+1})"
                                )
                                continue

                            # Normalizar a data: aceitar datetime.date, pandas.Timestamp ou string
                            raw_d = row["date"]
                            if pd.isna(raw_d):
                                st.error(f"Data inválida (linha {idx+1})")
                                continue
                            # pandas.Timestamp -> date
                            if isinstance(raw_d, pd.Timestamp):
                                raw_d = raw_d.date()
                            # string -> date
                            if isinstance(raw_d, str):
                                try:
                                    raw_d = pd.to_datetime(raw_d, errors="raise").date()
                                except Exception:
                                    st.error(f"Data inválida (linha {idx+1})")
                                    continue
                            # garantia final: objeto com isoformat()
                            try:
                                iso = raw_d.isoformat()
                            except Exception:
                                st.error(f"Data inválida (linha {idx+1})")
                                continue

                            item_atualizado = {
                                "type": str(row["type"]).strip().lower(),
                                "description": str(row["description"]).strip(),
                                "amount": float(row["amount"]),
                                "category": str(row["category"]).strip(),
                                "date": iso,
                            }

                            try:
                                db["transactions"].update(
                                    int(row["id"]), item_atualizado
                                )
                            except Exception:
                                # fallback: delete + insert
                                db["transactions"].delete(int(row["id"]))
                                db["transactions"].insert(
                                    {"id": int(row["id"]), **item_atualizado},
                                    alter=True,
                                )

                        st.success("Edições salvas com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar edições: {e}")

            with col2:
                if st.button("🗑️ Excluir Selecionadas", key="excluir_selecionadas"):
                    try:
                        ids_para_excluir = [
                            int(r["id"])
                            for _, r in edited_df.iterrows()
                            if bool(r["Selecionar"])
                        ]
                        if ids_para_excluir:
                            for id_item in ids_para_excluir:
                                db["transactions"].delete(id_item)
                            st.success(
                                f"{len(ids_para_excluir)} transação(ões) excluída(s)!"
                            )
                            st.rerun()
                        else:
                            st.warning("Nenhuma transação selecionada para exclusão.")
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")

            # Dados selecionados (p/ export)
            selecionadas = edited_df[edited_df["Selecionar"] == True]  # noqa: E712
            dados_para_exportar = (
                selecionadas.drop(columns=["Selecionar"], errors="ignore")
                if not selecionadas.empty
                else df_filtrado.copy()
            )
            # Converter 'date' p/ string ISO antes de exportar (garante compatibilidade)
            dados_para_exportar = dados_para_exportar.copy()
            try:
                dados_para_exportar["date"] = pd.to_datetime(
                    dados_para_exportar["date"], errors="coerce"
                ).dt.date
                dados_para_exportar["date"] = dados_para_exportar["date"].apply(
                    lambda d: d.isoformat() if hasattr(d, "isoformat") else str(d)
                )
            except Exception:
                pass

            with col3:
                if not dados_para_exportar.empty:
                    csv_data = dados_para_exportar.to_csv(index=False)
                    st.download_button(
                        "📥 Exportar CSV",
                        data=csv_data,
                        file_name=f"transacoes_{date.today().isoformat()}.csv",
                        mime="text/csv",
                        key="export_csv",
                    )

            with col4:
                if not dados_para_exportar.empty:
                    json_data = dados_para_exportar.to_json(
                        orient="records", indent=2, force_ascii=False
                    )
                    st.download_button(
                        "📥 Exportar JSON",
                        data=json_data,
                        file_name=f"transacoes_{date.today().isoformat()}.json",
                        mime="application/json",
                        key="export_json",
                    )

            st.caption(
                f"Mostrando {len(df_pagina)} de {total_items} transações (página {pagina_atual} de {total_pages})"
            )

        # Seção de voz
        render_voice_section()


def render_goals():
    st.header("🎯 Metas")

    # Criar tabela se não existir
    if "goals" not in db.table_names():
        db["goals"].create(
            {
                "id": int,
                "description": str,
                "target_amount": float,
                "current_amount": float,
                "target_date": str,
                "category": str,
            },
            pk="id",
        )

    # Carregar metas
    goals_df = (
        pd.DataFrame(list(db["goals"].rows))
        if "goals" in db.table_names()
        else pd.DataFrame()
    )

    if goals_df.empty:
        st.info("Nenhuma meta cadastrada ainda.")
    else:
        # Editor de metas
        edited_goals = st.data_editor(
            goals_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "description": st.column_config.TextColumn("Descrição"),
                "target_amount": st.column_config.NumberColumn(
                    "Valor Meta", min_value=0.0, step=0.01
                ),
                "current_amount": st.column_config.NumberColumn(
                    "Valor Atual", min_value=0.0, step=0.01
                ),
                "target_date": st.column_config.DateColumn("Data Meta"),
                "category": st.column_config.TextColumn("Categoria"),
            },
            num_rows="dynamic",
            key="goals_editor",
        )

        # Salvar alterações
        if st.button("💾 Salvar Metas", key="salvar_metas"):
            try:
                # Limpar tabela e reinserir
                db["goals"].delete_where()
                for idx, row in edited_goals.iterrows():
                    if pd.notna(row["description"]) and row["description"].strip():
                        meta = {
                            "id": int(row["id"]) if pd.notna(row["id"]) else idx + 1,
                            "description": str(row["description"]).strip(),
                            "target_amount": (
                                float(row["target_amount"])
                                if pd.notna(row["target_amount"])
                                else 0.0
                            ),
                            "current_amount": (
                                float(row["current_amount"])
                                if pd.notna(row["current_amount"])
                                else 0.0
                            ),
                            "target_date": (
                                str(row["target_date"]).strip()
                                if pd.notna(row["target_date"])
                                else date.today().isoformat()
                            ),
                            "category": (
                                str(row["category"]).strip()
                                if pd.notna(row["category"])
                                else "geral"
                            ),
                        }
                        db["goals"].insert(meta, alter=True)
                st.success("Metas salvas com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar metas: {e}")

        # Exportar metas
        if not goals_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                csv_data = goals_df.to_csv(index=False)
                st.download_button(
                    "📥 Exportar Metas (CSV)",
                    data=csv_data,
                    file_name=f"metas_{date.today().isoformat()}.csv",
                    mime="text/csv",
                    key="export_goals_csv",
                )
            with col2:
                json_data = goals_df.to_json(orient="records", indent=2)
                st.download_button(
                    "📥 Exportar Metas (JSON)",
                    data=json_data,
                    file_name=f"metas_{date.today().isoformat()}.json",
                    mime="application/json",
                    key="export_goals_json",
                )


# ===== MAIN =====
def main():
    # Sidebar
    st.sidebar.title("RC-Finance-IA")
    pagina = st.sidebar.radio(
        "Navegação", ["Dashboard", "Transações", "Metas"], key="navegacao_principal"
    )

    # Roteamento
    if pagina == "Dashboard":
        render_dashboard()
    elif pagina == "Transações":
        render_transactions()
    elif pagina == "Metas":
        render_goals()


if __name__ == "__main__":
    main()
