"""
Configurações do agente, lidas do arquivo backend/.env
"""
import os
import warnings
from pathlib import Path

# Avisos do Python 3.9 / LibreSSL do Mac: não quebram nada, só poluem o terminal
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")
warnings.filterwarnings("ignore", message=".*non-text parts.*")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


def _float(nome, padrao):
    try:
        return float(os.getenv(nome, padrao))
    except ValueError:
        return float(padrao)


# ── Chaves ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Se der erro de modelo não encontrado, troque por outro da lista do AI Studio
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

# Modelos de reserva se o principal estiver fora do ar (separados por vírgula)
GEMINI_MODELOS_RESERVA = [m.strip() for m in os.getenv("GEMINI_MODELOS_RESERVA", "").split(",") if m.strip()]

# ── Comportamento do agente ───────────────────────────────────────────────────
# Retorno proativo ("voltei pra saber da planta"). Na demo use 60 segundos.
FOLLOWUP_SEGUNDOS = int(_float("FOLLOWUP_SEGUNDOS", 60))

# Detecção de surto: N casos da mesma praga num raio de X km nos últimos D dias
RAIO_SURTO_KM = _float("RAIO_SURTO_KM", 10)
MIN_CASOS_SURTO = int(_float("MIN_CASOS_SURTO", 3))
JANELA_SURTO_DIAS = int(_float("JANELA_SURTO_DIAS", 7))

# Localização padrão (Maués/AM) para quem ainda não compartilhou a localização
LAT_PADRAO = _float("LAT_PADRAO", -3.3836)
LON_PADRAO = _float("LON_PADRAO", -57.7186)

# Responder também em áudio: "sempre", "auto" (só quando o produtor manda áudio) ou "nunca"
RESPOSTA_EM_AUDIO = os.getenv("RESPOSTA_EM_AUDIO", "auto").strip().lower()

# ── Parâmetros da estimativa de economia (valores de referência, ajustáveis) ──
PLANTAS_POR_HECTARE = _float("PLANTAS_POR_HECTARE", 400)      # espaçamento 5 x 5 m
AREA_PADRAO_HA = _float("AREA_PADRAO_HA", 3)                   # pequeno produtor típico
LITROS_CALDA_POR_PLANTA = _float("LITROS_CALDA_POR_PLANTA", 1.5)
CUSTO_POR_PLANTA_REAIS = _float("CUSTO_POR_PLANTA_REAIS", 0.90)  # produto + mão de obra
MARGEM_SEGURANCA = _float("MARGEM_SEGURANCA", 3)               # trata também as vizinhas
