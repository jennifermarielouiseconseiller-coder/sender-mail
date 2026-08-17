"""
Bot Telegram d'envoi d'emails via Resend.
- Flux guidé étape par étape avec boutons.
- Choix du compte/clé d'envoi (Compte 1 / Compte 2).
- Nom d'expéditeur personnalisable (par défaut + modifiable à chaque envoi).
- Accès restreint à une liste blanche d'IDs Telegram.
"""
import os
import re
import json
import logging
from pathlib import Path

import resend
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
CONFIG_FILE = BASE_DIR / "config.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("email-bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

AUTHORIZED_USER_IDS = {
    int(uid.strip())
    for uid in os.getenv("AUTHORIZED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
}

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# --- Conversation states ---
CHOOSE_ACCOUNT, ASK_NAME, ASK_TO, ASK_SUBJECT, ASK_BODY, CONFIRM = range(6)


# ---------------------------------------------------------------------------
# Comptes / clés
# ---------------------------------------------------------------------------
def load_accounts() -> list[dict]:
    """Charge les comptes depuis les variables ACCOUNT_n_KEY / _SENDER / _LABEL."""
    accounts = []
    for i in range(1, 21):
        key = os.getenv(f"ACCOUNT_{i}_KEY", "").strip()
        sender = os.getenv(f"ACCOUNT_{i}_SENDER", "").strip()
        label = os.getenv(f"ACCOUNT_{i}_LABEL", f"Compte {i}").strip()
        if key and sender:
            accounts.append({"index": i, "label": label, "key": key, "sender": sender})
    return accounts


ACCOUNTS = load_accounts()


# ---------------------------------------------------------------------------
# Réglages persistés (nom d'expéditeur par défaut)
# ---------------------------------------------------------------------------
def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))


def get_default_name() -> str:
    return load_config().get("default_from_name", "")


# ---------------------------------------------------------------------------
# Autorisation
# ---------------------------------------------------------------------------
def is_authorized(update: Update) -> bool:
    user = update.effective_user
    if not user or not AUTHORIZED_USER_IDS:
        return False
    return user.id in AUTHORIZED_USER_IDS


async def deny(update: Update) -> None:
    uid = update.effective_user.id if update.effective_user else "inconnu"
    await update.effective_message.reply_text(
        f"⛔ Accès refusé. Votre ID Telegram ({uid}) n'est pas autorisé."
    )


# ---------------------------------------------------------------------------
# Envoi Resend
# ---------------------------------------------------------------------------
def build_from(name: str, sender_email: str) -> str:
    name = (name or "").strip()
    return f"{name} <{sender_email}>" if name else sender_email


def send_email(account: dict, from_name: str, to: str, subject: str, body: str) -> tuple[bool, str]:
    resend.api_key = account["key"]
    try:
        result = resend.Emails.send({
            "from": build_from(from_name, account["sender"]),
            "to": [to],
            "subject": subject,
            "text": body,
        })
        email_id = result.get("id") if isinstance(result, dict) else None
        return True, f"ID Resend : {email_id}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


# ---------------------------------------------------------------------------
# Commandes simples
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return
    await update.message.reply_text(
        "👋 *Bot d'envoi d'emails (Resend)*\n\n"
        "✉️ /email — envoyer un email (assistant guidé)\n"
        "🏷️ /nom — définir votre nom d'expéditeur par défaut\n"
        "📇 /comptes — voir les comptes d'envoi disponibles\n"
        "❓ /help — aide\n\n"
        "Tapez /email pour commencer.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return
    default_name = get_default_name() or "(aucun)"
    lignes = "\n".join(f"• {a['label']} — `{a['sender']}`" for a in ACCOUNTS) or "(aucun)"
    await update.message.reply_text(
        "ℹ️ *Aide*\n\n"
        "*Envoyer :* /email (assistant pas à pas avec boutons).\n"
        "*Nom par défaut :* /nom VotreNom (ex: `/nom Faracosta`).\n"
        "Vous pouvez aussi changer le nom à chaque envoi.\n\n"
        f"*Nom d'expéditeur par défaut :* `{default_name}`\n"
        f"*Comptes d'envoi :*\n{lignes}\n\n"
        f"*Votre ID Telegram :* `{update.effective_user.id}`\n\n"
        "💡 Le nom d'expéditeur est libre et n'affecte pas la délivrabilité ; "
        "seule compte l'adresse (domaine vérifié).",
        parse_mode=ParseMode.MARKDOWN,
    )


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Votre ID Telegram est : {update.effective_user.id}"
    )


