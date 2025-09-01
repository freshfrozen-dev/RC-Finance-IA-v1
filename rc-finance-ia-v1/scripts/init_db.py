from sqlite_utils import Database

db = Database(DB_PATH)

if "transactions" not in db.table_names():
    db["transactions"].create({
        "id": int,
        "type": str,
        "description": str,
        "amount": float,
        "category": str,
        "date": str,
    }, pk="id")

if "goals" not in db.table_names():
    db["goals"].create({
        "id": int,
        "name": str,
        "target_amount": float,
        "current_amount": float,
        "priority": str,        # Alta, Média, Baixa
        "due_date": str,        # YYYY-MM-DD
        "status": str           # ativa, concluida, pausada
    }, pk="id")

print("Banco inicializado/atualizado.")