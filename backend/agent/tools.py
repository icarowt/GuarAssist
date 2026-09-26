"""
Ferramentas que o agente pode usar.

Cada ferramenta recebe o Contexto da conversa e devolve um dicionário simples
(é isso que volta para o LLM). Ações no mundo real (mandar mensagem para vizinho,
agendar retorno) NÃO são executadas aqui: elas entram em ctx.acoes e o adaptador
do canal (Telegram, WhatsApp) executa. Assim o núcleo serve para qualquer canal.
"""
import time
from dataclasses import dataclass, field

import httpx

from agent import config, conhecimento, store

# Controle simples para não mandar o mesmo alerta de surto repetidas vezes
_ultimo_alerta = {}
INTERVALO_ALERTA_SEG = int(config._float("ALERTA_INTERVALO_MIN", 5) * 60)


@dataclass
class Contexto:
    chat_id: str
    canal: str = "telegram"
    usuario: dict = None
    foto: bytes = None
    diagnostico: dict = None
    imagem_anotada_b64: str = None
    acoes: list = field(default_factory=list)
    ferramentas_usadas: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Diagnóstico: YOLO treinado + segunda checagem (anti falsa validação)
# ══════════════════════════════════════════════════════════════════════════════

INSTRUCOES = {
    "rejeitada": "NÃO registre. Explique o motivo com gentileza. Se for outra cultura, diga que o diagnóstico por foto hoje é só de guaraná e ofereça ajudar por texto. Se for foto ruim, peça outra: bem de perto, com luz do dia, mostrando a parte com problema.",
    "inconclusivo": "NÃO registre e NÃO assuste o produtor. Diga que ficou em dúvida e peça uma foto mais de perto da parte com mancha ou inseto.",
    "confirmado": "Registre, consulte o clima e agende retorno. Pode afirmar o diagnóstico (sempre como triagem).",
    "provavel": "Registre. Diga 'provavelmente é' a praga e que o técnico vai confirmar. Não afirme com certeza.",
    "suspeita": "Registre. Diga que viu sinal de problema mas não conseguiu identificar com segurança, que o técnico foi avisado, e peça foto mais de perto.",
    "saudavel": "Registre. Diga que não encontrou sinais das pragas que conhece. Não prometa que a planta está 100%.",
    "nao_verificado": "Registre. Fale em 'possível' praga, reforce que é triagem e que o técnico confirma.",
}

VEREDITOS_REGISTRAVEIS = {"confirmado", "provavel", "suspeita", "saudavel", "nao_verificado"}
VEREDITOS_COM_PROBLEMA = {"confirmado", "provavel", "suspeita", "nao_verificado"}


def _severidade(confianca):
    if confianca is None:
        return "a avaliar"
    if confianca >= 0.85:
        return "severa"
    if confianca >= 0.65:
        return "moderada"
    return "leve"


