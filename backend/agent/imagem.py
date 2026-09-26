"""
Qualidade de imagem: medir, corrigir de leve, ou pedir outra foto.
====================================================================
Regra de ouro: NÃO aplicar filtro em toda foto. O modelo reconhece doença por cor
e textura (mancha escura, pó branco, halo amarelo); filtro forte muda isso e gera
falso positivo. Aqui só corrigimos LUZ e CONTRASTE, e só quando a foto precisa.

    Escura / sem contraste  -> CLAHE no canal de luminosidade (cor preservada)
    Cor muito puxada        -> balanço de branco suave (50% do ajuste)
    Tremida / muito pequena -> não tem conserto: pede outra foto com dica prática

A segunda checagem (verificador) continua olhando a foto ORIGINAL, então se a
correção "inventar" algo, ela não confirma.
"""
import cv2
import numpy as np

from agent import config

# Limiares (medidos numa versão redimensionada para 800 px de largura)
BRILHO_ESCURO = config._float("IMG_BRILHO_ESCURO", 80)      # média de luminosidade 0-255
BRILHO_ESTOURADO = config._float("IMG_BRILHO_ESTOURADO", 215)
CONTRASTE_BAIXO = config._float("IMG_CONTRASTE_BAIXO", 35)  # desvio padrão da luminosidade
NITIDEZ_MINIMA = config._float("IMG_NITIDEZ_MINIMA", 4)     # nitidez normalizada; dataset real fica acima de 5
LADO_MINIMO = int(config._float("IMG_LADO_MINIMO", 120))    # px
DESVIO_COR = config._float("IMG_DESVIO_COR", 30)            # diferença entre canais de cor
CORRIGIR_COR = config._float("IMG_CORRIGIR_COR", 0) == 1     # desligado: risco de mexer na cor do sintoma


def _decodificar(foto: bytes):
    arr = np.frombuffer(foto, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _padronizar(img):
    h, w = img.shape[:2]
    if w <= 800:
        return img
    escala = 800 / w
    return cv2.resize(img, (800, int(h * escala)), interpolation=cv2.INTER_AREA)


def analisar(foto: bytes) -> dict:
    img = _decodificar(foto)
    if img is None:
        return {"valida": False, "problemas": ["arquivo"], "dica": "Não consegui abrir a imagem. Manda de novo como foto."}

    h, w = img.shape[:2]
    p = _padronizar(img)
    cinza = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
    brilho = float(cinza.mean())
    contraste = float(cinza.std())
    # Nitidez normalizada pelo contraste: foto escura não pode parecer "tremida"
    norm = (cinza.astype(np.float64) - brilho) / max(contraste, 1.0) * 50.0
    nitidez = float(cv2.Laplacian(norm, cv2.CV_64F).var())
    b, g, r = [float(c.mean()) for c in cv2.split(p)]
    desvio_cor = max(b, g, r) - min(b, g, r) if brilho > 40 else 0.0
    # Folha é verde e o fruto do guaraná é vermelho: só corrige cor se ativado e se for azulado forte
    cor_puxada = CORRIGIR_COR and desvio_cor > DESVIO_COR and b > g and b > r

    problemas, corrigiveis = [], []
    if min(h, w) < LADO_MINIMO:
        problemas.append("pequena")
    if nitidez < NITIDEZ_MINIMA:
        problemas.append("tremida")
    if brilho < BRILHO_ESCURO:
        problemas.append("escura"); corrigiveis.append("escura")
    if brilho > BRILHO_ESTOURADO and contraste < 45:
        problemas.append("estourada")
    if contraste < CONTRASTE_BAIXO and "escura" not in problemas:
        problemas.append("sem_contraste"); corrigiveis.append("sem_contraste")
    if cor_puxada:
        problemas.append("cor_puxada"); corrigiveis.append("cor_puxada")

    irrecuperavel = any(x in problemas for x in ("pequena", "tremida", "estourada"))
    return {
        "valida": not irrecuperavel,
        "precisa_melhorar": bool(corrigiveis) and not irrecuperavel,
        "problemas": problemas,
        "corrigiveis": corrigiveis,
        "metricas": {
            "brilho": round(brilho, 1), "contraste": round(contraste, 1),
            "nitidez": round(nitidez, 1), "largura": w, "altura": h,
        },
        "dica": dica(problemas) if irrecuperavel else None,
    }


def dica(problemas) -> str:
    if "estourada" in problemas:
        return "A foto ficou clara demais (sol direto). Faz sombra com o corpo ou com a mão e tira de novo."
    if "tremida" in problemas:
        return ("A foto saiu tremida ou fora de foco. Encosta o celular a mais ou menos um palmo da folha, "
                "toca na tela em cima da mancha pra focar e segura firme uns 2 segundos.")
    if "pequena" in problemas:
        return "A foto ficou muito pequena. Manda pela câmera normal, sem cortar, e chega mais perto da parte doente."
    if "estourada" in problemas:
        return "A foto ficou clara demais (sol direto). Faz sombra com o corpo ou com a mão e tira de novo."
    return "Tira outra foto bem de perto, com luz do dia."


def melhorar(foto: bytes, correcoes=None) -> bytes:
    """Correção leve: luz e contraste (CLAHE no canal L) e balanço de branco suave."""
    img = _decodificar(foto)
    if img is None:
        return foto
    correcoes = correcoes or ["escura", "sem_contraste"]

    if "cor_puxada" in correcoes:
        # Gray-world aplicado pela metade, pra não "lavar" o verde da folha
        medias = img.reshape(-1, 3).mean(axis=0)
        alvo = medias.mean()
        ganho = 1 + 0.5 * (alvo / np.maximum(medias, 1) - 1)
        img = np.clip(img.astype(np.float32) * ganho, 0, 255).astype(np.uint8)

    if "escura" in correcoes or "sem_contraste" in correcoes:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        if "escura" in correcoes:
            # Gama suave só na luminosidade: clareia sombra sem estourar o claro
            tabela = np.array([((i / 255.0) ** 0.75) * 255 for i in range(256)]).astype(np.uint8)
            l = cv2.LUT(l, tabela)
        img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes() if ok else foto
