# PATH BOOTSTRAP
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sqlite3
from typing import Any, Dict
from loguru import logger
import pandas as pd

from scripts.utils.db_utils import insert_transaction, update_transaction, create_goal, get_transactions_filtered
from scripts.utils.export import export_df_csv, export_df_excel

def execute_intent(intent_name: str, intent_obj: Dict[str, Any], user_id: int, con: sqlite3.Connection) -> Dict[str, Any]:
    logger.info(f"Executando intenção: {intent_name} com dados: {intent_obj} para user_id: {user_id}")

    if intent_name == "AddTransaction":
        row_id = insert_transaction(
            con,
            date=intent_obj.get("date"),
            type=intent_obj.get("type"),
            category=intent_obj.get("category"),
            description=intent_obj.get("description"),
            amount=intent_obj.get("amount"),
            user_id=user_id
        )
        con.commit()
        return {"status": "ok", "message": f"Transação de {intent_obj.get('amount')} em {intent_obj.get('category')} adicionada com sucesso. ID: {row_id}"}

    elif intent_name == "EditTransaction":
        if intent_obj.get("needs_disambiguation"):
            candidates = intent_obj.get("candidates", [])
            return {"status": "needs_disambiguation", "message": "Múltiplas transações encontradas. Por favor, selecione uma.", "candidates": candidates}
        else:
            tx_id = intent_obj.get("selector").get("id")
            changes = intent_obj.get("changes")
            rows_affected = update_transaction(con, id=tx_id, user_id=user_id, fields=changes)
            con.commit()
            if rows_affected > 0:
                return {"status": "ok", "message": f"Transação {tx_id} atualizada com sucesso."}
            else:
                return {"status": "error", "message": f"Falha ao atualizar transação {tx_id}."}

    elif intent_name == "CreateGoal":
        goal_id = create_goal(
            con,
            name=intent_obj.get("name"),
            target_amount=intent_obj.get("target_amount"),
            due_date=intent_obj.get("due_date"),
            user_id=user_id
        )
        con.commit()
        return {"status": "ok", "message": f"Meta '{intent_obj.get('name')}' criada com sucesso. ID: {goal_id}"}

    elif intent_name == "ExportReport":
        df = get_transactions_filtered(con, user_id, intent_obj.get("start_date"), intent_obj.get("end_date"), intent_obj.get("categories"))
        if df.empty:
            return {"status": "error", "message": "Nenhuma transação encontrada para os filtros especificados."}

        if intent_obj.get("format") == "csv":
            file_bytes = export_df_csv(df)
            filename = f"relatorio_{intent_obj.get('start_date')}_{intent_obj.get('end_date')}.csv"
            mime = "text/csv"
        else:
            file_bytes = export_df_excel(df)
            filename = f"relatorio_{intent_obj.get('start_date')}_{intent_obj.get('end_date')}.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        return {"status": "ok", "message": "Relatório gerado com sucesso.", "download": {"filename": filename, "bytes": file_bytes, "mime": mime}}

    else:
        return {"status": "error", "message": "Intenção não reconhecida."}

if __name__ == "__main__":
    # Exemplo de uso (sem integração real com DB)
    print("Testando AddTransaction...")
    # Para testar, você precisaria de uma conexão real com o banco de dados
    # import sqlite3
    # con = sqlite3.connect("finance.db") # ou o caminho correto para o seu DB
    # result = execute_intent("AddTransaction", {"amount": 100.0, "category": "alimentacao", "date": "2025-08-29", "description": "Almoço", "type": "despesa"}, 1, con)
    # print(result)

    print("\nTestando ExportReport...")
    # result = execute_intent("ExportReport", {"format": "csv", "start_date": "2025-08-01", "end_date": "2025-08-29"}, 1, con)
    # print(result)

    print("\nTestando EditTransaction (com desambiguação)...")
    # result = execute_intent("EditTransaction", {"needs_disambiguation": True, "candidates": [{"id": 1, "desc": "Transacao A"}, {"id": 2, "desc": "Transacao B"}]}, 1, con)
    # print(result)

    print("\nTestando CreateGoal...")
    # result = execute_intent("CreateGoal", {"name": "Viagem", "target_amount": 5000.0, "due_date": "2026-12-31"}, 1, con)
    # print(result)


