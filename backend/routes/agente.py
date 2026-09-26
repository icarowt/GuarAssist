"""
Rotas do agente para o painel React (mapa em tempo real).

GET /api/ocorrencias          -> lista de pontos para o mapa
GET /api/ocorrencias/resumo   -> números para os cards do painel
"""
from fastapi import APIRouter

from agent import store

router = APIRouter()


@router.get("/ocorrencias")
def listar_ocorrencias(limite: int = 500):
    """
    Cada item: id, nome_produtor, timestamp, praga, praga_nome, confianca,
    severidade (leve|moderada|severa|saudavel), plantas_afetadas, lat, lon,
    economia_reais, economia_litros, surto (0|1)
    """
    return store.listar_ocorrencias(limite=limite)


@router.get("/ocorrencias/resumo")
def resumo():
    return store.resumo()
