"""
Dupla checagem contra falsas validações
=======================================
O YOLO sozinho tem 3 fraquezas conhecidas no GuarAssist:
  1. Quando não acha nada, o detector devolve "saudável 92%" para QUALQUER foto
     (um gato, uma parede, uma folha de outra planta).
  2. Limiar baixo (0.35): aparecem falsos positivos.
  3. Dataset pequeno e feito de capturas de tela; foto real de campo é diferente.

Solução: um segundo "par de olhos" (Gemini visão) responde perguntas objetivas
sobre a foto em JSON, e o CÓDIGO (não o LLM) cruza as duas opiniões e decide
o veredito. Só caso CONFIRMADO dispara surto e alerta para vizinhos.

Vereditos:
    rejeitada     -> não é guaraná ou foto ruim: pede outra, não registra
    inconclusivo  -> YOLO viu praga, verificador não vê sintoma: pede foto de perto, não registra
    confirmado    -> YOLO (confiança boa) + verificador concordam: registra, conta para surto
    provavel      -> concordam que tem problema, mas confiança baixa ou praga diferente: registra, aciona técnico
    suspeita      -> YOLO não achou, verificador vê sintoma: registra, aciona técnico
    saudavel      -> os dois não veem problema
    nao_verificado-> sem Gemini (modo reserva): só YOLO, nunca dispara alerta a vizinhos
"""
import json

from agent import config, conhecimento

LIMIAR_CONFIRMA = config._float("LIMIAR_CONFIRMA", 0.50)

CHAVES = list(conhecimento.PRAGAS.keys())

SCHEMA = {
    "type": "object",
    "properties": {
        "e_planta": {"type": "boolean", "description": "A foto mostra uma planta (folha, fruto, ramo, flor)?"},
        "parece_guarana": {"type": "boolean", "description": "Parece ser guaranazeiro (Paullinia cupana)?"},
        "qualidade_ok": {"type": "boolean", "description": "Foto nítida, perto e com luz suficiente para avaliar sintomas?"},
        "problema_qualidade": {"type": "string", "description": "Se qualidade_ok for falso: escura, tremida, longe, cortada etc."},
        "parte": {"type": "string", "enum": ["folha", "fruto", "ramo", "flor", "planta_inteira", "outro"]},
        "tem_sintoma": {"type": "boolean", "description": "Há mancha, lesão, inseto, deformação ou dano visível?"},
        "descricao_sintoma": {"type": "string"},
        "suspeita": {"type": "string", "enum": CHAVES + ["nenhuma", "outra"]},
        "certeza": {"type": "string", "enum": ["baixa", "media", "alta"]},
    },
    "required": ["e_planta", "parece_guarana", "qualidade_ok", "parte", "tem_sintoma", "suspeita", "certeza"],
}

PROMPT = f"""
Você é um fitopatologista revisando uma foto enviada por um produtor de guaraná no Amazonas.
Responda SOMENTE o que dá para ver na imagem. Não chute.

Pragas/doenças possíveis (use a chave exata em "suspeita"):
{chr(10).join(f"- {k}: {v['sintomas']}" for k, v in conhecimento.PRAGAS.items())}

Regras:
- Se não houver planta na foto, e_planta = false.
- Se for planta mas claramente NÃO for guaraná, parece_guarana = false.
- Na dúvida se é guaraná (foto muito de perto de uma folha), considere parece_guarana = true.
- tem_sintoma = true só se houver dano visível de verdade. Folha velha com pequenas marcas naturais não conta.
""".strip()


def verificar(foto: bytes, cliente=None, modelo: str = None):
    """Retorna o dicionário do SCHEMA ou None se não conseguir verificar."""
    from google.genai import types
    from agent import llm

    try:
        resp = llm.gerar(
            modelo=modelo,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(data=foto, mime_type="image/jpeg"),
                types.Part.from_text(text=PROMPT),
            ])],
            cfg=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=SCHEMA,
            ),
        )
        return json.loads(llm.texto(resp))
    except Exception as e:
        print(f"[verificador] não verificou: {e}")
        return None


def decidir(yolo: dict, ver: dict):
    """
    Cruza YOLO + verificador e devolve (veredito, praga_final, motivo).
    yolo: {"status": "praga"|"saudavel", "disease": chave, "confidence": float}
    ver:  resposta do verificador ou None
    """
    y_praga = yolo.get("status") == "praga"
    y_chave = yolo.get("disease")
    y_conf = float(yolo.get("confidence") or 0) if y_praga else 0.0

    # ── Sem verificador: só YOLO, com cautela ──
    if ver is None:
        if y_praga and y_conf >= LIMIAR_CONFIRMA:
            return "nao_verificado", y_chave, "Só o modelo YOLO analisou (verificador indisponível)."
        if y_praga:
            return "nao_verificado", y_chave, "Confiança baixa e sem segunda checagem."
        return "saudavel", None, "YOLO não encontrou pragas conhecidas (sem segunda checagem)."

    # ── Foto inválida ──
    if not ver.get("e_planta"):
        return "rejeitada", None, "A foto não mostra uma planta."
    if not ver.get("parece_guarana"):
        return "rejeitada", None, "A planta da foto não parece ser guaraná."
    if not ver.get("qualidade_ok"):
        return "rejeitada", None, f"Foto sem qualidade para avaliar ({ver.get('problema_qualidade') or 'escura, tremida ou longe'})."

    v_sintoma = bool(ver.get("tem_sintoma"))
    v_chave = ver.get("suspeita") if ver.get("suspeita") in conhecimento.PRAGAS else None

    # ── YOLO viu praga ──
    if y_praga:
        if not v_sintoma:
            return "inconclusivo", None, "O modelo apontou praga, mas a segunda checagem não viu sintoma. Precisa de foto mais de perto."
        if y_conf >= LIMIAR_CONFIRMA and (v_chave in (None, y_chave)):
            return "confirmado", y_chave, "Modelo YOLO e segunda checagem concordam."
        if v_chave and v_chave != y_chave:
            return "provavel", y_chave, f"Os dois veem problema, mas divergem no tipo (YOLO: {y_chave}, verificador: {v_chave})."
        return "provavel", y_chave, "Os dois veem problema, mas a confiança do modelo está baixa."

    # ── YOLO não viu praga ──
    if v_sintoma:
        return "suspeita", v_chave, "O modelo não reconheceu, mas a segunda checagem viu sintoma. Técnico deve avaliar."
    return "saudavel", None, "Modelo YOLO e segunda checagem não viram problema."
