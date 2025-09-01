
import sys
from pathlib import Path
import pandas as pd
import csv
from io import StringIO
from datetime import datetime

# PATH BOOTSTRAP
# Adiciona o diretório raiz do projeto ao sys.path para que os módulos possam ser encontrados
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from scripts.utils.db_utils import normalize_date

def parse_csv(file_content: str) -> list[dict]:
    transactions = []
    # Detectar automaticamente o delimitador
    try:
        dialect = csv.Sniffer().sniff(file_content, delimiters=",;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "," # Fallback para vírgula se a detecção falhar

    f = StringIO(file_content)
    reader = csv.DictReader(f, delimiter=delimiter)
    
    for row in reader:
        # Normalizar nomes das colunas para minúsculas e remover espaços
        normalized_row = {k.strip().lower(): v for k, v in row.items()}

        date = normalized_row.get("date")
        description = normalized_row.get("description", normalized_row.get("memo", normalized_row.get("note", "")))
        amount_str = normalized_row.get("amount")
        category = normalized_row.get("category", "Uncategorized")
        type_str = normalized_row.get("type")

        if not date or not amount_str:
            continue # Pula linhas sem data ou valor

        try:
            amount = float(amount_str.replace(",", ".")) # Lida com separador decimal vírgula
        except ValueError:
            continue # Pula linhas com valor inválido

        # Inferir tipo se não fornecido
        if not type_str:
            type_str = "income" if amount >= 0 else "expense"

        transactions.append({
            "date": normalize_date(date),
            "description": description,
            "amount": amount,
            "category": category,
            "type": type_str
        })
    return transactions

def parse_ofx(file_content: str) -> list[dict]:
    try:
        from ofxparse import OfxParser
    except ImportError:
        # ofxparse não está disponível
        return []

    transactions = []
    try:
        ofx = OfxParser.parse(StringIO(file_content))
        for transaction in ofx.account.statement.transactions:
            amount = float(transaction.amount)
            # OFX geralmente tem valores positivos para receita e negativos para despesa
            type_str = "income" if amount >= 0 else "expense"
            transactions.append({
                "date": normalize_date(transaction.date),
                "description": transaction.memo,
                "amount": amount,
                "category": transaction.payee if transaction.payee else "Uncategorized", # OFX pode ter payee como categoria
                "type": type_str
            })
    except Exception as e:
        # Logar o erro, mas não quebrar a aplicação
        print(f"Erro ao parsear OFX: {e}")
        return []
    return transactions


