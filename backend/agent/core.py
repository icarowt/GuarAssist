"""
Núcleo do agente GuarAssist (independente de canal).

Uso:
    from agent.core import processar
    resp = processar(chat_id="123", foto=bytes_da_imagem, texto="olha essa folha")
    resp.texto          -> mensagem para o produtor
    resp.imagem_anotada -> bytes JPG com as caixas do YOLO (ou None)
    resp.audio          -> bytes MP3 da resposta falada (ou None)
    resp.acoes          -> ações para o adaptador executar (alertas, retornos)

Fluxo com LLM (Gemini):
    mensagem -> Gemini decide ferramentas -> executa -> Gemini decide de novo -> resposta final
Se não houver chave ou o Gemini falhar, cai no modo "só YOLO" (respostas prontas).
"""
import base64
from dataclasses import dataclass, field

from agent import config, llm, prompt, tools, voz, store

MAX_HISTORICO = 12
MAX_PASSOS = 8

_historico = {}  # chat_id -> [(role, texto)]


@dataclass
class Resposta:
    texto: str
    imagem_anotada: bytes = None
    audio: bytes = None
    acoes: list = field(default_factory=list)
    ferramentas: list = field(default_factory=list)
    modo: str = "llm"


# ══════════════════════════════════════════════════════════════════════════════
# Entrada principal
# ══════════════════════════════════════════════════════════════════════════════

def processar(chat_id, texto=None, foto=None, audio=None, audio_mime="audio/ogg",
              nome=None, canal="telegram") -> Resposta:
    chat_id = str(chat_id)
    usuario = store.garantir_usuario(chat_id, nome=nome, canal=canal)
    ctx = tools.Contexto(chat_id=chat_id, canal=canal, usuario=usuario, foto=foto)

    resposta = None
    if config.GEMINI_API_KEY:
        try:
            resposta = _processar_com_llm(ctx, texto, foto, audio, audio_mime)
        except Exception as e:
            print(f"[agente] Gemini falhou, usando modo só YOLO: {e}")

    if resposta is None:
        resposta = _processar_sem_llm(ctx, texto, foto, audio)

    # Rede de segurança: resultado válido sempre vai para o mapa, mesmo se o LLM esquecer.
    # Quem decide se é válido é o verificador (código), não o LLM.
    if (ctx.diagnostico and ctx.diagnostico["veredito"] in tools.VEREDITOS_REGISTRAVEIS
            and "registrar_ocorrencia" not in ctx.ferramentas_usadas):
        tools.executar("registrar_ocorrencia", {"plantas_afetadas": 1}, ctx)

    resposta.acoes = ctx.acoes
    resposta.ferramentas = ctx.ferramentas_usadas
    if ctx.imagem_anotada_b64:
        try:
            resposta.imagem_anotada = base64.b64decode(ctx.imagem_anotada_b64)
        except Exception:
            pass

    falar = config.RESPOSTA_EM_AUDIO == "sempre" or (config.RESPOSTA_EM_AUDIO == "auto" and audio)
    if falar:
        resposta.audio = voz.gerar_audio(resposta.texto)

    _guardar_historico(chat_id, texto, foto, audio, resposta.texto)
    print(f"[agente] {chat_id} | modo={resposta.modo} | ferramentas={ctx.ferramentas_usadas} | acoes={len(ctx.acoes)}")
    return resposta


def limpar_historico(chat_id):
    _historico.pop(str(chat_id), None)


# ══════════════════════════════════════════════════════════════════════════════
# Modo agente (Gemini + ferramentas)
# ══════════════════════════════════════════════════════════════════════════════

def _processar_com_llm(ctx, texto, foto, audio, audio_mime):
    from google.genai import types


    # Histórico curto em texto (fotos antigas não são reenviadas, economiza tempo)
    contents = []
    for role, t in _historico.get(ctx.chat_id, []):
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=t)]))

    partes = []
    if foto:
        partes.append(types.Part.from_bytes(data=foto, mime_type="image/jpeg"))
    if audio:
        partes.append(types.Part.from_bytes(data=audio, mime_type=audio_mime))

    u = ctx.usuario or {}
    contexto_usuario = (
        f"[Contexto do sistema: produtor '{u.get('nome') or 'sem nome'}', "
        f"área {u.get('area_ha') or 'não informada'} ha, "
        f"localização {'compartilhada' if u.get('lat') is not None else 'não compartilhada'}. "
        f"Tipo de mensagem: {'foto' if foto else ''}{' + ' if foto and audio else ''}{'áudio' if audio else ''}"
        f"{'texto' if not foto and not audio else ''}.]"
    )
    corpo = texto or ("(o produtor mandou só a foto)" if foto else "(o produtor mandou um áudio)" if audio else "")
    partes.append(types.Part.from_text(text=f"{contexto_usuario}\n{corpo}"))
    contents.append(types.Content(role="user", parts=partes))

    ferramentas = [types.Tool(function_declarations=tools.DECLARACOES)]

    def _config(forcar_diagnostico):
        cfg = dict(
            system_instruction=prompt.SISTEMA,
            tools=ferramentas,
            temperature=0.4,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        if forcar_diagnostico:
            # Com foto, o primeiro passo é SEMPRE rodar o modelo treinado
            cfg["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=["diagnosticar_foto"]
                )
            )
        return types.GenerateContentConfig(**cfg)

    resp = None
    for passo in range(MAX_PASSOS):
        resp = llm.gerar(contents, _config(forcar_diagnostico=bool(foto) and passo == 0))
        chamadas = resp.function_calls or []
        if not chamadas:
            break

        contents.append(resp.candidates[0].content)
        respostas = []
        for fc in chamadas:
            args = dict(fc.args) if fc.args else {}
            resultado = tools.executar(fc.name, args, ctx)
            print(f"[agente]   -> {fc.name}({args})")
            respostas.append(types.Part.from_function_response(name=fc.name, response={"result": resultado}))
        contents.append(types.Content(role="user", parts=respostas))

    texto_final = llm.texto(resp) if resp is not None else ""
    if not texto_final:
        return None  # cai no modo sem LLM
    return Resposta(texto=texto_final, modo="llm")


