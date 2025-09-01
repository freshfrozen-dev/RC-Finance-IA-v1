

import sys
from pathlib import Path

# PATH BOOTSTRAP
# Adiciona o diretório raiz do projeto ao sys.path para que os módulos possam ser encontrados
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from sqlite_utils import Database
import sqlite3
from typing import Any, Dict, Optional
import pandas as pd
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "finance.db"

def get_db():
    return Database(DB_PATH)

def init_db():
    db = get_db()
    if "transactions" not in db.table_names():
        db["transactions"].create(
            {
                "id": int,
                "user_id": int,
                "date": str,
                "description": str,
                "amount": float,
                "category": str,
                "type": str
            },
            pk="id",
            if_not_exists=True
        )
    if "goals" not in db.table_names():
        db["goals"].create(
            {
                "id": int,
                "user_id": int,
                "name": str,
                "target_amount": float,
                "due_date": str,
                "funded_amount": float,
                "created_at": str
            },
            pk="id",
            if_not_exists=True,
            defaults={
                "funded_amount": 0.0,
                "created_at": datetime.now().strftime("%Y-%m-%d")
            }
        )
    else:
        # Ensure 'created_at' column exists if table already exists
        if "created_at" not in db["goals"].columns_dict:
            db["goals"].add_column("created_at", str)
            db["goals"].update_where("created_at IS NULL", {"created_at": datetime.now().strftime("%Y-%m-%d")})

def normalize_date(s) -> str:
    if isinstance(s, datetime):
        return s.strftime("%Y-%m-%d")
    try:
        # Tenta parsear vários formatos de data
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"): # Adicione mais formatos se necessário
            try:
                return datetime.strptime(str(s), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Se nenhum formato conhecido funcionar, tenta o parse padrão do pandas
        return pd.to_datetime(s).strftime("%Y-%m-%d")
    except Exception as e:
        raise ValueError(f"Não foi possível normalizar a data: {s} - {e}")

def insert_transaction(user_id: int, date: str, description: str, amount: float, category: str, type: str) -> Dict[str, Any]:
    db = get_db()
    con = db.conn
    normalized_date = normalize_date(date)
    
    # Inferir tipo se necessário
    if type is None or type == "":
        type = "income" if amount >= 0 else "expense"

    # Deduplicação leve: (user_id, date, description, amount, category) são iguais
    existing_transaction = con.execute(
        "SELECT id FROM transactions WHERE user_id = ? AND date = ? AND description = ? AND amount = ? AND category = ?",
        (user_id, normalized_date, description, amount, category)
    ).fetchone()

    if existing_transaction:
        return {"inserted": False, "reason": "Duplicate transaction"}

    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO transactions(user_id, date, description, amount, category, type)
            VALUES (?,?,?,?,?,?)
            """
            ,
            (user_id, normalized_date, description, amount, category, type)
        )
        con.commit()
        return {"inserted": True, "reason": ""}
    except Exception as e:
        con.rollback()
        return {"inserted": False, "reason": str(e)}

def bulk_insert_transactions(user_id: int, rows: list[dict]) -> Dict[str, int]:
    inserted_count = 0
    duplicates_count = 0
    failed_count = 0
    for row in rows:
        # Assegura que todos os campos necessários estão presentes, com valores padrão se ausentes
        date = row.get("date")
        description = row.get("description", "")
        amount = row.get("amount", 0.0)
        category = row.get("category", "Uncategorized")
        type = row.get("type")

        # Tenta inferir o tipo se não fornecido ou vazio
        if type is None or type == "":
            type = "income" if amount >= 0 else "expense"

        try:
            result = insert_transaction(user_id, date, description, amount, category, type)
            if result["inserted"]:
                inserted_count += 1
            else:
                if result["reason"] == "Duplicate transaction":
                    duplicates_count += 1
                else:
                    failed_count += 1
        except Exception:
            failed_count += 1
    return {"inserted": inserted_count, "duplicates": duplicates_count, "failed": failed_count}

def get_transactions_filtered(
    user_id: int,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    categories: Optional[list[str]] = None,
    type_filter: Optional[str] = None  # None|"income"|"expense"
) -> pd.DataFrame:
    db = get_db()
    con = db.conn
    query = "SELECT date, description, category, type, amount FROM transactions WHERE user_id = ?"
    params = [user_id]

    if date_start:
        query += " AND date >= ?"
        params.append(normalize_date(date_start))
    if date_end:
        query += " AND date <= ?"
        params.append(normalize_date(date_end))
    if categories and len(categories) > 0:
        placeholders = ", ".join(["?" for _ in categories])
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
    if type_filter in ["income", "expense"]:
        query += " AND type = ?"
        params.append(type_filter)

    df = pd.read_sql_query(query, con, params=params)
    return df

# Manter a função salvar_transacao para compatibilidade, mas adaptar para usar insert_transaction
def salvar_transacao(transaction_data: dict):
    db = get_db()
    con = db.conn
    init_db() # Garante que a tabela 'transactions' existe
    
    # A função original `salvar_transacao` usava um ID baseado no conteúdo e `alter=True` para upsert.
    # Como as novas funções `insert_transaction` e `update_transaction` usam IDs autoincrementais
    # e são chamadas pelo executor de intents, esta função `salvar_transacao` pode ser simplificada
    # para apenas inserir, ou ser removida se não houver mais chamadas a ela.
    # Por enquanto, assume-se que esta função é para novas transações.
    insert_transaction(
        user_id=transaction_data["user_id"],
        date=transaction_data["date"],
        type=transaction_data["type"],
        category=transaction_data["category"],
        description=transaction_data.get("description"),
        amount=transaction_data["amount"]
    )
    con.commit()







def create_goal(user_id: int, name: str, target_amount: float, due_date: Optional[str]) -> dict:
    db = get_db()
    con = db.conn
    created_at = normalize_date(datetime.now())
    normalized_due_date = normalize_date(due_date) if due_date else None

    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO goals(user_id, name, target_amount, due_date, funded_amount, created_at)
            VALUES (?,?,?,?,?,?)
            """
            ,
            (user_id, name, target_amount, normalized_due_date, 0.0, created_at)
        )
        con.commit()
        goal_id = cur.lastrowid
        return {"id": goal_id, "user_id": user_id, "name": name, "target_amount": target_amount, "due_date": normalized_due_date, "funded_amount": 0.0, "created_at": created_at}
    except Exception as e:
        con.rollback()
        raise e




