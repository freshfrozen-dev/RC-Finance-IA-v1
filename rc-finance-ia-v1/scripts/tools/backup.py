# scripts/tools/backup.py
import os, json, time, shutil, sys
from datetime import datetime
from sqlite_utils import Database
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../scripts
ROOT = os.path.dirname(BASE)                                        # projeto
DB_PATH = os.path.join(ROOT, "data", "finance.db")
BACKUPS = os.path.join(ROOT, "data", "backups")

def ensure_dirs():
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    os.makedirs(BACKUPS, exist_ok=True)

def backup_now():
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(BACKUPS, f"backup-{ts}")
    os.makedirs(out_dir, exist_ok=True)

    db = Database(DB_PATH)
    tables = [t for t in db.table_names() if t in ("transactions", "goals")]

    meta = {"db_path": DB_PATH, "tables": tables, "timestamp": ts}
    for t in tables:
        rows = list(db[t].rows)
        # JSON
        with open(os.path.join(out_dir, f"{t}.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        # CSV
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(out_dir, f"{t}.csv"), index=False, encoding="utf-8-sig")

    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Zip
    zip_path = shutil.make_archive(out_dir, "zip", out_dir)
    print(f"[OK] Backup em: {zip_path}")

if __name__ == "__main__":
    try:
        backup_now()
        sys.exit(0)
    except Exception as e:
        print(f"[ERRO] {e}")
        sys.exit(1)
