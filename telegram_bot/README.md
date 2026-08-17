# Bot Telegram — Envoi d'emails via Resend

Bot Telegram classique (polling) avec assistant guidé, choix du compte d'envoi et nom d'expéditeur personnalisable.

## Commandes
- `/start` — accueil
- `/email` — assistant guidé pas à pas (Compte → Nom → Destinataire → Sujet → Message → Aperçu → ✅ Envoyer)
- `/nom VotreNom` — définit le nom d'expéditeur par défaut
- `/comptes` — liste les comptes d'envoi
- `/whoami` — votre ID Telegram
- `/help` — aide
- `/annuler` — annule l'assistant en cours

Raccourci rapide : `/email dest@mail.com | Sujet | Message` (envoi direct via Compte 1).

## Nom d'expéditeur & délivrabilité
- Le **nom** affiché est 100% libre (ex: « Faracosta ») et n'affecte pas la délivrabilité.
- La **délivrabilité** dépend du domaine de l'adresse : il doit être vérifié dans Resend (SPF/DKIM). Ici `topwork.se` et `forssdigital.com` sont vérifiés.

## Comptes (`.env`)
Chaque compte = un trio `ACCOUNT_n_KEY` / `ACCOUNT_n_SENDER` / `ACCOUNT_n_LABEL` (n de 1 à 5).
- Compte 1 : clé utilisateur → `noreply@topwork.se`
- Compte 2 : clé utilisateur → `noreply@forssdigital.com`

Pour utiliser une **autre clé Resend** en Compte 2, remplacez `ACCOUNT_2_KEY` par la nouvelle clé et `ACCOUNT_2_SENDER` par une adresse de son domaine vérifié, puis `sudo supervisorctl restart telegram_bot`.

## Config également
- `TELEGRAM_BOT_TOKEN`, `AUTHORIZED_USER_IDS` (IDs autorisés séparés par des virgules)
- `config.json` : stocke le nom d'expéditeur par défaut (créé par `/nom`)

## Exécution
```
sudo supervisorctl restart telegram_bot
tail -n 100 /var/log/supervisor/telegram_bot.*.log
```
