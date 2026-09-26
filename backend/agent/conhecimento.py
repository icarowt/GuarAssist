"""
Base de conhecimento das pragas e doenças que o modelo YOLO do GuarAssist reconhece.
Os textos das 4 primeiras vêm do catálogo em database/database.py (Embrapa).

A chave de cada item é o nome da classe que o models/detector.py devolve.
"""

PRAGAS = {
    "antracnose": {
        "parte": "folhas e brotos novos, ramos e frutos",
        "nome": "Antracnose",
        "cientifico": "Colletotrichum guaranicola",
        "tipo": "fungo",
        "risco": "critico",
        "espalha_com_chuva": True,
        "sintomas": "Manchas escuras e secas nas folhas e brotos novos. Principal causa de baixa produtividade no Amazonas.",
        "manejo": "Podar e retirar da área os ramos atacados. Fungicida preventivo antes da época de chuva. Usar clones resistentes (BRS Maués).",
        "produtos": "Cercobin 700, Folicur 200 (sempre com receituário agronômico)",
        "fonte": "Embrapa Amazônia Ocidental",
    },
    "superbrotamento": {
        "parte": "brotos e flores",
        "nome": "Superbrotamento",
        "cientifico": "Fitoplasma",
        "tipo": "fitoplasma",
        "risco": "critico",
        "espalha_com_chuva": False,
        "sintomas": "Brotos e flores embolados, formando uma massa densa. Pode acabar com toda a produção da planta.",
        "manejo": "Podar o ramo 10 cm abaixo da parte embolada e queimar. Vistoriar as plantas a cada 30 dias. Não existe remédio químico que resolva.",
        "produtos": "Nenhum produto químico eficaz. Controle só por poda.",
        "fonte": "Pereira, Embrapa, 2005",
    },
    "mancha_angular": {
        "parte": "folhas de baixo (ramos baixeiros)",
        "nome": "Mancha angular",
        "cientifico": "Xanthomonas campestris pv. paullinae",
        "tipo": "bactéria",
        "risco": "alto",
        "espalha_com_chuva": True,
        "sintomas": "Manchas com aspecto oleoso e halo amarelo nas folhas de baixo, que ficam marrom-avermelhadas. Perigosa em planta nova.",
        "manejo": "Retirar e destruir as folhas atacadas. Aplicação preventiva de produto à base de cobre.",
        "produtos": "Oxicloreto de cobre (sempre com receituário agronômico)",
        "fonte": "Embrapa Amazônia Ocidental",
    },
    "oidio": {
        "parte": "folhas e brotos novos",
        "nome": "Oídio",
        "cientifico": "Oidium anacardii",
        "tipo": "fungo",
        "risco": "medio",
        "espalha_com_chuva": False,
        "sintomas": "Pó branco acinzentado em cima das folhas e brotos novos. A planta cresce menos.",
        "manejo": "Aplicar enxofre ou fungicida específico para oídio. Aparece mais no período seco.",
        "produtos": "Enxofre molhável (sempre com receituário agronômico)",
        "fonte": "Embrapa Amazônia Ocidental",
    },
    "cochonilha": {
        "parte": "ramos e parte de baixo das folhas",
        "nome": "Cochonilha",
        "cientifico": "Hemiptera: Coccoidea",
        "tipo": "inseto",
        "risco": "medio",
        "espalha_com_chuva": False,
        "sintomas": "Pequenos insetos grudados em ramos e folhas, às vezes com aspecto de cera branca. Pode aparecer fumagina (mofo preto) e formigas por perto.",
        "manejo": "Podar e retirar os ramos mais atacados. Controlar as formigas que protegem a cochonilha. Produto só se a infestação for alta, com orientação técnica.",
        "produtos": "Inseticida registrado para a cultura, com orientação técnica",
        "fonte": "Orientação geral de manejo integrado de pragas",
    },
    "mosca_das_frutas": {
        "parte": "frutos",
        "nome": "Mosca-das-frutas",
        "cientifico": "Diptera: Tephritidae",
        "tipo": "inseto",
        "risco": "alto",
        "espalha_com_chuva": False,
        "sintomas": "Frutos furados, amolecidos ou caindo antes da hora, às vezes com larvas dentro.",
        "manejo": "Catar e enterrar os frutos caídos. Colocar armadilhas com isca para monitorar. Colher no ponto certo.",
        "produtos": "Isca tóxica em pontos, com orientação técnica",
        "fonte": "Orientação geral de manejo integrado de pragas",
    },
}


def buscar(chave_ou_nome):
    """Aceita a chave do YOLO ('mancha_angular') ou o nome ('Mancha angular')."""
    if not chave_ou_nome:
        return None
    alvo = str(chave_ou_nome).strip().lower().replace(" ", "_").replace("-", "_")
    alvo = alvo.replace("í", "i").replace("ó", "o")
    if alvo in PRAGAS:
        return PRAGAS[alvo]
    for chave, info in PRAGAS.items():
        if alvo in chave or chave in alvo:
            return info
    return None


def resumo_para_prompt():
    linhas = []
    for chave, p in PRAGAS.items():
        linhas.append(f"- {p['nome']} ({p['tipo']}, risco {p['risco']}): {p['sintomas']}")
    return "\n".join(linhas)
