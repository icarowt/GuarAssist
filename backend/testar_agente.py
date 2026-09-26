"""
Teste rápido do agente no terminal, sem Telegram.

    python testar_agente.py                         # usa uma foto de antracnose do dataset
    python testar_agente.py caminho/da/foto.jpg     # usa a sua foto
    python testar_agente.py "tá tudo pintado de preto nas folhas"   # só texto
"""
import sys
from pathlib import Path

from agent import config, core

PASTA = Path(__file__).parent / "database" / "img"


def foto_exemplo():
    for pasta in ["Guarana-Antracnose", "Guarana-Superbrotamento", "Guarana-Saudavel"]:
        fotos = sorted((PASTA / pasta).glob("*.png")) + sorted((PASTA / pasta).glob("*.jp*g"))
        if fotos:
            return fotos[0]
    return None


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    foto, texto = None, None

    if arg and Path(arg).exists():
        foto = Path(arg).read_bytes()
        print(f"📸 Foto: {arg}")
    elif arg:
        texto = arg
        print(f"💬 Texto: {texto}")
    else:
        caminho = foto_exemplo()
        foto = caminho.read_bytes()
        print(f"📸 Foto de exemplo: {caminho.name}")

    print(f"🤖 Modo: {'Gemini ' + config.GEMINI_MODEL if config.GEMINI_API_KEY else 'só YOLO'}\n")
    r = core.processar("teste-terminal", texto=texto, foto=foto, nome="Raimundo", canal="terminal")

    print("─" * 60)
    print(r.texto)
    print("─" * 60)
    print(f"Ferramentas usadas: {r.ferramentas}")
    print(f"Imagem anotada: {'sim' if r.imagem_anotada else 'não'}")
    print(f"Ações para o canal executar: {len(r.acoes)}")
    for a in r.acoes:
        print(f"  • {a['tipo']} -> {a['chat_id']}")


if __name__ == "__main__":
    main()
