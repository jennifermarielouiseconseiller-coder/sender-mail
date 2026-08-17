# Bot Telegram — Envoi d'emails via SendGrid

Bot Telegram classique (mode polling) qui envoie des emails via SendGrid.

## Commandes
- `/start` — message de bienvenue
- `/help` — aide + affiche l'expéditeur configuré et votre ID
- `/whoami` — affiche votre ID Telegram
- `/email destinataire@mail.com | Sujet | Message` — envoie un email

## Configuration (`.env`)
- `TELEGRAM_BOT_TOKEN` — token du bot (@BotFather)
- `SENDGRID_API_KEY` — clé API SendGrid (permission *Mail Send* minimum)
- `SENDER_EMAIL` — adresse expéditeur **vérifiée** dans SendGrid
- `AUTHORIZED_USER_IDS` — IDs Telegram autorisés, séparés par des virgules

## Exécution
Le bot tourne via supervisor :
```
sudo supervisorctl restart telegram_bot
sudo supervisorctl status telegram_bot
tail -n 100 /var/log/supervisor/telegram_bot.*.log
```
