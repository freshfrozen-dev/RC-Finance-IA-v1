# scripts/utils/ocr_reader.py — OCR utilitário "puro" (sem Streamlit)
import os
import subprocess

import cv2
import pytesseract
from PIL import Image

# === Caminhos (ajuste se necessário) ===
TESS_EXE = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
TESSDATA_DIR = os.environ.get("RC_TESSDATA", r"C:\\RC-Finance-IA\\tessdata")
LANG_SPEC = "por+eng"

# Garante que o Tesseract encontre os idiomas
pytesseract.pytesseract.tesseract_cmd = TESS_EXE
if TESSDATA_DIR.lower().endswith("tessdata"):
    os.environ["TESSDATA_PREFIX"] = os.path.dirname(TESSDATA_DIR)
else:
    os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR


def ocr_diag() -> dict:
    """Retorna infos para diagnóstico (mostradas pela UI quando habilitada)."""
    por_ok = os.path.exists(os.path.join(TESSDATA_DIR, "por.traineddata"))
    eng_ok = os.path.exists(os.path.join(TESSDATA_DIR, "eng.traineddata"))
    return {
        "tesseract_cmd": pytesseract.pytesseract.tesseract_cmd or "",
        "tessdata_dir": TESSDATA_DIR,
        "lang_spec": LANG_SPEC,
        "por_exists": por_ok,
        "eng_exists": eng_ok,
        "TESSDATA_PREFIX": os.environ.get("TESSDATA_PREFIX", ""),
    }


def _preprocess(path: str) -> str:
    """Upscale + binariza para melhorar OCR em recibos/fotos."""
    img = cv2.imread(path)
    if img is None:
        return path
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    up = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    th = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    tmp = path + ".prep.png"
    cv2.imwrite(tmp, th)
    return tmp


def _cli(image_path: str, langs: str) -> str:
    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = os.environ.get("TESSDATA_PREFIX", TESSDATA_DIR)
    cmd = [
        TESS_EXE,
        image_path,
        "stdout",
        "-l",
        langs,
        "--oem",
        "1",
        "--psm",
        "6",
        "--tessdata-dir",
        TESSDATA_DIR,
    ]
    run = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    if run.returncode == 0 and run.stdout.strip():
        return run.stdout
    raise RuntimeError(run.stderr.strip() or "CLI Tesseract falhou")


def extract_text_any(image_path: str) -> str:
    """Tenta pytesseract; se falhar, usa CLI; faz fallback de línguas."""
    prep = _preprocess(image_path)

    # 1) pytesseract
    for langs in (LANG_SPEC, "por", "eng"):
        try:
            cfg = f'--tessdata-dir "{TESSDATA_DIR}" --oem 1 --psm 6'
            txt = pytesseract.image_to_string(Image.open(prep), lang=langs, config=cfg)
            if txt and txt.strip():
                return txt
        except Exception:
            pass

    # 2) CLI fallback
    for langs in (LANG_SPEC, "por", "eng"):
        try:
            return _cli(prep, langs)
        except Exception:
            continue

    return (
        "Erro OCR: verifique se por.traineddata/eng.traineddata existem em "
        + TESSDATA_DIR
    )
