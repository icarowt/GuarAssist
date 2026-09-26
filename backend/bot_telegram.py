"""
GuarAssist no Telegram
======================
Adaptador do canal Telegram. Toda a inteligência fica em agent/core.py.

Rodar (dentro da pasta backend, com o venv ativo):
    python bot_telegram.py

Comandos do bot:
    /start    boas-vindas + botão para compartilhar localização
    /tecnico  marca este chat como TÉCNICO (recebe os casos graves)
    /produtor volta a ser produtor
    /area 3   salva a área em hectares
    /painel   link do mapa
    /resumo   números gerais (bom para o pitch)
    /reset    limpa a memória da conversa
"""
import asyncio
import logging
import os

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from agent import config, core, prompt, store

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("guarassist.telegram")

PAINEL_URL = os.getenv("PAINEL_URL", "http://localhost:5173")

TECLADO_LOCALIZACAO = ReplyKeyboardMarkup(
    [[KeyboardButton("📍 Compartilhar minha localização", request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# Envio seguro (Markdown pode quebrar com texto do LLM; aí manda sem formatação)
# ══════════════════════════════════════════════════════════════════════════════

async def enviar_texto(bot, chat_id, texto, **kwargs):
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except BadRequest:
        await bot.send_message(chat_id=chat_id, text=texto.replace("*", "").replace("_", ""), **kwargs)


async def manter_digitando(bot, chat_id, acao, parar: asyncio.Event):
    while not parar.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=acao)
        except Exception:
            pass
        try:
            await asyncio.wait_for(parar.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


async def executar_acoes(bot, acoes):
    """Executa as ações que o agente decidiu (alertar vizinhos, técnico, retorno)."""
    for acao in acoes:
        if acao.get("canal", "telegram") != "telegram":
            continue  # outro canal (ex.: WhatsApp) cuida disso
        if acao["tipo"] == "mensagem":
            try:
                await enviar_texto(bot, acao["chat_id"], acao["texto"])
                log.info("alerta enviado para %s", acao["chat_id"])
            except Exception as e:
                log.warning("não consegui alertar %s: %s", acao["chat_id"], e)
        elif acao["tipo"] == "retorno":
            asyncio.create_task(_retorno_agendado(bot, acao))
            log.info("retorno agendado para %s em %ss", acao["chat_id"], acao["segundos"])


async def _retorno_agendado(bot, acao):
    await asyncio.sleep(acao["segundos"])
    try:
        await enviar_texto(bot, acao["chat_id"], acao["texto"])
    except Exception as e:
        log.warning("retorno falhou: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# Fluxo principal: qualquer mensagem -> agente -> resposta
# ══════════════════════════════════════════════════════════════════════════════

async def atender(update: Update, context: ContextTypes.DEFAULT_TYPE, texto=None, foto=None,
                  audio=None, audio_mime="audio/ogg"):
    chat_id = update.effective_chat.id
    nome = update.effective_user.first_name if update.effective_user else None

    parar = asyncio.Event()
    acao_status = ChatAction.UPLOAD_PHOTO if foto else ChatAction.TYPING
    digitando = asyncio.create_task(manter_digitando(context.bot, chat_id, acao_status, parar))

    try:
        resp = await asyncio.to_thread(
            core.processar, chat_id, texto=texto, foto=foto, audio=audio,
            audio_mime=audio_mime, nome=nome, canal="telegram",
        )
    except Exception as e:
        log.exception("erro no agente")
        parar.set()
        await digitando
        await update.message.reply_text("Deu um probleminha aqui do meu lado. 😕 Tenta de novo em instantes?")
        return
    finally:
        parar.set()

    await digitando

    if resp.imagem_anotada:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=resp.imagem_anotada,
                                         caption="🔍 Onde o modelo encontrou o problema")
        except Exception as e:
            log.warning("imagem anotada não enviada: %s", e)

    await enviar_texto(context.bot, chat_id, resp.texto)

    if resp.audio:
        try:
            await context.bot.send_voice(chat_id=chat_id, voice=resp.audio)
        except Exception:
            try:
                await context.bot.send_audio(chat_id=chat_id, audio=resp.audio, title="GuarAssist")
            except Exception as e:
                log.warning("áudio não enviado: %s", e)

    await executar_acoes(context.bot, resp.acoes)

    u = store.buscar_usuario(chat_id) or {}
    if foto and u.get("lat") is None and not context.chat_data.get("pediu_localizacao"):
        context.chat_data["pediu_localizacao"] = True
        await update.message.reply_text(
            "📍 Dica: compartilha sua localização pra eu te avisar quando aparecer praga perto da sua roça.",
            reply_markup=TECLADO_LOCALIZACAO,
        )


async def on_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:
        arquivo = await msg.photo[-1].get_file()
    else:  # foto enviada como arquivo
        arquivo = await msg.document.get_file()
    dados = bytes(await arquivo.download_as_bytearray())
    await atender(update, context, texto=msg.caption, foto=dados)


async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    midia = msg.voice or msg.audio
    arquivo = await midia.get_file()
    dados = bytes(await arquivo.download_as_bytearray())
    mime = getattr(midia, "mime_type", None) or "audio/ogg"
    await atender(update, context, texto=msg.caption, audio=dados, audio_mime=mime)


async def on_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await atender(update, context, texto=update.message.text)


async def on_localizacao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    loc = update.message.location
    store.garantir_usuario(chat_id, nome=update.effective_user.first_name)
    store.salvar_localizacao(chat_id, loc.latitude, loc.longitude)
    await update.message.reply_text(
        "✅ Localização salva! Agora eu te aviso se aparecer praga perto da sua roça.\n\n"
        "📸 Pode mandar a foto da planta.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Comandos
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name if update.effective_user else None
    store.garantir_usuario(update.effective_chat.id, nome=nome)
    texto = prompt.BOAS_VINDAS.format(nome=f", {nome}" if nome else "")
    try:
        await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN, reply_markup=TECLADO_LOCALIZACAO)
    except BadRequest:
        await update.message.reply_text(texto.replace("*", ""), reply_markup=TECLADO_LOCALIZACAO)


async def cmd_tecnico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store.garantir_usuario(update.effective_chat.id, nome=update.effective_user.first_name)
    store.marcar_tecnico(update.effective_chat.id, True)
    await update.message.reply_text("🧑‍🌾 Pronto! Este chat agora é de TÉCNICO e vai receber os casos graves e surtos.")


async def cmd_produtor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store.marcar_tecnico(update.effective_chat.id, False)
    await update.message.reply_text("🌱 Ok, voltou a ser produtor.")


async def cmd_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        area = float(context.args[0].replace(",", "."))
    except (IndexError, ValueError):
        await update.message.reply_text("Usa assim: /area 3  (em hectares)")
        return
    store.garantir_usuario(update.effective_chat.id, nome=update.effective_user.first_name)
    store.salvar_area(update.effective_chat.id, area)
    await update.message.reply_text(f"✅ Área salva: {area:g} hectares (uns {int(area * config.PLANTAS_POR_HECTARE)} pés).")


async def cmd_painel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🗺️ Mapa de ocorrências em tempo real:\n{PAINEL_URL}")


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = store.resumo()
    pragas = "\n".join(f"• {k}: {v}" for k, v in r["por_praga"].items()) or "• nenhuma ainda"
    await update.message.reply_text(
        f"📊 GuarAssist em números\n\n"
        f"Diagnósticos: {r['total_ocorrencias']}\n"
        f"Produtores atendidos: {r['produtores']}\n"
        f"Com praga: {r['com_praga']} ({r['confirmados']} confirmados, {r['aguardando_tecnico']} aguardando técnico)\n"
        f"Sem praga: {r['saudaveis']}\n"
        f"Surtos ativos: {r['surtos_ativos']}\n"
        f"Economia estimada: R$ {r['economia_reais']:.0f} e {r['economia_litros']:.0f} L de calda\n\n"
        f"Por praga:\n{pragas}"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    core.limpar_historico(update.effective_chat.id)
    await update.message.reply_text("🧹 Memória da conversa limpa.")


# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not config.TELEGRAM_TOKEN:
        raise SystemExit("❌ Falta TELEGRAM_TOKEN no arquivo backend/.env")

    modo = f"Gemini ({config.GEMINI_MODEL})" if config.GEMINI_API_KEY else "SÓ YOLO (sem GEMINI_API_KEY)"
    print(f"🌱 GuarAssist Telegram iniciando | modo: {modo} | retorno em {config.FOLLOWUP_SEGUNDOS}s")

    # Carrega o YOLO já na partida, pra primeira foto não demorar
    try:
        from models.detector import _carregar_modelo
        _carregar_modelo()
    except Exception as e:
        print(f"⚠️ YOLO não carregou agora ({e}); vai tentar na primeira foto.")

    app = Application.builder().token(config.TELEGRAM_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("tecnico", cmd_tecnico))
    app.add_handler(CommandHandler("produtor", cmd_produtor))
    app.add_handler(CommandHandler("area", cmd_area))
    app.add_handler(CommandHandler("painel", cmd_painel))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("reset", cmd_reset))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_foto))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_audio))
    app.add_handler(MessageHandler(filters.LOCATION, on_localizacao))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_texto))

    print("✅ Bot no ar. Manda /start pro seu bot no Telegram. (Ctrl+C para parar)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
