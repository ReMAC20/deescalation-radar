import os, sys, pathlib, logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from telegram import Update, __version__ as TG_VER
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
    BaseHandler,
)

HAVE_NATIVE_BIZ = True
try:
    from telegram.ext import (
        BusinessConnectionHandler, BusinessMessageHandler,
        EditedBusinessMessageHandler, DeletedBusinessMessagesHandler
    )
except Exception:
    HAVE_NATIVE_BIZ = False

if not HAVE_NATIVE_BIZ:
    class BusinessConnectionHandler(BaseHandler):
        def check_update(self, update: Update) -> bool:
            return getattr(update, "business_connection", None) is not None

        async def handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
            return await self.callback(update, context)


    class BusinessMessageHandler(BaseHandler):
        def __init__(self, callback): super().__init__(callback, block=False)

        def check_update(self, update: Update) -> bool:
            return getattr(update, "business_message", None) is not None

        async def handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
            return await self.callback(update, context)


    class EditedBusinessMessageHandler(BaseHandler):
        def __init__(self, callback): super().__init__(callback, block=False)

        def check_update(self, update: Update) -> bool:
            return getattr(update, "edited_business_message", None) is not None

        async def handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
            return await self.callback(update, context)


    class DeletedBusinessMessagesHandler(BaseHandler):
        def __init__(self, callback): super().__init__(callback, block=False)

        def check_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
            return getattr(update, "deleted_business_messages", None) is not None

        async def handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
            return await self.callback(update, context)

from src.core.config import Config
from src.core.engine import RulesEngine
from src.core.hints import pick_hints

try:
    from src.core.triggers import TriggerMatcher

    HAVE_TRIGGER_MATCHER = True
except Exception:
    TriggerMatcher = None
    HAVE_TRIGGER_MATCHER = False

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
CFG_PATH = os.getenv("CFG_PATH", "config/rules.yaml")
MODE = os.getenv("MODE", "pilot")

USER_CHAT_ID = os.getenv("USER_CHAT_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bizbot")
log.info("python-telegram-bot version: %s (native business handlers: %s) (trigger_matcher: %s)",
         TG_VER, HAVE_NATIVE_BIZ, HAVE_TRIGGER_MATCHER)

cfg = Config.from_yaml(CFG_PATH)
engine = RulesEngine(cfg)

trigger_matcher = TriggerMatcher(cfg) if HAVE_TRIGGER_MATCHER else None

business_user_chat_id: Optional[str] = USER_CHAT_ID if USER_CHAT_ID else None


def _short_snippet(text: Optional[str], length: int = 200) -> str:
    if not text:
        return "—"
    return (text[:length] + "...") if len(text) > length else text


def _extract_sender_repr(from_user) -> Optional[str]:
    if not from_user:
        return None
    parts = []
    fn = getattr(from_user, "first_name", None)
    ln = getattr(from_user, "last_name", None)
    if fn: parts.append(fn)
    if ln: parts.append(ln)
    name = " ".join(parts).strip() or None
    uname = getattr(from_user, "username", None)
    uid = getattr(from_user, "id", None)
    repr_parts = []
    if name:
        repr_parts.append(name)
    if uname:
        repr_parts.append(f"@{uname}")
    if uid is not None:
        repr_parts.append(f"[{uid}]")
    return " ".join(repr_parts) if repr_parts else None


