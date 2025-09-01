import asyncio
import tempfile
import os
from pathlib import Path

try:
    import edge_tts
    _HAVE_EDGE_TTS = True
except ImportError:
    _HAVE_EDGE_TTS = False

async def _speak_async(text: str, voice: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def speak_bytes(texto: str, voice: str = "pt-BR-AntonioNeural") -> bytes:
    """
    Gera áudio MP3 em memória a partir do texto usando edge-tts.
    Retorna os bytes do áudio.
    """
    if not _HAVE_EDGE_TTS:
        raise RuntimeError("A biblioteca 'edge-tts' não está instalada. Instale com: pip install edge-tts")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        tmp_path = tmp_file.name

    try:
        asyncio.run(_speak_async(texto, voice, tmp_path))
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    except Exception as e:
        raise RuntimeError(f"Erro ao gerar áudio com edge-tts: {e}")
    finally:
        if Path(tmp_path).exists():
            os.remove(tmp_path)

def speak_to_file(texto: str, path: str, voice: str = "pt-BR-AntonioNeural") -> str:
    """
    Gera áudio MP3 a partir do texto usando edge-tts e salva em um arquivo.
    Retorna o caminho do arquivo salvo.
    """
    if not _HAVE_EDGE_TTS:
        raise RuntimeError("A biblioteca 'edge-tts' não está instalada. Instale com: pip install edge-tts")

    try:
        asyncio.run(_speak_async(texto, voice, path))
        return path
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar áudio com edge-tts: {e}")


