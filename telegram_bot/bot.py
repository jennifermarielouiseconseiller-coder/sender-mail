"""
Bot Telegram d'envoi d'emails via Resend.
- Flux guidé étape par étape avec boutons.
- Choix du compte/clé d'envoi (Compte 1 / Compte 2).
- Nom d'expéditeur personnalisable (par défaut + modifiable à chaque envoi).
- Accès restreint à une liste blanche d'IDs Telegram.
"""
import os
import re
import io
import json
import time
import asyncio
import logging
from pathlib import Path

import resend
from dotenv import load_dotenv
from telegram import (
    Update,
    InputFile,
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

# Délai entre deux envois en masse (secondes) — régule le débit (anti-spam / rate-limit)
MASS_SEND_DELAY = float(os.getenv("MASS_SEND_DELAY", "0.6"))

# --- Conversation states ---
CHOOSE_ACCOUNT, ASK_NAME, ASK_TO, ASK_SUBJECT, ASK_BODY, CONFIRM = range(6)

# --- Conversation states (envoi en masse) ---
(M_ACCOUNT, M_NAME, M_RECIPIENTS, M_SUBJECT, M_BODY, M_CONFIRM) = range(100, 106)


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


HTML_TAG_REGEX = re.compile(r"<(html|body|div|p|br|table|h[1-6]|a|img|span|ul|ol|li|strong|em|b|i)\b", re.IGNORECASE)


def looks_like_html(text: str) -> bool:
    """Détecte si un contenu ressemble à du HTML (balises courantes présentes)."""
    return bool(text) and bool(HTML_TAG_REGEX.search(text))


def send_email(account: dict, from_name: str, to: str, subject: str, body: str,
               is_html: bool = False) -> tuple[bool, str]:
    resend.api_key = account["key"]
    payload = {
        "from": build_from(from_name, account["sender"]),
        "to": [to],
        "subject": subject,
    }
    if is_html:
        payload["html"] = body
    else:
        payload["text"] = body
    try:
        result = resend.Emails.send(payload)
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
        "👋 *L3 SENDER*\n\n"
        "✉️ /email — envoyer un email (assistant guidé)\n"
        "📣 /masse — envoi en masse (liste + suivi + échecs)\n"
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
        "*Envoi en masse :* /masse (liste `.txt` ou collée → même email pour tous, "
        "suivi en direct + rapport des échecs).\n"
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
    ok, detail = send_email(account, get_default_name(), to, subject, body,
                            is_html=looks_like_html(body))
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
    await update.message.reply_text(
        "💬 Envoyez le *message* :\n\n"
        "• Tapez votre texte, *ou*\n"
        "• Collez directement du *code HTML*, *ou*\n"
        "• Envoyez un *fichier* `.html` en pièce jointe.\n\n"
        "Le HTML est détecté automatiquement et l'email sera envoyé au bon format.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_BODY


async def _finish_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Affiche l'aperçu une fois le corps du message renseigné."""
    d = context.user_data
    account = d["account"]
    name = d.get("from_name", "")
    is_html = d.get("is_html", False)

    body = d["body"]
    if is_html:
        extrait = body if len(body) <= 500 else body[:500] + "\n… (tronqué)"
        corps_apercu = f"🧩 *Contenu HTML* ({len(body)} caractères) :\n```\n{extrait}\n```"
    else:
        corps_apercu = f"*Message :*\n{body}"

    apercu = (
        "👀 *Aperçu de l'email*\n\n"
        f"*De :* {build_from(name, account['sender'])}\n"
        f"*À :* {d['to']}\n"
        f"*Sujet :* {d['subject']}\n"
        f"*Format :* {'HTML' if is_html else 'Texte'}\n"
        f"{corps_apercu}\n\n"
        "Confirmez l'envoi ?"
    )
    await update.effective_message.reply_text(
        apercu, parse_mode=ParseMode.MARKDOWN, reply_markup=confirm_keyboard()
    )
    return CONFIRM


async def ask_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""
    context.user_data["body"] = text
    context.user_data["is_html"] = looks_like_html(text)
    return await _finish_body(update, context)


def _decode_bytes(raw: bytes) -> str:
    """Décode des octets en texte en essayant plusieurs encodages courants.

    UTF-16 n'est tenté que si un BOM UTF-16 est présent, sinon il « attrape »
    à tort des octets Latin-1/CP1252 et produit du texte illisible.
    """
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except (UnicodeDecodeError, LookupError):
            pass
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


async def ask_body_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Traite TOUT fichier envoyé en pièce jointe comme corps de l'email.

    On ne rejette plus selon l'extension/type MIME : on télécharge, on décode
    le texte, et on détecte le HTML d'après le contenu ou le nom du fichier.
    """
    doc = update.message.document
    filename = doc.file_name or "fichier"

    try:
        tg_file = await doc.get_file()
        content_bytes = await tg_file.download_as_bytearray()
        content = _decode_bytes(bytes(content_bytes))
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(
            f"❌ Impossible de télécharger le fichier : {e}\n"
            "Astuce : Telegram limite les fichiers reçus par un bot à ~20 Mo."
        )
        return ASK_BODY

    if not content.strip():
        await update.message.reply_text("❌ Le fichier semble vide ou illisible. Réessayez :")
        return ASK_BODY

    name_is_html = filename.lower().endswith((".html", ".htm"))
    is_html = name_is_html or looks_like_html(content)

    context.user_data["body"] = content
    context.user_data["is_html"] = is_html
    fmt = "HTML" if is_html else "Texte"
    await update.message.reply_text(
        f"📎 Fichier reçu : `{filename}` — {len(content)} caractères, format détecté : *{fmt}*.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return await _finish_body(update, context)


async def confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    d = context.user_data
    await query.edit_message_text("📤 Envoi en cours...")
    ok, detail = send_email(
        d["account"], d.get("from_name", ""), d["to"], d["subject"], d["body"],
        is_html=d.get("is_html", False),
    )
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
# Envoi en masse (/masse)
# ---------------------------------------------------------------------------
def parse_emails(text: str) -> tuple[list[str], list[str]]:
    """Extrait les emails d'un texte. Retourne (valides_dédupliqués, invalides)."""
    tokens = re.split(r"[\s,;]+", text or "")
    valid, invalid, seen = [], [], set()
    for tok in tokens:
        t = tok.strip().strip("<>").lower()
        if not t:
            continue
        if EMAIL_REGEX.match(t):
            if t not in seen:
                seen.add(t)
                valid.append(t)
        else:
            invalid.append(tok.strip())
    return valid, invalid


def mass_account_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(a["label"], callback_data=f"macct:{a['index']}")] for a in ACCOUNTS]
    rows.append([InlineKeyboardButton("❌ Annuler", callback_data="mcancel")])
    return InlineKeyboardMarkup(rows)


