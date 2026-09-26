"""
Resposta em áudio (texto -> fala em português)
==============================================
Três motores em cascata, do mais humano pro mais simples:

  1. gemini  -> voz neural do Gemini TTS, com entonação e "jeito" controlável (mais humana)
  2. mac     -> voz do macOS (Luciana/Felipe). Offline, rápida, boa se baixar a versão Premium
  3. gtts    -> Google Tradutor (voz de robô, só como última reserva)

Configuração no .env:
  VOZ_MOTOR=gemini            # gemini | mac | gtts (os seguintes viram reserva automática)
  VOZ_MODELO=gemini-3.8-flash-tts
  VOZ_NOME=Puck               # voz do Gemini (ex.: Puck, Charon, Kore, Aoede, Fenrir, Leda, Orus, Zephyr)
  VOZ_ESTILO=...              # como falar (sotaque, ritmo, humor)
  VOZ_MAC=Luciana             # voz do Mac (rode: say -v '?' | grep pt_BR)

Saída sempre em M4A ou MP3 (formatos que o Telegram aceita como mensagem de voz).
"""
import io
import os
import re
import shutil
import subprocess
import tempfile
import wave

from agent import config

VOZ_MOTOR = os.getenv("VOZ_MOTOR", "gemini").strip().lower()
VOZ_MODELO = os.getenv("VOZ_MODELO", "gemini-3.8-flash-tts").strip()
VOZ_NOME = os.getenv("VOZ_NOME", "Puck").strip()
VOZ_ESTILO = os.getenv(
    "VOZ_ESTILO",
    "Fale em português do Brasil como um técnico agrícola do interior do Amazonas, "
    "amigo do produtor: tom calmo, acolhedor e confiante, ritmo tranquilo, sem pressa, "
    "como numa conversa no quintal. Leia exatamente o texto a seguir",
).strip()
VOZ_MAC = os.getenv("VOZ_MAC", "Luciana").strip()

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF‍️]+",
    flags=re.UNICODE,
)


def limpar_para_fala(texto: str) -> str:
    t = _EMOJI.sub("", texto or "")
    t = re.sub(r"https?://\S+", "", t)
    t = t.replace("*", "").replace("_", " ").replace("`", "").replace("#", "")
    t = re.sub(r"R\$\s?(\d+(?:[.,]\d+)*)", r"\1 reais", t)  # "R$ 340" vira "340 reais"
    t = re.sub(r"(\d)\s?L\b", r"\1 litros", t)
    t = re.sub(r"^\s*\d+[.)]\s*", "", t, flags=re.MULTILINE)  # tira "1." de listas
    t = re.sub(r"\n+", ". ", t)
    t = re.sub(r"\.\s*\.", ".", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


# ── Conversão de formato (Mac tem o afconvert de fábrica; ffmpeg se existir) ──

def _para_m4a(caminho_entrada):
    saida = caminho_entrada.rsplit(".", 1)[0] + ".m4a"
    if shutil.which("afconvert"):
        cmd = ["afconvert", "-f", "m4af", "-d", "aac", caminho_entrada, saida]
    elif shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", caminho_entrada, "-c:a", "aac", saida]
    else:
        return None
    subprocess.run(cmd, check=True, timeout=30)
    with open(saida, "rb") as f:
        return f.read()


# ── Motor 1: Gemini TTS ──

def _gemini(fala):
    if not config.GEMINI_API_KEY:
        return None
    from google.genai import types
    from agent import llm

    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOZ_NOME)
            )
        ),
    )
    ultimo = None
    for _ in range(2):  # uma nova tentativa se estiver ocupado
        try:
            resp = llm.cliente().models.generate_content(
                model=VOZ_MODELO, contents=f"{VOZ_ESTILO}:\n\n{fala}", config=cfg
            )
            pcm = resp.candidates[0].content.parts[0].inline_data.data
            break
        except Exception as e:
            ultimo = e
    else:
        raise ultimo

    # Gemini devolve PCM cru (24 kHz, 16 bits, mono): embrulha em WAV e converte
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "fala.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        return _para_m4a(wav)


# ── Motor 2: voz do macOS ──

def _mac(fala):
    if not shutil.which("say"):
        return None
    with tempfile.TemporaryDirectory() as d:
        aiff = os.path.join(d, "fala.aiff")
        subprocess.run(["say", "-v", VOZ_MAC, "-r", "175", "-o", aiff, fala], check=True, timeout=60)
        return _para_m4a(aiff)


# ── Motor 3: gTTS ──

def _gtts(fala):
    from gtts import gTTS
    buf = io.BytesIO()
    gTTS(fala, lang="pt", tld="com.br").write_to_fp(buf)
    return buf.getvalue()


MOTORES = {"gemini": _gemini, "mac": _mac, "gtts": _gtts}


def gerar_audio(texto: str):
    """Retorna bytes (M4A ou MP3) ou None. Tenta o motor escolhido e depois os outros."""
    fala = limpar_para_fala(texto)
    if not fala:
        return None
    ordem = [VOZ_MOTOR] + [m for m in ("gemini", "mac", "gtts") if m != VOZ_MOTOR]
    for nome in ordem:
        func = MOTORES.get(nome)
        if not func:
            continue
        try:
            audio = func(fala)
            if audio:
                print(f"[voz] gerada com: {nome}")
                return audio
        except Exception as e:
            print(f"[voz] {nome} falhou: {str(e)[:100]}")
    return None