def diagnosticar_foto(ctx: Contexto):
    if not ctx.foto:
        return {"erro": "Nenhuma foto recebida nesta mensagem. Peça para o produtor mandar uma foto da folha, fruto ou ramo."}

    from concurrent.futures import ThreadPoolExecutor
    from models.detector import detectar  # import tardio: YOLO é pesado
    from agent import llm, verificador

    from agent import imagem

    # ── 0. Qualidade da foto: rejeita o que não tem conserto, corrige de leve o resto ──
    qualidade = imagem.analisar(ctx.foto)
    if not qualidade["valida"]:
        ctx.diagnostico = {
            "veredito": "rejeitada",
            "motivo": qualidade["dica"],
            "praga": "indefinida", "praga_nome": None, "confianca": None, "severidade": "nenhuma",
        }
        return {**ctx.diagnostico, "instrucao": INSTRUCOES["rejeitada"] + " Use exatamente esta dica: " + qualidade["dica"],
                "qualidade": qualidade["problemas"]}

    foto_modelo = ctx.foto
    if qualidade["precisa_melhorar"]:
        foto_modelo = imagem.melhorar(ctx.foto, qualidade["corrigiveis"])
        print(f"[imagem] foto melhorada: {qualidade['corrigiveis']} {qualidade['metricas']}")

    # YOLO (foto corrigida) e verificador (foto ORIGINAL) rodam em paralelo
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_yolo = ex.submit(detectar, foto_modelo)
        f_ver = ex.submit(verificador.verificar, ctx.foto, llm.cliente(), config.GEMINI_MODEL) if llm.disponivel() else None
        resultado = f_yolo.result()
        ver = f_ver.result() if f_ver else None

    if resultado.get("status") == "erro":
        return {"erro": resultado.get("erro", "Não consegui ler a imagem.")}

    veredito, chave, motivo = verificador.decidir(resultado, ver)
    info = conhecimento.buscar(chave) if chave else None
    y_praga = resultado.get("status") == "praga"
    conf = round(float(resultado.get("confidence", 0)), 2) if y_praga and chave == resultado.get("disease") else None

    if veredito in VEREDITOS_COM_PROBLEMA:
        nome_praga = info["nome"] if info else "Sintoma a identificar"
    elif veredito == "saudavel":
        nome_praga = "Sem praga identificada"
    else:
        nome_praga = None

    # Só mostra as caixas do YOLO quando a detecção dele foi aceita
    mostrar_caixas = y_praga and veredito in {"confirmado", "provavel", "nao_verificado"}
    ctx.imagem_anotada_b64 = resultado.get("annotated_image") if mostrar_caixas else None

    ctx.diagnostico = {
        "veredito": veredito,
        "motivo": motivo,
        "praga": chave or ("saudavel" if veredito == "saudavel" else "indefinida"),
        "praga_nome": nome_praga,
        "confianca": conf,
        "severidade": _severidade(conf) if veredito in VEREDITOS_COM_PROBLEMA else "nenhuma",
    }

    # Mantém o histórico antigo do React, só com resultados válidos
    if veredito in VEREDITOS_REGISTRAVEIS:
        try:
            from database.database import save_analysis
            save_analysis({
                "timestamp": int(time.time()),
                "filename": f"{ctx.canal}_{ctx.chat_id}.jpg",
                "status": "praga" if veredito in VEREDITOS_COM_PROBLEMA else "saudavel",
                "disease": chave,
                "confidence": conf or 0.0,
            })
        except Exception as e:
            print(f"[agente] aviso: não salvou no histórico antigo: {e}")

    retorno = dict(ctx.diagnostico)
    retorno["instrucao"] = INSTRUCOES[veredito]
    if qualidade["precisa_melhorar"]:
        retorno["foto_melhorada"] = qualidade["corrigiveis"]
        retorno["instrucao"] += (" A foto estava ruim (" + ", ".join(qualidade["corrigiveis"]) +
                                 ") e foi corrigida automaticamente; mencione isso em meia frase e dê uma dica rápida de como tirar a próxima.")
    retorno["modelo_yolo"] = {
        "achou_praga": y_praga,
        "praga": resultado.get("disease"),
        "confianca": round(float(resultado.get("confidence", 0)), 2) if y_praga else None,
    }
    if ver:
        retorno["segunda_checagem"] = {
            "tem_sintoma": ver.get("tem_sintoma"),
            "descricao": ver.get("descricao_sintoma"),
            "suspeita": ver.get("suspeita"),
            "parte": ver.get("parte"),
            "certeza": ver.get("certeza"),
        }
    if info:
        retorno.update({
            "tipo": info["tipo"],
            "risco": info["risco"],
            "sintomas": info["sintomas"],
            "manejo_recomendado": info["manejo"],
            "produtos": info["produtos"],
            "espalha_com_chuva": info["espalha_com_chuva"],
            "fonte": info["fonte"],
        })
    return retorno


# ══════════════════════════════════════════════════════════════════════════════
# 2. Economia com aplicação localizada
# ══════════════════════════════════════════════════════════════════════════════