def mass_name_keyboard() -> InlineKeyboardMarkup:
    default_name = get_default_name()
    rows = []
    if default_name:
        rows.append([InlineKeyboardButton(f"👤 {default_name} (par défaut)", callback_data="mname:default")])
    rows.append([InlineKeyboardButton("🚫 Sans nom", callback_data="mname:none")])
    rows.append([InlineKeyboardButton("❌ Annuler", callback_data="mcancel")])
    return InlineKeyboardMarkup(rows)


def mass_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Lancer l'envoi en masse", callback_data="msend")],
        [InlineKeyboardButton("❌ Annuler", callback_data="mcancel")],
    ])


async def mass_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized(update):
        await deny(update)
        return ConversationHandler.END
    if not ACCOUNTS:
        await update.message.reply_text("⚠️ Aucun compte d'envoi configuré.")
        return ConversationHandler.END

    context.user_data.clear()
    if len(ACCOUNTS) == 1:
        context.user_data["account"] = ACCOUNTS[0]
        return await _mass_ask_name(update, context)

    await update.message.reply_text(
        "📣 *Envoi en masse*\n\nDepuis quel compte voulez-vous envoyer ?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=mass_account_keyboard(),
    )
    return M_ACCOUNT


async def mass_choose_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    account = next((a for a in ACCOUNTS if a["index"] == idx), None)
    if not account:
        await query.edit_message_text("Compte introuvable. /masse pour recommencer.")
        return ConversationHandler.END
    context.user_data["account"] = account
    await query.edit_message_text(f"✅ Compte : *{account['label']}* (`{account['sender']}`)",
                                  parse_mode=ParseMode.MARKDOWN)
    return await _mass_ask_name(update, context)


async def _mass_ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "🏷️ *Nom d'expéditeur ?*\n\nTapez le nom à afficher, ou utilisez un bouton.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=mass_name_keyboard(),
    )
    return M_NAME


