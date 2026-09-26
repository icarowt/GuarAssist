"""
Persistência do agente no mesmo SQLite do backend (database/guarassist.db).
Usa tabelas próprias (prefixo agente_) para não mexer no schema existente.
"""
import math
import random
import sqlite3
import time
from pathlib import Path

from agent import config

DB_PATH = Path(__file__).parent.parent / "database" / "guarassist.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS agente_usuarios (
    chat_id     TEXT PRIMARY KEY,
    canal       TEXT DEFAULT 'telegram',
    nome        TEXT,
    lat         REAL,
    lon         REAL,
    area_ha     REAL,
    is_tecnico  INTEGER DEFAULT 0,
    criado_em   INTEGER
);

CREATE TABLE IF NOT EXISTS agente_ocorrencias (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id           TEXT,
    nome_produtor     TEXT,
    timestamp         INTEGER,
    praga             TEXT,        -- chave do YOLO ou 'saudavel'
    praga_nome        TEXT,
    confianca         REAL,
    severidade        TEXT,        -- leve | moderada | severa | saudavel
    plantas_afetadas  INTEGER,
    lat               REAL,
    lon               REAL,
    economia_reais    REAL DEFAULT 0,
    economia_litros   REAL DEFAULT 0,
    surto             INTEGER DEFAULT 0,
    validacao         TEXT DEFAULT 'confirmado'  -- confirmado | provavel | suspeita | saudavel | nao_verificado
);
"""


def _conectar():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conectar() as conn:
        conn.executescript(SCHEMA)
        # Migração: bancos criados pela versão anterior não têm a coluna validacao
        colunas = [r["name"] for r in conn.execute("PRAGMA table_info(agente_ocorrencias)")]
        if "validacao" not in colunas:
            conn.execute("ALTER TABLE agente_ocorrencias ADD COLUMN validacao TEXT DEFAULT 'confirmado'")


init()


# ── Usuários ──────────────────────────────────────────────────────────────────

def garantir_usuario(chat_id, nome=None, canal="telegram"):
    chat_id = str(chat_id)
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM agente_usuarios WHERE chat_id = ?", (chat_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO agente_usuarios (chat_id, canal, nome, criado_em) VALUES (?, ?, ?, ?)",
                (chat_id, canal, nome, int(time.time())),
            )
        elif nome and not row["nome"]:
            conn.execute("UPDATE agente_usuarios SET nome = ? WHERE chat_id = ?", (nome, chat_id))
    return buscar_usuario(chat_id)


def buscar_usuario(chat_id):
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM agente_usuarios WHERE chat_id = ?", (str(chat_id),)).fetchone()
        return dict(row) if row else None


def salvar_localizacao(chat_id, lat, lon):
    with _conectar() as conn:
        conn.execute("UPDATE agente_usuarios SET lat = ?, lon = ? WHERE chat_id = ?", (lat, lon, str(chat_id)))


def salvar_area(chat_id, area_ha):
    with _conectar() as conn:
        conn.execute("UPDATE agente_usuarios SET area_ha = ? WHERE chat_id = ?", (area_ha, str(chat_id)))


def marcar_tecnico(chat_id, valor=True):
    with _conectar() as conn:
        conn.execute("UPDATE agente_usuarios SET is_tecnico = ? WHERE chat_id = ?", (1 if valor else 0, str(chat_id)))


def listar_tecnicos():
    with _conectar() as conn:
        rows = conn.execute("SELECT * FROM agente_usuarios WHERE is_tecnico = 1").fetchall()
        return [dict(r) for r in rows]


def posicao_do_usuario(usuario):
    """Localização real se houver; senão Maués com um desvio de até ~1,5 km (para o mapa não empilhar pontos)."""
    if usuario and usuario.get("lat") is not None and usuario.get("lon") is not None:
        return usuario["lat"], usuario["lon"]
    return (
        config.LAT_PADRAO + random.uniform(-0.012, 0.012),
        config.LON_PADRAO + random.uniform(-0.012, 0.012),
    )


# ── Ocorrências ───────────────────────────────────────────────────────────────

def registrar_ocorrencia(dados):
    campos = [
        "chat_id", "nome_produtor", "timestamp", "praga", "praga_nome", "confianca",
        "severidade", "plantas_afetadas", "lat", "lon", "economia_reais", "economia_litros", "surto", "validacao",
    ]
    valores = [dados.get(c) for c in campos]
    with _conectar() as conn:
        cur = conn.execute(
            f"INSERT INTO agente_ocorrencias ({', '.join(campos)}) VALUES ({', '.join('?' * len(campos))})",
            valores,
        )
        return cur.lastrowid


def marcar_surto(ids):
    if not ids:
        return
    with _conectar() as conn:
        conn.executemany("UPDATE agente_ocorrencias SET surto = 1 WHERE id = ?", [(i,) for i in ids])


def listar_ocorrencias(limite=500):
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM agente_ocorrencias ORDER BY timestamp DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(r) for r in rows]


def distancia_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def ocorrencias_proximas(lat, lon, praga, raio_km, dias):
    desde = int(time.time()) - dias * 86400
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM agente_ocorrencias WHERE praga = ? AND timestamp >= ? AND validacao = 'confirmado'",
            (praga, desde),
        ).fetchall()
    return [dict(r) for r in rows if distancia_km(lat, lon, r["lat"], r["lon"]) <= raio_km]


def usuarios_proximos(lat, lon, raio_km, excluir_chat_id=None):
    with _conectar() as conn:
        rows = conn.execute("SELECT * FROM agente_usuarios").fetchall()
    vizinhos = []
    for r in rows:
        if str(r["chat_id"]) == str(excluir_chat_id):
            continue
        u_lat, u_lon = r["lat"], r["lon"]
        if u_lat is None or u_lon is None:
            # Sem localização: considera que está na região padrão (útil na demo)
            u_lat, u_lon = config.LAT_PADRAO, config.LON_PADRAO
        if distancia_km(lat, lon, u_lat, u_lon) <= raio_km:
            vizinhos.append(dict(r))
    return vizinhos


def resumo():
    ocorr = listar_ocorrencias(limite=100000)
    com_praga = [o for o in ocorr if o.get("validacao") != "saudavel" and o["praga"] != "saudavel"]
    por_praga = {}
    for o in com_praga:
        por_praga[o["praga_nome"]] = por_praga.get(o["praga_nome"], 0) + 1
    return {
        "total_ocorrencias": len(ocorr),
        "com_praga": len(com_praga),
        "saudaveis": len(ocorr) - len(com_praga),
        "produtores": len({o["chat_id"] for o in ocorr}),
        "economia_reais": round(sum(o["economia_reais"] or 0 for o in ocorr), 2),
        "economia_litros": round(sum(o["economia_litros"] or 0 for o in ocorr), 1),
        "confirmados": sum(1 for o in com_praga if o.get("validacao") == "confirmado"),
        "aguardando_tecnico": sum(1 for o in com_praga if o.get("validacao") in ("provavel", "suspeita", "nao_verificado")),
        "surtos_ativos": len({o["praga"] for o in com_praga if o["surto"]}),
        "por_praga": por_praga,
    }
