# scripts/utils/ofx_import.py
from __future__ import annotations

import os
from io import BytesIO, StringIO
from typing import Dict, List, Union

try:
    from ofxparse import OfxParser

    _HAVE_OFXPARSE = True
except Exception:
    _HAVE_OFXPARSE = False


def _read_text_safely(src: Union[bytes, BytesIO, str]) -> str:
    """
    Lê bytes/BytesIO/caminho e tenta decodificar em várias codificações comuns no Brasil.
    """
    data = None

    if isinstance(src, str):
        # É um caminho de arquivo
        if os.path.exists(src):
            with open(src, "rb") as f:
                data = f.read()
        else:
            raise FileNotFoundError(f"Arquivo não encontrado: {src}")
    elif isinstance(src, bytes):
        # É bytes direto
        data = src
    elif isinstance(src, BytesIO):
        # É BytesIO
        src.seek(0)
        data = src.read()
    else:
        # Tenta ler como file-like object (ex: st.file_uploader retorna um objeto com read())
        try:
            if hasattr(src, "seek"):
                src.seek(0)
            data = src.read()
        except Exception:
            raise ValueError(f"Tipo de entrada não suportado: {type(src)}")

    if isinstance(data, str):  # já é texto
        return data

    # ordem de tentativas de encoding
    for enc in ("utf-8-sig", "latin-1", "cp1252", "utf-8"):
        try:
            return data.decode(enc)
        except Exception:
            pass

    # último recurso: chardet (se instalado)
    try:
        import chardet

        enc = chardet.detect(data).get("encoding") or "latin-1"
        return data.decode(enc, errors="ignore")
    except Exception:
        return data.decode("latin-1", errors="ignore")


def importar_ofx(src: Union[bytes, BytesIO, str]) -> List[Dict[str, Union[str, float]]]:
    """
    Importa transações de arquivo OFX.

    Args:
        src: Pode ser bytes, BytesIO, ou caminho do arquivo (str)

    Returns:
        Lista de transações normalizadas:
        {type: 'income'|'expense', description: str, amount: float, category: str, date: 'YYYY-MM-DD'}
    """
    if not _HAVE_OFXPARSE:
        raise ImportError(
            "Biblioteca ofxparse não está disponível. Instale com: pip install ofxparse"
        )

    try:
        text = _read_text_safely(src)
        ofx = OfxParser.parse(StringIO(text))

        txs = []

        # Verifica se há conta e extrato
        if not hasattr(ofx, "account") or not ofx.account:
            return []

        if not hasattr(ofx.account, "statement") or not ofx.account.statement:
            return []

        if not hasattr(ofx.account.statement, "transactions"):
            return []

        for t in ofx.account.statement.transactions:
            # Extrai informações da transação
            memo = ""
            if hasattr(t, "memo") and t.memo:
                memo = str(t.memo).strip()
            elif hasattr(t, "payee") and t.payee:
                memo = str(t.payee).strip()
            elif hasattr(t, "name") and t.name:
                memo = str(t.name).strip()

            if not memo:
                memo = "Transação OFX"

            # Valor da transação
            amt = float(t.amount) if hasattr(t, "amount") else 0.0

            # Data da transação
            date_str = ""
            if hasattr(t, "date") and t.date:
                try:
                    date_str = t.date.strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(t.date)[:10]  # pega apenas YYYY-MM-DD

            txs.append(
                {
                    "type": "income" if amt > 0 else "expense",
                    "description": memo,
                    "amount": abs(amt),
                    "category": "",  # OFX não tem categoria padrão
                    "date": date_str,
                }
            )

        return txs

    except Exception as e:
        # Em caso de erro, retorna lista vazia em vez de quebrar
        print(f"Erro ao processar OFX: {e}")
        return []
