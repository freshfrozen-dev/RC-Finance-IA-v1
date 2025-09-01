# scripts/utils/pdf_bank_parser.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Union

try:
    import pdfplumber

    _HAVE_PDFPLUMBER = True
except Exception:
    _HAVE_PDFPLUMBER = False

# Padrão para reconhecer linhas de transação em extratos bancários
PAT_LINHA = re.compile(
    r"^(?P<tipo>Débito|Debito|Crédito|Credito)\s+"
    r"(?P<data>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<valor>-?\s*R\$\s*[\d\.\,]+)\s+"
    r"(?P<ref>\S+)\s+"
    r"(?P<memo>.+)$",
    flags=re.IGNORECASE,
)


def _to_amount(txt: str) -> float:
    """Converte string de valor monetário para float"""
    try:
        s = txt.replace("R$", "").replace(" ", "")
        # Remove separadores de milhar e converte vírgula decimal para ponto
        if "," in s and "." in s:  # Ex: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:  # Ex: 1234,56
            s = s.replace(",", ".")
        # Se tiver apenas ponto, assume que é decimal (Ex: 1234.56)
        return abs(float(s))  # Sempre retorna valor absoluto
    except Exception:
        return 0.0


def _norm_date(d: str) -> str:
    """Normaliza data de DD/MM/YYYY para YYYY-MM-DD"""
    try:
        return datetime.strptime(d, "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return d


def parse_pdf_statement(path_pdf: str) -> List[Dict[str, Union[str, float]]]:
    """
    Parser PDF textual simples que retorna lista normalizada.

    Args:
        path_pdf: Caminho para o arquivo PDF

    Returns:
        Lista de transações normalizadas:
        {type: 'income'|'expense', description: str, amount: float, category: str, date: 'YYYY-MM-DD'}
    """
    if not _HAVE_PDFPLUMBER:
        print(
            "Biblioteca pdfplumber não está disponível. Instale com: pip install pdfplumber"
        )
        return []

    try:
        # 1) extrai todas as linhas de texto
        linhas = []
        with pdfplumber.open(path_pdf) as pdf:
            for p in pdf.pages:
                t = p.extract_text() or ""
                for ln in t.splitlines():
                    ln = " ".join(ln.split())  # normaliza espaços
                    if ln:
                        linhas.append(ln)

        # 2) junta quebras do "memorando": novo bloco quando começa com Débito/Crédito
        blocos = []
        atual = ""
        for ln in linhas:
            if re.match(r"^(Débito|Debito|Crédito|Credito)\b", ln, flags=re.IGNORECASE):
                if atual:
                    blocos.append(atual.strip())
                atual = ln
            else:
                atual += " " + ln
        if atual:
            blocos.append(atual.strip())

        # 3) aplica regex em cada bloco
        out = []
        for b in blocos:
            m = PAT_LINHA.match(b)
            if not m:
                continue

            tipo = m.group("tipo").lower()
            data = _norm_date(m.group("data"))
            valor_txt = m.group("valor")
            ref = m.group("ref")
            memo = m.group("memo").strip()

            amount = _to_amount(valor_txt)
            is_credit = tipo.startswith("cr")

            item = {
                "type": "income" if is_credit else "expense",
                "description": memo if memo else ref,
                "amount": amount,
                "category": "",  # PDF não tem categoria padrão
                "date": data,
            }
            out.append(item)

        return out

    except Exception as e:
        print(f"Erro ao processar PDF: {e}")
        return []
