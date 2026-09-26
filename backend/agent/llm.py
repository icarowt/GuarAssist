"""
Cliente único do Gemini, compartilhado pelo agente e pelo verificador.

gerar() tenta de novo quando o Gemini está sobrecarregado (503/429/500)
e, se mesmo assim falhar, tenta os modelos de reserva de GEMINI_MODELOS_RESERVA.
"""
import time

from agent import config

_cliente = None

ERROS_TEMPORARIOS = ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "overloaded", "high demand")
ESPERAS = [1]  # segundos entre tentativas


def cliente():
    global _cliente
    if _cliente is None:
        from google import genai
        _cliente = genai.Client(api_key=config.GEMINI_API_KEY)
    return _cliente


def disponivel():
    return bool(config.GEMINI_API_KEY)


def _temporario(erro):
    texto = str(erro)
    return any(t in texto for t in ERROS_TEMPORARIOS)


def gerar(contents, cfg, modelo=None):
    """generate_content com novas tentativas e modelos de reserva."""
    modelos = [modelo or config.GEMINI_MODEL] + [m for m in config.GEMINI_MODELOS_RESERVA if m]
    ultimo_erro = None
    for m in modelos:
        for i in range(len(ESPERAS) + 1):
            try:
                return cliente().models.generate_content(model=m, contents=contents, config=cfg)
            except Exception as e:
                ultimo_erro = e
                if not _temporario(e):
                    break  # erro que não resolve tentando de novo (ex.: 404): pula pro próximo modelo
                if i < len(ESPERAS):
                    print(f"[gemini] {m} ocupado, tentando de novo em {ESPERAS[i]}s...")
                    time.sleep(ESPERAS[i])
        print(f"[gemini] {m} não respondeu: {str(ultimo_erro)[:120]}")
    raise ultimo_erro


def texto(resp):
    """Junta só as partes de texto (evita o aviso de 'thought_signature')."""
    try:
        partes = resp.candidates[0].content.parts or []
        t = "".join(p.text for p in partes if getattr(p, "text", None) and not getattr(p, "thought", False))
        return t.strip()
    except Exception:
        return (getattr(resp, "text", None) or "").strip()