# ══════════════════════════════════════════════════════════════════════════════
# Modo reserva (sem LLM): só o YOLO + respostas prontas
# ══════════════════════════════════════════════════════════════════════════════

def _processar_sem_llm(ctx, texto, foto, audio):
    nome = (ctx.usuario or {}).get("nome")
    saud = f", {nome}" if nome else ""

    if not foto:
        if audio:
            return Resposta(
                texto=f"Recebi seu áudio{saud}! 🎤 Pra eu te ajudar certinho, me manda uma *foto* bem de perto da folha ou fruto. 📸",
                modo="reserva",
            )
        return Resposta(
            texto=f"Oi{saud}! 🌱 Me manda uma *foto* da folha, fruto ou ramo do guaraná que eu vejo se tem praga ou doença. 📸",
            modo="reserva",
        )

    d = tools.executar("diagnosticar_foto", {}, ctx)
    if d.get("erro"):
        return Resposta(texto="Não consegui analisar essa foto. 😕 Tenta outra bem de perto, com luz do dia. 📸", modo="reserva")

    v = d["veredito"]
    if v == "saudavel":
        tools.executar("registrar_ocorrencia", {}, ctx)
        return Resposta(
            texto=(
                f"✅ Não encontrei sinais das pragas que eu conheço nessa foto{saud}.\n\n"
                f"Continue vistoriando as plantas toda semana, principalmente os brotos novos. "
                f"Se aparecer mancha ou inseto, me manda uma foto bem de perto."
            ),
            modo="reserva",
        )
    if v in ("rejeitada", "inconclusivo"):
        return Resposta(
            texto=f"🤔 Fiquei em dúvida com essa foto. {d['motivo']}\n\nMe manda outra *bem de perto*, com luz do dia, mostrando a parte com problema. 📸",
            modo="reserva",
        )

    reg = tools.executar("registrar_ocorrencia", {"plantas_afetadas": 1}, ctx)
    tools.executar("agendar_retorno", {}, ctx)
    eco = reg.get("economia", {})
    certeza = f" ({int(d['confianca'] * 100)}% de certeza do modelo)" if d.get("confianca") is not None else ""

    if v == "confirmado":
        abertura = f"⚠️ Encontrei *{d['praga_nome']}* nessa foto{certeza}, gravidade {d['severidade']}."
    elif v == "suspeita":
        abertura = "⚠️ Vi sinal de problema nessa planta, mas não consegui identificar com segurança."
    else:  # provavel / nao_verificado
        abertura = f"⚠️ Parece ser *{d['praga_nome']}*{certeza}, mas precisa de confirmação do técnico."

    linhas = [abertura]
    if d.get("sintomas"):
        linhas += ["", f"*O que é:* {d['sintomas']}"]
    if d.get("manejo_recomendado"):
        linhas += ["", f"*O que fazer agora:* {d['manejo_recomendado']}"]
    if eco.get("economia_reais"):
        linhas += ["", f"💰 Tratando só as plantas afetadas e as vizinhas, você economiza cerca de "
                       f"*R$ {eco['economia_reais']:.0f}* e *{eco['economia_litros_calda']:.0f} L* de calda."]
    if reg.get("surto"):
        linhas += ["", f"🔴 Já são *{reg['casos_confirmados_na_regiao']} casos confirmados* perto de você. "
                       f"Avisei {reg.get('vizinhos_alertados', 0)} produtor(es) vizinho(s)."]
    if reg.get("tecnico_acionado"):
        linhas += ["🧑‍🌾 O técnico foi avisado do seu caso."]
    linhas += ["", "Daqui uns dias eu volto pra saber como ficou. 🌱",
               "_Isso é uma triagem. Produto químico só com orientação do técnico._"]
    return Resposta(texto="\n".join(linhas), modo="reserva")


# ══════════════════════════════════════════════════════════════════════════════

def _guardar_historico(chat_id, texto, foto, audio, resposta):
    h = _historico.setdefault(chat_id, [])
    marcador = " ".join(x for x in ["[mandou foto]" if foto else "", "[mandou áudio]" if audio else ""] if x)
    h.append(("user", f"{marcador} {texto or ''}".strip() or "(mensagem)"))
    h.append(("model", resposta))
    del h[:-MAX_HISTORICO]