def _chat_repr_from_msg(msg) -> str:
    try:
        chat = getattr(msg, 'chat', None) or getattr(msg, 'effective_chat', None)
        cid = getattr(chat, 'id', None) if chat is not None else getattr(msg, 'chat_id', None)

        if not chat:
            return f"неизвестный чат [{cid}]" if cid is not None else "неизвестный чат"

        ctype = getattr(chat, 'type', None)

        if ctype == 'private':

            first = getattr(chat, 'first_name', None)
            last = getattr(chat, 'last_name', None)
            title_name = " ".join(p for p in (first, last) if p).strip() or None
            username = getattr(chat, 'username', None)

            if title_name or username:
                display = title_name if title_name else f"@{username}"
                if username and title_name:
                    display = f"{title_name} (@{username})"
                return f"private: {display} [{cid}]"
            # fallback
            from_user = getattr(msg, 'from_user', None)
            if from_user:
                fn = getattr(from_user, 'first_name', None)
                ln = getattr(from_user, 'last_name', None)
                uname = getattr(from_user, 'username', None)
                name = " ".join(p for p in (fn, ln) if p).strip() or None
                if name or uname:
                    repr_name = name if name else f"@{uname}"
                    if uname and name:
                        repr_name = f"{name} (@{uname})"
                    return f"private: {repr_name} [{cid}]"
            return f"private: [{cid}]"

        title = getattr(chat, 'title', None)
        username = getattr(chat, 'username', None)
        if title:
            return f"{ctype}: {title} [{cid}]"
        if username:
            return f"{ctype}: @{username} [{cid}]"
        return f"{ctype}: [{cid}]"
    except Exception:
        try:
            return f"Чат: [{getattr(msg, 'chat_id', 'unknown')}]"
        except Exception:
            return "Чат: неизвестен"


def _get_matches(text: str, res_events: Optional[set] = None) -> Dict[str, list]:
    if not text:
        return {}
    if trigger_matcher:
        try:
            return trigger_matcher.get_matches(text)
        except Exception:
            log.exception("trigger_matcher.get_matches failed, falling back to simple matcher")
    matches = {}
    try:
        keywords = set()
        if hasattr(cfg, "rules") and isinstance(cfg.rules, dict):
            for ev, node in cfg.rules.items():
                keywords.add(ev)
        if res_events:
            keywords |= set(res_events)
        tlow = text.lower()
        for kw in sorted(keywords, key=lambda x: -len(x)):
            if not kw:
                continue
            k = str(kw).lower()
            if k in tlow:
                idx = tlow.find(k)
                start = max(0, idx - 15)
                end = min(len(text), idx + len(k) + 15)
                snippet = text[start:end].strip()
                matches.setdefault(str(kw), []).append(snippet)
    except Exception:
        log.exception("Simple matcher failed")
    return matches


def make_summary(res: Dict[str, Any], text: Optional[str] = None, matches: Optional[Dict[str, list]] = None,
                 sender: Optional[str] = None, chat_repr: Optional[str] = None) -> str:
    header_lines = []
    if chat_repr:
        header_lines.append(f"Чат: {chat_repr}")
    if sender:
        header_lines.append(f"От: {sender}")
    if text:
        header_lines.append(f"Сообщение: {_short_snippet(text, 300)}")
    if matches:
        mlines = []
        for ev, ms in matches.items():
            short_ms = [(m if len(m) <= 80 else (m[:77] + "...")) for m in (ms[:5])]
            mlines.append(f"{ev}: {', '.join(short_ms)}")
        header_lines.append("Триггеры: " + "; ".join(mlines))
    header = "\n".join(header_lines) if header_lines else "Чат: —"

    ev = ", ".join(res.get("events", [])) if res.get("events") else "—"
    bad = [r.get("id") for r in res.get("ltlf", []) if not r.get("ok")]
    viol = ", ".join(filter(None, bad)) or "—"
    body = (f"События: {ev}\nСостояние: {res.get('state')}\nРиск: {res.get('risk')}\nНарушения: {viol}")

    hints = []
    try:
        if trigger_matcher:
            hints = pick_hints(cfg, trigger_matcher, text or "", res.get("state"), set(res.get("events", [])), count=2,
                               user=sender, message=text)
        else:
            hints = pick_hints(cfg, res.get("state"), set(res.get("events", [])), count=2)
    except TypeError:
        try:
            hints = pick_hints(cfg, res.get("state"), set(res.get("events", [])), count=2)
        except Exception:
            hints = []
    except Exception:
        hints = []

    if hints:
        body += "\n\nПодсказки:\n- " + "\n- ".join(hints)

    return header + "\n\n" + body