async def _mass_ask_recipients_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "👥 *Destinataires ?*\n\n"
        "• Envoyez un *fichier* `.txt` (une adresse par ligne), *ou*\n"
        "• Collez la *liste* d'adresses (séparées par virgule, espace ou retour à la ligne).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return M_RECIPIENTS


async def mass_name_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]
    name = get_default_name() if choice == "default" else ""
    context.user_data["from_name"] = name
    await query.edit_message_text(f"🏷️ Nom d'expéditeur : {name if name else '(sans nom)'}")
    return await _mass_ask_recipients_prompt(update, context)


async def mass_name_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["from_name"] = update.message.text.strip()
    return await _mass_ask_recipients_prompt(update, context)


async def _mass_store_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    valid, invalid = parse_emails(text)
    if not valid:
        await update.effective_message.reply_text(
            "❌ Aucune adresse valide trouvée. Renvoyez un fichier `.txt` ou collez la liste :",
            parse_mode=ParseMode.MARKDOWN,
        )
        return M_RECIPIENTS
    context.user_data["recipients"] = valid
    msg = f"✅ *{len(valid)}* destinataire(s) valides détecté(s)."
    if invalid:
        apercu = ", ".join(invalid[:5]) + ("…" if len(invalid) > 5 else "")
        msg += f"\n⚠️ {len(invalid)} entrée(s) ignorée(s) (invalides) : {apercu}"
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    await update.effective_message.reply_text("📝 Quel est le *sujet* ?", parse_mode=ParseMode.MARKDOWN)
    return M_SUBJECT


async def mass_recipients_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _mass_store_recipients(update, context, update.message.text or "")


async def mass_recipients_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    try:
        tg_file = await doc.get_file()
        raw = await tg_file.download_as_bytearray()
        content = _decode_bytes(bytes(raw))
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(f"❌ Impossible de lire le fichier : {e}")
        return M_RECIPIENTS
    return await _mass_store_recipients(update, context, content)


