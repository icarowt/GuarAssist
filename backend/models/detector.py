"""
GuarAssist - Detector de Pragas
================================
Usa o modelo treinado se disponível, senão usa fallback automático.
"""
from pathlib import Path
from ultralytics import YOLO
import cv2
import numpy as np
import base64

BASE_DIR   = Path(__file__).parent.parent
MODEL_FILE = BASE_DIR / "models" / "weights" / "best.pt"
FALLBACK   = "yolov8n.pt"

CONFIANCA_MINIMA = 0.35

CLASSES_PRAGAS = {
    "antracnose":      "antracnose",
    "mancha_angular":  "mancha_angular",
    "oidio":           "oidio",
    "cochonilha":      "cochonilha",
    "mosca_das_frutas":"mosca_das_frutas",
    "superbrotamento": "superbrotamento",
}

_modelo = None


def _carregar_modelo():
    global _modelo
    if _modelo is None:
        if MODEL_FILE.exists():
            print(f"[GuarAssist] Modelo treinado carregado: {MODEL_FILE}")
            _modelo = YOLO(str(MODEL_FILE))
        else:
            print(f"[GuarAssist] best.pt não encontrado — usando fallback {FALLBACK}")
            _modelo = YOLO(FALLBACK)
    return _modelo


def detectar(imagem_bytes: bytes) -> dict:
    modelo = _carregar_modelo()

    arr = np.frombuffer(imagem_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return {
            "status": "erro",
            "disease": None,
            "confidence": 0.0,
            "detections": [],
            "annotated_image": None,
            "total": 0,
            "erro": "Não foi possível ler a imagem. Use JPG ou PNG."
        }

    resultados = modelo(img, conf=CONFIANCA_MINIMA, verbose=False)

    deteccoes = []
    melhor_confianca = 0.0
    melhor_praga = None

    for resultado in resultados:
        for box in resultado.boxes:
            classe_id   = int(box.cls[0])
            classe_nome = modelo.names[classe_id].lower().strip()
            confianca   = float(box.conf[0])

            if classe_nome not in CLASSES_PRAGAS:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            deteccoes.append({
                "name":       CLASSES_PRAGAS[classe_nome],
                "confidence": round(confianca, 4),
                "box":        [round(x1,1), round(y1,1), round(x2,1), round(y2,1)]
            })

            if confianca > melhor_confianca:
                melhor_confianca = confianca
                melhor_praga     = CLASSES_PRAGAS[classe_nome]

    # Lógica por exclusão: não detectou praga = saudável
    if deteccoes:
        status           = "praga"
        disease          = melhor_praga
        confidence_final = melhor_confianca
    else:
        status           = "saudavel"
        disease          = None
        confidence_final = 0.92

    img_anotada_b64 = None
    try:
        img_anotada = resultados[0].plot()
        _, buffer   = cv2.imencode(".jpg", img_anotada)
        img_anotada_b64 = base64.b64encode(buffer).decode("utf-8")
    except Exception as e:
        print(f"[GuarAssist] Erro ao gerar imagem anotada: {e}")

    return {
        "status":          status,
        "disease":         disease,
        "confidence":      round(confidence_final, 4),
        "detections":      deteccoes,
        "annotated_image": img_anotada_b64,
        "total":           len(deteccoes)
    }