async def send_to_business_user(context: ContextTypes.DEFAULT_TYPE, text: str):
    global business_user_chat_id
    if not business_user_chat_id:
        log.warning("send_to_business_user: business_user_chat_id не задан — пропускаем отправку")
        return
    try:
        await context.bot.send_message(chat_id=business_user_chat_id, text=text)
    except Exception as e:
        log.error("Не удалось отправить сообщение владельцу (chat_id=%s): %s", business_user_chat_id, e)


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Привет! Я радар деэскалации. Пиши сюда — я анализирую сообщения."
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    text = msg.text or ""
    chat_id = str(msg.chat_id)

    res = engine.process_message(chat_id, text)

    sender = _extract_sender_repr(getattr(msg, "from_user", None))
    matches = _get_matches(text, set(res.get("events", [])))

    await send_to_business_user(context, make_summary(res, text=text, matches=matches, sender=sender,
                                                      chat_repr=_chat_repr_from_msg(msg)))
    log.info("Processed non-business message from %s — summary sent to owner (if known).", chat_id)


async def on_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global business_user_chat_id
    bc = update.business_connection
    if not bc:
        return
    log.info("Business connection: id=%s can_reply=%s user_chat_id=%s", getattr(bc, "id", None),
             getattr(bc, "can_reply", None), getattr(bc, "user_chat_id", None))
    if getattr(bc, "user_chat_id", None):
        business_user_chat_id = str(bc.user_chat_id)
        log.info("Saved business_user_chat_id = %s", business_user_chat_id)
        try:
            await context.bot.send_message(chat_id=business_user_chat_id,
                                           text="🔗 Бизнес-бот подключён. Я буду отсылать сводки по сообщениям.")
        except Exception:
            log.exception("Не удалось отправить приветствие владельцу бизнес-аккаунта")
    else:
        log.warning("business_connection не содержит user_chat_id")


async def on_business_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message
    if not msg:
        return

    text = msg.text or msg.caption or ""
    chat_id = msg.chat_id
    bc_id = getattr(msg, "business_connection_id", None)
    log.info("business_message chat=%s bc_id=%s text=%r", chat_id, bc_id, text)

    res = engine.process_message(str(chat_id), text)

    sender = _extract_sender_repr(getattr(msg, "from_user", None))
    matches = _get_matches(text, set(res.get("events", [])))

    detailed = make_summary(res, text=text, matches=matches, sender=sender, chat_repr=_chat_repr_from_msg(msg))

    if business_user_chat_id:
        try:
            await context.bot.send_message(chat_id=business_user_chat_id, text=detailed)
            log.info("Detailed summary for business_message from %s sent to owner %s", chat_id, business_user_chat_id)
            return
        except Exception:
            log.exception(
                "Failed to send detailed summary to owner; will fallback to replying in business chat without owner info")

    try:
        anon_summary = make_summary(res, text=_short_snippet(text, 120), matches=matches, sender=None,
                                    chat_repr=_chat_repr_from_msg(msg))
        await context.bot.send_message(chat_id=chat_id, text=anon_summary, business_connection_id=bc_id)
        log.info("Fallback reply sent into business chat for chat=%s", chat_id)
    except Exception:
        log.exception("Failed to send fallback reply into business chat")


async def ignore(*_):
    return


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Укажи TELEGRAM_BOT_TOKEN (или BOT_TOKEN) в .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.add_handler(BusinessConnectionHandler(on_business_connection))
    app.add_handler(BusinessMessageHandler(on_business_text))
    app.add_handler(EditedBusinessMessageHandler(ignore))
    app.add_handler(DeletedBusinessMessagesHandler(ignore))

    allowed = [
        "message",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    ]
    app.run_polling(allowed_updates=allowed)


if __name__ == "__main__":
    main()