async def mass_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text(
        "💬 Envoyez le *message* (identique pour tous) :\n\n"
        "• Tapez du texte, *ou* collez du *code HTML*, *ou* envoyez un *fichier* `.html`.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return M_BODY


async def _mass_finish_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = context.user_data
    account = d["account"]
    name = d.get("from_name", "")
    is_html = d.get("is_html", False)
    n = len(d.get("recipients", []))
    body = d["body"]
    extrait = body if len(body) <= 400 else body[:400] + "…"
    corps = f"```\n{extrait}\n```" if is_html else extrait
    apercu = (
        "👀 *Aperçu de l'envoi en masse*\n\n"
        f"*De :* {build_from(name, account['sender'])}\n"
        f"*Destinataires :* {n}\n"
        f"*Sujet :* {d['subject']}\n"
        f"*Format :* {'HTML' if is_html else 'Texte'}\n"
        f"*Débit :* ~1 email / {MASS_SEND_DELAY:g}s\n"
        f"{corps}\n\n"
        f"Lancer l'envoi aux *{n}* destinataires ?"
    )
    await update.effective_message.reply_text(
        apercu, parse_mode=ParseMode.MARKDOWN, reply_markup=mass_confirm_keyboard()
    )
    return M_CONFIRM


async def mass_body_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""
    context.user_data["body"] = text
    context.user_data["is_html"] = looks_like_html(text)
    return await _mass_finish_body(update, context)


async def mass_body_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    filename = doc.file_name or "fichier"
    try:
        tg_file = await doc.get_file()
        raw = await tg_file.download_as_bytearray()
        content = _decode_bytes(bytes(raw))
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(f"❌ Impossible de lire le fichier : {e}")
        return M_BODY
    if not content.strip():
        await update.message.reply_text("❌ Le fichier semble vide. Réessayez :")
        return M_BODY
    is_html = filename.lower().endswith((".html", ".htm")) or looks_like_html(content)
    context.user_data["body"] = content
    context.user_data["is_html"] = is_html
    await update.message.reply_text(
        f"📎 Fichier reçu : `{filename}` — format : *{'HTML' if is_html else 'Texte'}*.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return await _mass_finish_body(update, context)


async def _run_mass_send(bot, chat_id: int, account: dict, name: str,
                         recipients: list[str], subject: str, body: str,
                         is_html: bool, status_msg_id: int, user_id: int) -> None:
    total = len(recipients)
    sent_ok = 0
    failed: list[tuple[str, str]] = []
    last_edit = 0.0

    async def refresh(final: bool = False) -> None:
        done = sent_ok + len(failed)
        txt = (f"📤 *Envoi en masse en cours…*\n\n"
               f"Traités : *{done}/{total}*\n✅ Réussis : *{sent_ok}*\n❌ Échecs : *{len(failed)}*")
        if final:
            txt = (f"🏁 *Envoi en masse terminé*\n\n"
                   f"Total : *{total}*\n✅ Réussis : *{sent_ok}*\n❌ Échecs : *{len(failed)}*")
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=status_msg_id,
                                        text=txt, parse_mode=ParseMode.MARKDOWN)
        except Exception:  # noqa: BLE001
            pass

    for i, to in enumerate(recipients, 1):
        try:
            ok, detail = await asyncio.to_thread(
                send_email, account, name, to, subject, body, is_html
            )
        except Exception as e:  # noqa: BLE001
            ok, detail = False, str(e)
        if ok:
            sent_ok += 1
        else:
            failed.append((to, detail))
            logger.error("Masse: échec %s : %s", to, detail)

        now = time.monotonic()
        if i == total or now - last_edit >= 3:
            last_edit = now
            await refresh()
        if i < total:
            await asyncio.sleep(MASS_SEND_DELAY)

    await refresh(final=True)
    logger.info("Masse terminée par %s : %s/%s OK, %s échecs",
                user_id, sent_ok, total, len(failed))

    if failed:
        report = "Adresse;Raison\n" + "\n".join(f"{addr};{reason}" for addr, reason in failed)
        if len(failed) <= 20 and len(report) < 3500:
            lignes = "\n".join(f"• {addr} — {reason}" for addr, reason in failed)
            await bot.send_message(chat_id=chat_id,
                                   text=f"❌ *Détail des {len(failed)} échec(s) :*\n{lignes}",
                                   parse_mode=ParseMode.MARKDOWN)
        else:
            buf = io.BytesIO(report.encode("utf-8"))
            await bot.send_document(
                chat_id=chat_id,
                document=InputFile(buf, filename="echecs.csv"),
                caption=f"❌ {len(failed)} échec(s) — détail en pièce jointe.",
            )


async def mass_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    d = context.user_data
    recipients = d.get("recipients", [])
    total = len(recipients)
    account = d["account"]
    name = d.get("from_name", "")
    subject = d["subject"]
    body = d["body"]
    is_html = d.get("is_html", False)

    await query.edit_message_text(
        f"🚀 Lancement de l'envoi à *{total}* destinataire(s)…",
        parse_mode=ParseMode.MARKDOWN,
    )
    status = await query.message.reply_text(
        f"📤 *Envoi en masse en cours…*\n\nTraités : *0/{total}*\n✅ Réussis : *0*\n❌ Échecs : *0*",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Envoi en tâche de fond pour garder le bot réactif
    asyncio.create_task(_run_mass_send(
        context.bot, query.message.chat_id, account, name, recipients,
        subject, body, is_html, status.message_id, update.effective_user.id,
    ))
    context.user_data.clear()
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
            ASK_BODY: [
                MessageHandler(filters.Document.ALL, ask_body_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_body),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_send, pattern=r"^send$"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
            ],
        },
        fallbacks=[CommandHandler("annuler", cancel)],
    )

    conv_mass = ConversationHandler(
        entry_points=[CommandHandler("masse", mass_start)],
        states={
            M_ACCOUNT: [
                CallbackQueryHandler(mass_choose_account, pattern=r"^macct:"),
                CallbackQueryHandler(cancel, pattern=r"^mcancel$"),
            ],
            M_NAME: [
                CallbackQueryHandler(mass_name_button, pattern=r"^mname:"),
                CallbackQueryHandler(cancel, pattern=r"^mcancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mass_name_typed),
            ],
            M_RECIPIENTS: [
                MessageHandler(filters.Document.ALL, mass_recipients_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mass_recipients_text),
            ],
            M_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mass_subject)],
            M_BODY: [
                MessageHandler(filters.Document.ALL, mass_body_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mass_body_text),
            ],
            M_CONFIRM: [
                CallbackQueryHandler(mass_confirm, pattern=r"^msend$"),
                CallbackQueryHandler(cancel, pattern=r"^mcancel$"),
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
    app.add_handler(conv_mass)

    logger.info("Bot démarré. Comptes: %s | Utilisateurs autorisés: %s",
                 [a["label"] for a in ACCOUNTS], AUTHORIZED_USER_IDS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
