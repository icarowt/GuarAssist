"""
GuarAssist - Rota de Análise de Imagens
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image
import io
import time

from models.detector import detectar
from database.database import save_analysis

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024
FORMATOS_PERMITIDOS = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}


@router.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    # Validação de tipo MIME
    if file.content_type not in FORMATOS_PERMITIDOS:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use JPG, PNG ou WEBP.")

    # Validação de extensão
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in EXTENSOES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Extensão inválida. Use .jpg, .png ou .webp")

    # Lê os bytes
    conteudo = await file.read()

    # Validação de tamanho
    if len(conteudo) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo grande demais. Máximo: 10 MB.")

    # Valida se é imagem real
    try:
        img_pil = Image.open(io.BytesIO(conteudo))
        img_pil.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Arquivo corrompido ou não é uma imagem válida.")

    # Roda o detector
    resultado = detectar(conteudo)

    if resultado.get("status") == "erro":
        raise HTTPException(status_code=400, detail=resultado.get("erro"))

    # Adiciona timestamp
    timestamp = int(time.time())
    resultado["timestamp"] = timestamp

    # Salva no banco usando os nomes corretos do database.py
    try:
        save_analysis({
            "timestamp": timestamp,
            "filename": file.filename,
            "status": resultado["status"],
            "disease": resultado.get("disease"),
            "confidence": resultado.get("confidence", 0.0),
        })
    except Exception as e:
        print(f"[GuarAssist] Erro ao salvar no banco: {e}")

    return resultado
