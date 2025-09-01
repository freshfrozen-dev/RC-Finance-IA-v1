# scripts/tools/smoke.py
import subprocess, shutil, sys
from sqlite_utils import Database
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(os.path.dirname(ROOT), "data", "finance.db")

def check_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=10)
        return True, out.strip().splitlines()[0][:120]
    except Exception as e:
        return False, str(e)

def main():
    ok = True

    # DB e tabelas
    try:
        db = Database(DB_PATH)
        tables = db.table_names()
        need = {"transactions", "goals"}
        falta = [t for t in need if t not in tables]
        print(f"[DB] OK - tabelas: {tables}" if not falta else f"[DB] FALTAM: {falta}")
        ok = ok and (len(falta) == 0)
    except Exception as e:
        print(f"[DB] ERRO: {e}"); ok = False

    # ffmpeg
    s, msg = check_cmd("ffmpeg -version")
    print(f"[ffmpeg] {'OK' if s else 'ERRO'} - {msg}"); ok = ok and s

    # tesseract
    s, msg = check_cmd("tesseract -v")
    print(f"[tesseract] {'OK' if s else 'ERRO'} - {msg}"); ok = ok and s

    # whisper import
    try:
        import whisper  # noqa
        print("[whisper] OK - importou")
    except Exception as e:
        print(f"[whisper] ERRO: {e}"); ok = False

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
