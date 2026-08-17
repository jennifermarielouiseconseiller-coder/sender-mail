"""
Bot Telegram d'envoi d'emails via SendGrid.
Mode: polling (bot Telegram classique, sans interface web).

Commande principale:
    /email destinataire@mail.com | Sujet | Message
"""
import os
import re
import logging
from pathlib import Path

from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("email-bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

# Liste blanche d'IDs Telegram autorisés (séparés par des virgules)
AUTHORIZED_USER_IDS = {
    int(uid.strip())
    for uid in os.getenv("AUTHORIZED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
}

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    # Si aucune liste n'est configurée, on bloque par sécurité.
    if not AUTHORIZED_USER_IDS:
        return False
    return user.id in AUTHORIZED_USER_IDS


async def deny(update: Update) -> None:
    uid = update.effective_user.id if update.effective_user else "inconnu"
    await update.message.reply_text(
        f"⛔ Accès refusé. Votre ID Telegram ({uid}) n'est pas autorisé à utiliser ce bot."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return
    await update.message.reply_text(
        "👋 *Bot d'envoi d'emails SendGrid*\n\n"
        "Utilisez la commande /email pour envoyer un email.\n\n"
        "*Format :*\n"
        "`/email destinataire@mail.com | Sujet | Message`\n\n"
        "Exemple :\n"
        "`/email jean@exemple.com | Bonjour | Ceci est un test`\n\n"
        "Tapez /help pour plus d'infos.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return
    await update.message.reply_text(
        "ℹ️ *Aide*\n\n"
        "*Envoyer un email :*\n"
        "`/email destinataire@mail.com | Sujet | Message`\n\n"
        "Les parties sont séparées par le caractère `|`.\n"
        "Le message peut contenir plusieurs lignes.\n\n"
        f"*Expéditeur configuré :* `{SENDER_EMAIL or 'non configuré'}`\n"
        "*Votre ID Telegram :* `"
        f"{update.effective_user.id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Votre ID Telegram est : {update.effective_user.id}"
    )


def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Envoie un email via SendGrid. Retourne (succès, message)."""
    if not SENDGRID_API_KEY:
        return False, "Clé SendGrid non configurée (SENDGRID_API_KEY)."
    if not SENDER_EMAIL:
        return False, "Email expéditeur non configuré (SENDER_EMAIL)."

    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to,
        subject=subject,
        plain_text_content=body,
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code in (200, 201, 202):
            return True, f"Statut SendGrid : {response.status_code}"
        return False, f"SendGrid a répondu avec le statut {response.status_code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


async def email_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await deny(update)
        return

    raw = update.message.text
    # Retire la commande /email (et un éventuel @nom_du_bot)
    payload = re.sub(r"^/email(@\w+)?\s*", "", raw, flags=re.IGNORECASE).strip()

    if not payload:
        await update.message.reply_text(
            "❌ Format invalide.\n\n"
            "Utilisez :\n"
            "/email destinataire@mail.com | Sujet | Message",
        )
        return

    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Format invalide. Il faut 3 parties séparées par `|`.\n\n"
            "Exemple :\n"
            "`/email jean@exemple.com | Bonjour | Ceci est un test`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    to = parts[0]
    subject = parts[1]
    body = "|".join(parts[2:]).strip()  # au cas où le message contient des |

    if not EMAIL_REGEX.match(to):
        await update.message.reply_text(f"❌ Adresse email invalide : {to}")
        return
    if not subject:
        await update.message.reply_text("❌ Le sujet ne peut pas être vide.")
        return
    if not body:
        await update.message.reply_text("❌ Le message ne peut pas être vide.")
        return

    await update.message.reply_text("📤 Envoi en cours...")
    ok, detail = send_email(to, subject, body)
    if ok:
        await update.message.reply_text(
            f"✅ Email envoyé à {to}\nSujet : {subject}"
        )
        logger.info("Email envoyé à %s par %s", to, update.effective_user.id)
    else:
        await update.message.reply_text(f"❌ Échec de l'envoi.\nDétail : {detail}")
        logger.error("Échec envoi à %s : %s", to, detail)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN manquant dans .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("email", email_cmd))

    logger.info("Bot démarré. Utilisateurs autorisés : %s", AUTHORIZED_USER_IDS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
