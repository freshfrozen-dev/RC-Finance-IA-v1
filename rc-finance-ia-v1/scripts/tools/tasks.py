# scripts/tools/tasks.py
import argparse, subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_app():
    return subprocess.call("streamlit run scripts/ui.py", shell=True)

def backup():
    return subprocess.call(f"{sys.executable} scripts/tools/backup.py", shell=True)

def smoke():
    return subprocess.call(f"{sys.executable} scripts/tools/smoke.py", shell=True)

def reset_db():
    db = os.path.join(ROOT, "..", "data", "finance.db")
    try:
        os.remove(db)
        print("[OK] finance.db apagado.")
        return 0
    except FileNotFoundError:
        print("[OK] Já não existe.")
        return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "backup", "smoke", "reset-db"])
    args = ap.parse_args()
    rc = {"run": run_app, "backup": backup, "smoke": smoke, "reset-db": reset_db}[args.cmd]()
    sys.exit(rc)
