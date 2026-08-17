# PRD — Bot Telegram d'envoi d'emails via SendGrid

## Problème initial
"Je veux créer un bot telegram avec mes clés SendGrid pour envoyer des emails."

## Choix utilisateur
- Type : bot Telegram classique (polling, sans interface web)
- Token Telegram : fourni par l'utilisateur (fonctionnel)
- Fonctionnalité : commande simple `/email destinataire | sujet | message`
- Accès : liste blanche d'IDs Telegram autorisés (8777096346)

## Architecture
- App standalone Python : `/app/telegram_bot/bot.py`
- Librairies : `python-telegram-bot==21.6`, `sendgrid`, `python-dotenv`
- Exécution : supervisor `telegram_bot` (`/etc/supervisor/conf.d/telegram_bot.conf`)
- Config : `/app/telegram_bot/.env`

## Implémenté (2026-08-17)
- Bot Telegram en ligne (connecté à Telegram, polling actif) ✅
- Commandes : `/start`, `/help`, `/whoami`, `/email` ✅
- Contrôle d'accès par liste blanche d'IDs ✅
- Envoi d'email via **Resend** (`noreply@topwork.se`, domaine `topwork.se` vérifié) ✅ TESTÉ de bout en bout (email envoyé avec succès, ID Resend retourné)
- Gestion d'erreurs + retour de statut à l'utilisateur ✅

## Note
- SendGrid abandonné (les 2 clés fournies étaient invalides/révoquées). Migration vers Resend.

## Backlog / Next
- P1 : Historique des envois, templates d'email, pièces jointes, support HTML
- P2 : Mode guidé étape par étape, tableau de bord web
