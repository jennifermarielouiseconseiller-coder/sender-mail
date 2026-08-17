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
- P2 : Tableau de bord web

## Itération 2 (2026-08-17)
- Assistant guidé pas à pas avec boutons (Compte → Nom → Destinataire → Sujet → Message → Aperçu → Envoyer) ✅
- Nom d'expéditeur personnalisable : défaut via `/nom` + modifiable à chaque envoi ✅
- Sélecteur multi-comptes/clés : Compte 1 (topwork.se) / Compte 2 (forssdigital.com), extensible jusqu'à 5 via `ACCOUNT_n_*` ✅ TESTÉ (envoi compte 2 + nom perso OK)
- Note : pas de « clé Resend Emergent » (n'existe pas) → Compte 2 utilise un 2e domaine vérifié de la même clé, remplaçable par une autre clé plus tard.
- Raccourci `/email dest | sujet | msg` conservé.

## Itération 4 (2026-08-17) — Support HTML + rebrand
- **Envoi HTML** : à l'étape « message » de `/email`, on peut désormais envoyer un **fichier `.html`** (≤ 2 Mo), **coller du code HTML**, ou taper du texte. Détection auto du HTML → email envoyé en `html` (sinon `text`). Aperçu indique le format. ✅ TESTÉ de bout en bout (envoi HTML réel via Resend, ID retourné).
- **Rebrand** : titre du bot renommé « **L3 SENDER** » (au lieu de « Bot d'envoi d'emails (Resend) »).
- **Correctif conflit d'instances** : après reset conteneur, `.env` + config supervisor + deps recréés. Config supervisor pointe sur `/root/.venv/bin/python`. Bot relancé en instance unique (résout le 409 Conflict Telegram).
- 8 expéditeurs actifs : topwork.se, forssdigital.com (clé re_9Ubt3F16) ; upterior.eu, upterior.nl, gr-imm.com (clé re_H4Z86RY3) ; deadhidden.org, thebiblicalmantruth.com (clé re_8RhZzASD) ; sanddollardesign.co.za (clé re_YCgXgWeL).

  - Clé topwork : topwork.se, forssdigital.com
  - Clé A : deadhidden.org, thebiblicalmantruth.com
  - Clé B : upterior.eu, upterior.nl, gr-imm.com (hout-shop.com ignoré = non vérifié)
- Limite de comptes portée à 20 (`ACCOUNT_1..20`).
