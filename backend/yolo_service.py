"""
GuarAssist - Serviço de Detecção YOLOv8
========================================
Responsabilidade única: receber uma imagem e retornar as patologias detectadas.

Por que arquivo separado?
  Manter o serviço de IA isolado das rotas e do banco facilita:
  - Trocar o modelo (genérico → treinado) sem mexer em mais nada
  - Testar a detecção independentemente do resto do backend
  - Futuro: substituir YOLOv8 por outro modelo sem reescrever tudo

Problemas que você pode enfrentar:
  - ultralytics é pesado (~500MB). No Railway/Render gratuito pode estourar memória.
  - Sem GPU, a detecção demora mais (2-5s por imagem no CPU).
  - O modelo genérico NÃO conhece pragas do guaraná — só serve pra testar o fluxo.
    Quando o modelo treinado ficar pronto, só troca o caminho em MODEL_PATH.
"""

from ultralytics import YOLO
from pathlib import Path
import numpy as np
import cv2

# ── Configuração do modelo ────────────────────────────────────────────────────
# Caminho do modelo. Troca aqui quando o modelo treinado estiver pronto:
#   MODEL_PATH = Path(__file__).parent / "models" / "guarana_best.pt"
# Por enquanto usa o genérico (baixado automaticamente na primeira execução):
MODEL_PATH = "yolov8n.pt"

# Confiança mínima para considerar uma detecção válida (0.0 a 1.0)
# 0.5 = 50% — abaixo disso ignora. Ajuste conforme a precisão do modelo.
CONFIANCA_MINIMA = 0.5

# Mapeamento: classe do modelo → nome da patologia no banco
# Quando o modelo for treinado com as patologias do guaraná,
# atualize este dicionário com os nomes exatos usados no treinamento.
CLASSES_PATOLOGIAS = {
    "antracnose":         "Antracnose",
    "superbrotamento":    "Superbrotamento",
    "tripes":             "Tripes",
    "mancha_angular":     "Mancha angular",
    "oidio":              "Oídio",
    "crestamento":        "Crestamento abiótico",
    "formiga_cortadeira": "Formiga cortadeira",
    "broca_caule":        "Broca do caule",
    # Modelo genérico: classes comuns do COCO (só pra testar o fluxo)
    "person": None,  # None = ignorar
}

# Singleton do modelo — carregado uma vez, reutilizado em todas as requisições
_modelo = None


def _carregar_modelo():
    """Carrega o modelo na memória uma única vez (lazy loading)."""
    global _modelo
    if _modelo is None:
        _modelo = YOLO(MODEL_PATH)
    return _modelo


def detectar_patologias(imagem_bytes: bytes) -> dict:
    """
    Recebe os bytes de uma imagem e retorna as patologias detectadas.

    Parâmetros:
        imagem_bytes: conteúdo bruto do arquivo de imagem (jpg, png, etc.)

    Retorna:
        {
          "patologias": [
            {"nome": "Antracnose", "confianca": 0.94, "severidade": "severa"},
            ...
          ],
          "total_deteccoes": 1,
          "imagem_anotada": "<base64>"  # imagem com bounding boxes desenhadas
        }

    Problemas possíveis:
        - imagem corrompida ou formato não suportado → retorna erro amigável
        - modelo não carregado → exception com mensagem clara
    """
    modelo = _carregar_modelo()

    # Converte bytes → array numpy → imagem OpenCV
    arr = np.frombuffer(imagem_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return {"erro": "Não foi possível ler a imagem. Verifique o formato (jpg, png)."}

    # Roda a detecção
    resultados = modelo(img, conf=CONFIANCA_MINIMA, verbose=False)

    patologias_detectadas = []

    for resultado in resultados:
        for box in resultado.boxes:
            classe_id   = int(box.cls[0])
            classe_nome = modelo.names[classe_id].lower()
            confianca   = float(box.conf[0])

            # Mapeia para o nome do catálogo do banco
            nome_patologia = CLASSES_PATOLOGIAS.get(classe_nome)
            if nome_patologia is None:
                continue  # classe ignorada (ex: "person" do modelo genérico)

            patologias_detectadas.append({
                "nome":       nome_patologia,
                "confianca":  round(confianca, 4),
                "severidade": _calcular_severidade(confianca),
            })

    # Desenha as bounding boxes na imagem e converte pra base64
    img_anotada = _anotar_imagem(img, resultados, modelo)

    return {
        "patologias":       patologias_detectadas,
        "total_deteccoes":  len(patologias_detectadas),
        "imagem_anotada":   img_anotada,
    }


def _calcular_severidade(confianca: float) -> str:
    """
    Estima severidade com base na confiança do modelo.
    Quando o modelo for treinado, isso pode vir direto do dataset.

    Problemas: confiança alta não significa necessariamente severa —
    é uma aproximação até ter dados reais de severidade.
    """
    if confianca >= 0.85:
        return "severa"
    elif confianca >= 0.70:
        return "moderada"
    else:
        return "leve"


def _anotar_imagem(img, resultados, modelo) -> str:
    """
    Desenha as bounding boxes na imagem e retorna em base64.
    O frontend pode exibir diretamente num <img src="data:image/jpeg;base64,...">

    Por que base64? Evita salvar arquivos em disco no servidor,
    o que é problemático em ambientes de deploy como Railway/Render.
    """
    import base64

    img_anotada = resultados[0].plot()  # YOLOv8 já tem método pra desenhar
    _, buffer = cv2.imencode(".jpg", img_anotada)
    return base64.b64encode(buffer).decode("utf-8")