def update_goal(goal_id: int, user_id: int, *, name: Optional[str] = None, target_amount: Optional[float] = None, due_date: Optional[str] = None) -> dict:
    db = get_db()
    con = db.conn
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if target_amount is not None:
        updates.append("target_amount = ?")
        params.append(target_amount)
    if due_date is not None:
        updates.append("due_date = ?")
        params.append(normalize_date(due_date))

    if not updates:
        raise ValueError("Nenhum campo para atualizar.")

    params.append(goal_id)
    params.append(user_id)

    try:
        cur = con.cursor()
        cur.execute(
            f"UPDATE goals SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            params
        )
        con.commit()
        # Re-fetch the updated row to get all columns
        cur.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        updated_row = cur.fetchone()
        if updated_row:
            columns = [description[0] for description in cur.description]
            return dict(zip(columns, updated_row))
        else:
            raise ValueError("Meta não encontrada ou não pertence ao usuário.")
    except Exception as e:
        con.rollback()
        raise e




def fund_goal(goal_id: int, user_id: int, amount: float) -> dict:
    db = get_db()
    con = db.conn

    try:
        cur = con.cursor()
        # Get current funded_amount
        cur.execute("SELECT funded_amount FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        result = cur.fetchone()

        if not result:
            raise ValueError("Meta não encontrada ou não pertence ao usuário.")

        current_funded_amount = result[0]
        new_funded_amount = max(0.0, current_funded_amount + amount)

        cur.execute(
            "UPDATE goals SET funded_amount = ? WHERE id = ? AND user_id = ?",
            (new_funded_amount, goal_id, user_id)
        )
        con.commit()
        # Re-fetch the updated row to get all columns
        cur.execute("SELECT * FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        updated_row = cur.fetchone()
        if updated_row:
            columns = [description[0] for description in cur.description]
            return dict(zip(columns, updated_row))
        else:
            raise ValueError("Meta não encontrada após atualização.")
    except Exception as e:
        con.rollback()
        raise e




def delete_goal(goal_id: int, user_id: int) -> bool:
    db = get_db()
    con = db.conn

    try:
        cur = con.cursor()
        cur.execute(
            "DELETE FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, user_id)
        )
        con.commit()
        return cur.rowcount > 0
    except Exception as e:
        con.rollback()
        raise e




def list_goals(user_id: int) -> pd.DataFrame:
    db = get_db()
    con = db.conn
    query = "SELECT id, name, target_amount, funded_amount, due_date, created_at FROM goals WHERE user_id = ?"
    df = pd.read_sql_query(query, con, params=[user_id])
    return df




def progress(goal_row) -> float:
    if goal_row["target_amount"] == 0:
        return 0.0
    return goal_row["funded_amount"] / goal_row["target_amount"]



def update_transaction(con: sqlite3.Connection, id: int, user_id: int, fields: Dict[str, Any]) -> int:
    updates = []
    params = []
    for key, value in fields.items():
        updates.append(f"{key} = ?")
        params.append(value)
    
    if not updates:
        return 0

    params.append(id)
    params.append(user_id)

    try:
        cur = con.cursor()
        cur.execute(
            f"UPDATE transactions SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            params
        )
        return cur.rowcount
    except Exception as e:
        con.rollback()
        raise e





