import os
import wave
import json
from io import BytesIO

try:
    import vosk
    from vosk import KaldiRecognizer, Model, SetLogLevel
    # Desativa logs verbosos do Vosk
    SetLogLevel(-1)
    _HAVE_VOSK = True
except ImportError:
    _HAVE_VOSK = False

def transcrever_vosk_wav_bytes(wav_bytes: bytes, model_dir: str = "models/vosk-pt") -> str:
    """
    Transcreve áudio em formato WAV (bytes) usando o Vosk (offline).
    Espera áudio de 16 kHz mono.
    """
    if not _HAVE_VOSK:
        raise RuntimeError("A biblioteca 'vosk' não está instalada. Instale com: pip install vosk")
    
    if not os.path.exists(model_dir):
        raise RuntimeError(
            f"Modelo Vosk não encontrado em: {model_dir}. Baixe o modelo PT-BR e extraia para esta pasta."
        )

    try:
        model = Model(model_dir)
        rec = KaldiRecognizer(model, 16000)  # 16000 Hz é a taxa de amostragem esperada

        wf = wave.open(BytesIO(wav_bytes), "rb")
        if (
            wf.getnchannels() != 1
            or wf.getsampwidth() != 2
            or wf.getframerate() != 16000
        ):
            raise RuntimeError("Áudio WAV deve ser mono, 16-bit PCM e 16kHz para Vosk.")

        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            rec.AcceptWaveform(data)

        result = rec.FinalResult()
        text = json.loads(result).get("text", "")
        return text
    except Exception as e:
        raise RuntimeError(f"Erro na transcrição Vosk: {e}")


