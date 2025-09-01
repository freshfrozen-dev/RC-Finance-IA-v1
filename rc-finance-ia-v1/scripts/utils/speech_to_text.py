# PATH BOOTSTRAP
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
import subprocess

try:
    from loguru import logger  # ok se existir
except Exception:  # fallback p/ ambientes sem loguru
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("rc-finance-ia")

# Preferência: faster-whisper (CPU) com compute_type="int8" e modelo "small"
try:
    from faster_whisper import WhisperModel
    _model = None
    def _load_model():
        global _model
        if _model is None:
            _model = WhisperModel("small", device="cpu", compute_type="int8")
        return _model
except ImportError:
    logger.warning("faster-whisper não instalado. A transcrição offline não estará disponível.")
    _model = None

def transcrever_audio(file_bytes: bytes, lang: str = "pt") -> str:
    """
    Transcreve áudio usando faster-whisper (preferencialmente) ou retorna erro claro.
    Aceita bytes de áudio e tenta detectar/converter para WAV/PCM se necessário.
    """
    if _model is None:
        return "Transcrição offline indisponível. faster-whisper não está configurado ou FFmpeg não encontrado."

    # Salvar bytes para um arquivo temporário para processamento
    temp_audio_path = "temp_audio.wav"
    with open(temp_audio_path, "wb") as f:
        f.write(file_bytes)

    try:
        # Verificar se o FFmpeg está disponível para conversão, se necessário
        if os.getenv("RCF_DEBUG_STT") == "1":
            logger.info(f"Iniciando transcrição para {temp_audio_path}")

        # Transcrever
        model = _load_model()
        segments, info = model.transcribe(temp_audio_path, language=lang)
        
        transcribed_text = "".join([segment.text for segment in segments])
        
        if os.getenv("RCF_DEBUG_STT") == "1":
            logger.info(f"Transcrição concluída. Idioma detectado: {info.language}, Probabilidade: {info.language_probability:.2f}")
            logger.info(f"Texto: {transcribed_text[:100]}...") # Log dos primeiros 100 caracteres

        return transcribed_text
    except Exception as e:
        logger.error(f"Erro durante a transcrição: {e}")
        return f"Erro na transcrição: {e}"
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


if __name__ == "__main__":
    # Exemplo de uso (requer um arquivo de áudio de teste)
    # Crie um arquivo de áudio 'test_audio.wav' no mesmo diretório para testar
    test_file = "test_audio.wav"
    if os.path.exists(test_file):
        with open(test_file, "rb") as f:
            audio_data = f.read()
        print(f"Transcrevendo {test_file}...")
        text = transcrever_audio(audio_data)
        print(f"Texto Transcrito: {text}")
    else:
        print(f"Crie um arquivo '{test_file}' para testar a transcrição.")