async def comptes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return
    if not ACCOUNTS:
        await update.message.reply_text("Aucun compte d'envoi configuré.")
        return
    lignes = "\n".join(f"• *{a['label']}* — `{a['sender']}`" for a in ACCOUNTS)
    await update.message.reply_text(
        f"📇 *Comptes d'envoi disponibles :*\n{lignes}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return
    name = " ".join(context.args).strip() if context.args else ""
    cfg = load_config()
    cfg["default_from_name"] = name
    save_config(cfg)
    if name:
        await update.message.reply_text(f"✅ Nom d'expéditeur par défaut réglé sur : « {name} »")
    else:
        await update.message.reply_text("✅ Nom d'expéditeur par défaut supprimé (aucun nom).")


# ---------------------------------------------------------------------------
# Flux guidé (ConversationHandler)
# ---------------------------------------------------------------------------
def account_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(a["label"], callback_data=f"acct:{a['index']}")] for a in ACCOUNTS]
    rows.append([InlineKeyboardButton("❌ Annuler", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def name_keyboard() -> InlineKeyboardMarkup:
    default_name = get_default_name()
    rows = []
    if default_name:
        rows.append([InlineKeyboardButton(f"👤 {default_name} (par défaut)", callback_data="name:default")])
    rows.append([InlineKeyboardButton("🚫 Sans nom", callback_data="name:none")])
    rows.append([InlineKeyboardButton("❌ Annuler", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Envoyer", callback_data="send")],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


async def email_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized(update):
        await deny(update)
        return ConversationHandler.END
    if not ACCOUNTS:
        await update.message.reply_text("⚠️ Aucun compte d'envoi configuré. Contactez l'administrateur.")
        return ConversationHandler.END

    context.user_data.clear()

    # Raccourci « une ligne » : /email dest | sujet | message
    raw = update.message.text or ""
    payload = re.sub(r"^/email(@\w+)?\s*", "", raw, flags=re.IGNORECASE).strip()
    if "|" in payload:
        return await _quick_send(update, context, payload)

    if len(ACCOUNTS) == 1:
        context.user_data["account"] = ACCOUNTS[0]
        return await _ask_name(update, context)

    await update.message.reply_text(
        "📤 *Nouvel email*\n\nDepuis quel compte voulez-vous envoyer ?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=account_keyboard(),
    )
    return CHOOSE_ACCOUNT


async def _quick_send(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str) -> int:
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Format rapide invalide. Utilisez plutôt /email seul pour l'assistant guidé."
        )
        return ConversationHandler.END
    to, subject = parts[0], parts[1]
    body = "|".join(parts[2:]).strip()
    if not EMAIL_REGEX.match(to):
        await update.message.reply_text(f"❌ Adresse email invalide : {to}")
        return ConversationHandler.END
    account = ACCOUNTS[0]
    await update.message.reply_text("📤 Envoi en cours...")
    ok, detail = send_email(account, get_default_name(), to, subject, body)
    await update.message.reply_text(
        f"✅ Email envoyé à {to}" if ok else f"❌ Échec.\nDétail : {detail}"
    )
    return ConversationHandler.END


async def choose_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    account = next((a for a in ACCOUNTS if a["index"] == idx), None)
    if not account:
        await query.edit_message_text("Compte introuvable. /email pour recommencer.")
        return ConversationHandler.END
    context.user_data["account"] = account
    await query.edit_message_text(f"✅ Compte : *{account['label']}* (`{account['sender']}`)",
                                  parse_mode=ParseMode.MARKDOWN)
    return await _ask_name(update, context)


async def _ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    await msg.reply_text(
        "🏷️ *Nom d'expéditeur ?*\n\nTapez le nom à afficher, ou utilisez un bouton.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=name_keyboard(),
    )
    return ASK_NAME


async def name_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]
    name = get_default_name() if choice == "default" else ""
    context.user_data["from_name"] = name
    shown = name if name else "(sans nom)"
    await query.edit_message_text(f"🏷️ Nom d'expéditeur : {shown}")
    await query.message.reply_text("📧 À quelle *adresse email* envoyer ?", parse_mode=ParseMode.MARKDOWN)
    return ASK_TO


async def name_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["from_name"] = update.message.text.strip()
    await update.message.reply_text("📧 À quelle *adresse email* envoyer ?", parse_mode=ParseMode.MARKDOWN)
    return ASK_TO


async def ask_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    to = update.message.text.strip()
    if not EMAIL_REGEX.match(to):
        await update.message.reply_text("❌ Adresse invalide. Réessayez (ex: nom@exemple.com) :")
        return ASK_TO
    context.user_data["to"] = to
    await update.message.reply_text("📝 Quel est le *sujet* ?", parse_mode=ParseMode.MARKDOWN)
    return ASK_SUBJECT


async def ask_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text("💬 Écrivez le *message* :", parse_mode=ParseMode.MARKDOWN)
    return ASK_BODY


async def ask_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["body"] = update.message.text
    d = context.user_data
    account = d["account"]
    name = d.get("from_name", "")
    apercu = (
        "👀 *Aperçu de l'email*\n\n"
        f"*De :* {build_from(name, account['sender'])}\n"
        f"*À :* {d['to']}\n"
        f"*Sujet :* {d['subject']}\n"
        f"*Message :*\n{d['body']}\n\n"
        "Confirmez l'envoi ?"
    )
    await update.message.reply_text(apercu, parse_mode=ParseMode.MARKDOWN, reply_markup=confirm_keyboard())
    return CONFIRM


async def confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    d = context.user_data
    await query.edit_message_text("📤 Envoi en cours...")
    ok, detail = send_email(d["account"], d.get("from_name", ""), d["to"], d["subject"], d["body"])
    if ok:
        await query.message.reply_text(f"✅ Email envoyé à {d['to']} !")
        logger.info("Email envoyé à %s par %s", d["to"], update.effective_user.id)
    else:
        await query.message.reply_text(f"❌ Échec de l'envoi.\nDétail : {detail}")
        logger.error("Échec envoi à %s : %s", d["to"], detail)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Annulé.")
    else:
        await update.message.reply_text("❌ Annulé.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN manquant dans .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("email", email_start)],
        states={
            CHOOSE_ACCOUNT: [
                CallbackQueryHandler(choose_account, pattern=r"^acct:"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
            ],
            ASK_NAME: [
                CallbackQueryHandler(name_button, pattern=r"^name:"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_typed),
            ],
            ASK_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_to)],
            ASK_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_subject)],
            ASK_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_body)],
            CONFIRM: [
                CallbackQueryHandler(confirm_send, pattern=r"^send$"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
            ],
        },
        fallbacks=[CommandHandler("annuler", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("comptes", comptes))
    app.add_handler(CommandHandler("nom", set_name))
    app.add_handler(conv)

    logger.info("Bot démarré. Comptes: %s | Utilisateurs autorisés: %s",
                 [a["label"] for a in ACCOUNTS], AUTHORIZED_USER_IDS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