def calcular_economia(ctx: Contexto, plantas_afetadas: int = 1, area_ha: float = None):
    plantas_afetadas = max(1, int(plantas_afetadas or 1))
    area = area_ha or (ctx.usuario or {}).get("area_ha") or config.AREA_PADRAO_HA
    total = int(area * config.PLANTAS_POR_HECTARE)
    tratadas = min(total, int(plantas_afetadas * config.MARGEM_SEGURANCA))
    evitadas = max(0, total - tratadas)
    return {
        "area_ha": area,
        "plantas_na_area": total,
        "plantas_para_tratar": tratadas,
        "plantas_que_nao_precisam_de_produto": evitadas,
        "economia_reais": round(evitadas * config.CUSTO_POR_PLANTA_REAIS, 2),
        "economia_litros_calda": round(evitadas * config.LITROS_CALDA_POR_PLANTA, 1),
        "observacao": "Estimativa comparando tratar só as plantas afetadas e vizinhas contra pulverizar a área toda.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. Registrar ocorrência + detectar surto + acionar vizinhos e técnico
# ══════════════════════════════════════════════════════════════════════════════

def _link_mapa(lat, lon):
    return f"https://maps.google.com/?q={lat:.5f},{lon:.5f}"


def _msg_tecnico(nome, d, plantas_afetadas, lat, lon, surto, casos, precisa_confirmar):
    conf = f"{int(d['confianca'] * 100)}% no modelo" if d.get("confianca") is not None else "sem confiança do modelo"
    cabecalho = "🟡 *Precisa da sua confirmação*" if precisa_confirmar else "🧑‍🌾 *Caso grave confirmado*"
    return (
        f"{cabecalho}\n\n"
        f"Produtor: {nome}\n"
        f"Diagnóstico: *{d['praga_nome']}* ({conf}, {d['severidade']})\n"
        f"Validação: {d['veredito']} ({d['motivo']})\n"
        f"Plantas afetadas: {plantas_afetadas}\n"
        f"{'🔴 SURTO na região: ' + str(casos) + ' casos confirmados' + chr(10) if surto else ''}"
        f"Local: {_link_mapa(lat, lon)}"
    )


def registrar_ocorrencia(ctx: Contexto, plantas_afetadas: int = 1):
    d = ctx.diagnostico
    if not d:
        return {"erro": "Faça o diagnóstico da foto antes de registrar."}
    if d["veredito"] not in VEREDITOS_REGISTRAVEIS:
        return {"registrado": False, "motivo": f"Foto com veredito '{d['veredito']}' não entra no mapa. {d['motivo']}"}
    if "registrar_ocorrencia" in ctx.ferramentas_usadas[:-1]:
        return {"registrado": False, "motivo": "Esta foto já foi registrada."}

    tem_problema = d["veredito"] in VEREDITOS_COM_PROBLEMA
    plantas_afetadas = max(1, int(plantas_afetadas or 1)) if tem_problema else 0
    usuario = ctx.usuario or {}
    lat, lon = store.posicao_do_usuario(usuario)
    eco = calcular_economia(ctx, plantas_afetadas) if d["veredito"] in {"confirmado", "provavel"} else {}
    nome = usuario.get("nome") or "Produtor"

    oc_id = store.registrar_ocorrencia({
        "chat_id": ctx.chat_id,
        "nome_produtor": nome,
        "timestamp": int(time.time()),
        "praga": d["praga"],
        "praga_nome": d["praga_nome"],
        "confianca": d["confianca"],
        "severidade": d["severidade"],
        "plantas_afetadas": plantas_afetadas,
        "lat": lat,
        "lon": lon,
        "economia_reais": eco.get("economia_reais", 0),
        "economia_litros": eco.get("economia_litros_calda", 0),
        "surto": 0,
        "validacao": d["veredito"],
    })

    resposta = {"registrado": True, "id": oc_id, "aparece_no_mapa": True, "validacao": d["veredito"]}
    if not tem_problema:
        return resposta

    info = conhecimento.buscar(d["praga"]) or {}
    tecnicos = [t for t in store.listar_tecnicos() if str(t["chat_id"]) != str(ctx.chat_id)]

    # ── Surto: SÓ casos confirmados contam e SÓ caso confirmado dispara alerta ──
    surto, casos, vizinhos_avisados = False, 0, 0
    if d["veredito"] == "confirmado":
        proximas = store.ocorrencias_proximas(lat, lon, d["praga"], config.RAIO_SURTO_KM, config.JANELA_SURTO_DIAS)
        casos = len(proximas)
        surto = casos >= config.MIN_CASOS_SURTO
        if surto:
            store.marcar_surto([o["id"] for o in proximas])
            vizinhos = [v for v in store.usuarios_proximos(lat, lon, config.RAIO_SURTO_KM, excluir_chat_id=ctx.chat_id)
                        if not v.get("is_tecnico")]
            agora = time.time()
            for v in vizinhos:
                chave = (v["chat_id"], d["praga"])
                if agora - _ultimo_alerta.get(chave, 0) < INTERVALO_ALERTA_SEG:
                    continue
                _ultimo_alerta[chave] = agora
                ctx.acoes.append({
                    "tipo": "mensagem",
                    "chat_id": v["chat_id"],
                    "canal": v.get("canal", "telegram"),
                    "texto": (
                        f"⚠️ *Alerta GuarAssist*\n\n"
                        f"Foram confirmados *{casos} casos de {d['praga_nome']}* a menos de "
                        f"{config.RAIO_SURTO_KM:.0f} km da sua área nos últimos {config.JANELA_SURTO_DIAS} dias.\n\n"
                        f"Dá uma olhada nas suas plantas, principalmente em: {info.get('parte', 'folhas e ramos novos')}.\n"
                        f"Sinal pra procurar: {info.get('sintomas', '')}\n\n"
                        f"Achou algo diferente? Me manda uma foto aqui que eu analiso. 📸"
                    ),
                })
                vizinhos_avisados += 1

    # ── Técnico: caso grave confirmado OU qualquer caso que precisa de confirmação humana ──
    precisa_confirmar = d["veredito"] in {"provavel", "suspeita", "nao_verificado"}
    grave = d["veredito"] == "confirmado" and (surto or d["severidade"] == "severa" or info.get("risco") == "critico")
    tecnico_acionado = False
    if (grave or precisa_confirmar) and tecnicos:
        for t in tecnicos:
            ctx.acoes.append({
                "tipo": "mensagem",
                "chat_id": t["chat_id"],
                "canal": t.get("canal", "telegram"),
                "texto": _msg_tecnico(nome, d, plantas_afetadas, lat, lon, surto, casos, precisa_confirmar),
            })
        tecnico_acionado = True

    resposta.update({
        "casos_confirmados_na_regiao": casos,
        "surto": surto,
        "vizinhos_alertados": vizinhos_avisados,
        "tecnico_acionado": tecnico_acionado,
        "economia": eco,
    })
    return resposta


# ══════════════════════════════════════════════════════════════════════════════
# 4. Clima (Open-Meteo, grátis, sem chave)
# ══════════════════════════════════════════════════════════════════════════════

def consultar_clima(ctx: Contexto):
    lat, lon = store.posicao_do_usuario(ctx.usuario)
    try:
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "precipitation_sum,precipitation_probability_max,temperature_2m_max",
                "timezone": "America/Manaus",
                "forecast_days": 3,
            },
            timeout=8,
        )
        r.raise_for_status()
        dia = r.json()["daily"]
    except Exception as e:
        return {"erro": f"Previsão indisponível agora ({e.__class__.__name__})."}

    previsao = []
    for i, data in enumerate(dia["time"]):
        previsao.append({
            "data": data,
            "chuva_mm": dia["precipitation_sum"][i],
            "chance_chuva_pct": dia["precipitation_probability_max"][i],
            "temp_max": dia["temperature_2m_max"][i],
        })
    melhor = next((p for p in previsao if (p["chance_chuva_pct"] or 0) < 50), None)
    return {
        "previsao_3_dias": previsao,
        "melhor_dia_para_aplicar": melhor["data"] if melhor else None,
        "regra": "Evitar aplicar produto com chance de chuva alta nas próximas horas, a chuva lava o produto.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. Situação da região
# ══════════════════════════════════════════════════════════════════════════════

def consultar_regiao(ctx: Contexto):
    lat, lon = store.posicao_do_usuario(ctx.usuario)
    desde = time.time() - config.JANELA_SURTO_DIAS * 86400
    confirmados, em_avaliacao = {}, {}
    for o in store.listar_ocorrencias(limite=2000):
        if o["timestamp"] < desde or o.get("validacao") == "saudavel" or o["praga"] == "saudavel":
            continue
        if store.distancia_km(lat, lon, o["lat"], o["lon"]) > config.RAIO_SURTO_KM:
            continue
        alvo = confirmados if o.get("validacao") == "confirmado" else em_avaliacao
        alvo[o["praga_nome"]] = alvo.get(o["praga_nome"], 0) + 1
    return {
        "raio_km": config.RAIO_SURTO_KM,
        "dias": config.JANELA_SURTO_DIAS,
        "casos_confirmados": confirmados,
        "casos_aguardando_tecnico": em_avaliacao,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. Retorno proativo
# ══════════════════════════════════════════════════════════════════════════════

def agendar_retorno(ctx: Contexto, mensagem: str = None, dias: int = 3):
    # Regra no código: só acompanha foto de guaraná com problema (confirmado, provável, suspeita...).
    # Pergunta de texto, foto saudável ou rejeitada não geram retorno.
    d = ctx.diagnostico or {}
    if d.get("veredito") not in VEREDITOS_COM_PROBLEMA:
        return {"agendado": False,
                "motivo": "Retorno só é agendado quando uma foto de guaraná mostra problema. Não mencione retorno."}
    praga = (ctx.diagnostico or {}).get("praga_nome", "a planta")
    texto = mensagem or (
        f"Oi! Passando pra saber como estão as plantas depois daquela {praga}. "
        f"A mancha aumentou, diminuiu ou ficou igual? Me manda uma foto nova da mesma planta. 📸"
    )
    ctx.acoes.append({
        "tipo": "retorno",
        "chat_id": ctx.chat_id,
        "canal": ctx.canal,
        "segundos": config.FOLLOWUP_SEGUNDOS,
        "texto": "🔁 " + texto,
    })
    return {"agendado": True, "quando_para_o_produtor": f"em {dias} dias"}


# ══════════════════════════════════════════════════════════════════════════════
# 7. Dados da propriedade
# ══════════════════════════════════════════════════════════════════════════════

def salvar_area(ctx: Contexto, area_ha: float):
    store.salvar_area(ctx.chat_id, float(area_ha))
    if ctx.usuario is not None:
        ctx.usuario["area_ha"] = float(area_ha)
    return {"salvo": True, "area_ha": float(area_ha)}


# ══════════════════════════════════════════════════════════════════════════════
# Registro das ferramentas (nome -> função) e declarações para o Gemini
# ══════════════════════════════════════════════════════════════════════════════

FUNCOES = {
    "diagnosticar_foto": diagnosticar_foto,
    "registrar_ocorrencia": registrar_ocorrencia,
    "calcular_economia": calcular_economia,
    "consultar_clima": consultar_clima,
    "consultar_regiao": consultar_regiao,
    "agendar_retorno": agendar_retorno,
    "salvar_area": salvar_area,
}

DECLARACOES = [
    {
        "name": "diagnosticar_foto",
        "description": "Roda o modelo de visão treinado do GuarAssist na foto que o produtor acabou de mandar. "
                       "Retorna a praga/doença, confiança, severidade e o manejo recomendado. Use sempre que houver foto.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "registrar_ocorrencia",
        "description": "Registra o diagnóstico no mapa da região. Verifica automaticamente se há surto por perto, "
                       "alerta produtores vizinhos e aciona o técnico se for grave. Chame depois de diagnosticar_foto.",
        "parameters": {
            "type": "object",
            "properties": {
                "plantas_afetadas": {"type": "integer", "description": "Quantas plantas estão com o sintoma. Use 1 se não souber."},
            },
        },
    },
    {
        "name": "calcular_economia",
        "description": "Estima quanto o produtor economiza em reais e litros tratando só as plantas afetadas em vez da área toda.",
        "parameters": {
            "type": "object",
            "properties": {
                "plantas_afetadas": {"type": "integer"},
                "area_ha": {"type": "number", "description": "Área total em hectares, se o produtor informou."},
            },
            "required": ["plantas_afetadas"],
        },
    },
    {
        "name": "consultar_clima",
        "description": "Previsão de chuva dos próximos 3 dias na localização do produtor, para decidir o melhor dia de aplicar produto.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "consultar_regiao",
        "description": "Mostra quantos casos de cada praga foram registrados perto do produtor nos últimos dias.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "agendar_retorno",
        "description": "Agenda o agente para voltar a falar com o produtor e pedir uma foto nova, para acompanhar a evolução.",
        "parameters": {
            "type": "object",
            "properties": {
                "mensagem": {"type": "string", "description": "Mensagem curta que será enviada no retorno."},
                "dias": {"type": "integer", "description": "Em quantos dias voltar (normalmente 3)."},
            },
        },
    },
    {
        "name": "salvar_area",
        "description": "Salva o tamanho da área de guaraná do produtor em hectares, quando ele informar.",
        "parameters": {
            "type": "object",
            "properties": {"area_ha": {"type": "number"}},
            "required": ["area_ha"],
        },
    },
]


def executar(nome, argumentos, ctx: Contexto):
    func = FUNCOES.get(nome)
    if func is None:
        return {"erro": f"Ferramenta desconhecida: {nome}"}
    ctx.ferramentas_usadas.append(nome)
    try:
        return func(ctx, **(argumentos or {}))
    except TypeError:
        # LLM mandou argumento inesperado: tenta sem argumentos
        return func(ctx)
    except Exception as e:
        print(f"[agente] erro na ferramenta {nome}: {e}")
        return {"erro": f"Falha em {nome}: {e.__class__.__name__}"}