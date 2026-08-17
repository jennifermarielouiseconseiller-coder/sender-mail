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
- Envoi d'email via SendGrid (parsing `destinataire | sujet | message`, validation) ✅ (code)
- Gestion d'erreurs + retour de statut à l'utilisateur ✅

## Bloquants (dépendances externes, hors code)
- ⚠️ Clé SendGrid fournie renvoie `401 invalid/expired/revoked` (2 clés testées). Envoi d'email non testé de bout en bout.
- ⚠️ `SENDER_EMAIL` non fourni : SendGrid exige un expéditeur VÉRIFIÉ.

## Backlog / Next
- P0 : Clé SendGrid valide + email expéditeur vérifié → test d'envoi réel
- P1 : Historique des envois, templates d'email, pièces jointes
- P2 : Mode guidé étape par étape, tableau de bord web
