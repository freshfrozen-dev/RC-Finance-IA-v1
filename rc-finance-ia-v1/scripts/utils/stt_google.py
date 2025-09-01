# scripts/utils/stt_google.py
import speech_recognition as sr
from io import BytesIO

def transcrever_google_wav_bytes(wav_bytes: bytes, language: str = "pt-BR") -> str:
    """
    Transcreve áudio em formato WAV (bytes) usando o Google Speech Recognition.
    Lança RuntimeError em caso de falha.
    """
    r = sr.Recognizer()
    try:
        with sr.AudioFile(BytesIO(wav_bytes)) as source:
            audio_data = r.record(source)
        text = r.recognize_google(audio_data, language=language)
        if not text:
            raise RuntimeError("Transcrição vazia ou áudio não reconhecido.")
        return text
    except sr.UnknownValueError:
        raise RuntimeError("Não foi possível entender o áudio (Google STT).")
    except sr.RequestError as e:
        raise RuntimeError(f"Erro na requisição ao Google STT; verifique sua conexão: {e}")
    except Exception as e:
        raise RuntimeError(f"Erro inesperado na transcrição Google STT: {e}")
