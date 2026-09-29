# Fomo Backend — VPS Deployment

Deploy stack: Docker + docker compose (Postgres, Redis, web, celery) + Caddy
for automatic HTTPS. Works with free `*.sslip.io` domains — your
`fomoapi.<IP>.sslip.io` resolves automatically, no DNS setup needed.

## 1. Point a domain at the VPS

sslip.io resolves any `<name>.<IP-with-dashes>.sslip.io` to that IP:

    VPS IP:        102.68.4.9
    Domain:        fomoapi.102-68-4-9.sslip.io

## 2. On the VPS

```bash
# install docker + git + firewall
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
apt update && apt install -y git ufw
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

# clone
cd /opt && git clone https://github.com/raydanielg/Fomo-business.git fomo
cd fomo/backend
```

## 3. Production `.env`

```bash
cat > .env <<'ENV'
DEBUG=False
SECRET_KEY=PASTE_RANDOM_64_CHARS
DJANGO_SETTINGS_MODULE=config.settings.production

# replace 1-2-3-4 with your VPS IP in dash form
ALLOWED_HOSTS=fomoapi.1-2-3-4.sslip.io,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://fomoapi.1-2-3-4.sslip.io
CORS_ALLOWED_ORIGINS=https://fomoapi.1-2-3-4.sslip.io
FRONTEND_URL=https://fomoapi.1-2-3-4.sslip.io

DATABASE_URL=postgres://postgres:PASTE_DB_PASSWORD@db:5432/fomo
POSTGRES_PASSWORD=PASTE_DB_PASSWORD

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

JWT_SIGNING_KEY=PASTE_ANOTHER_RANDOM_64_CHARS

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SMS_PROVIDER=console
SECURE_SSL_REDIRECT=True

# Snippe — real values go ONLY here on the server, never in git
SNIPPE_API_KEY=snp_xxx_your_real_key
SNIPPE_WEBHOOK_SECRET=whsec_xxx_your_real_secret
SNIPPE_BASE_URL=https://api.snippe.sh
SNIPPE_API_VERSION=2026-01-25
SNIPPE_WEBHOOK_TOLERANCE=300
ENV

# generate the three secrets automatically:
sed -i "s/PASTE_RANDOM_64_CHARS/$(openssl rand -hex 32)/" .env
sed -i "s/PASTE_ANOTHER_RANDOM_64_CHARS/$(openssl rand -hex 32)/" .env
sed -i "s/PASTE_DB_PASSWORD/$(openssl rand -hex 16)/g" .env

# set your IP → domain (replace with real VPS IP):
VPS_IP=102.68.4.9
D=$(echo $VPS_IP | tr '.' '-')
sed -i "s/fomoapi\.1-2-3-4\.sslip\.io/fomoapi.${D}.sslip.io/g" .env
```

## 4. Caddy HTTPS gateway

```bash
cat > Caddyfile <<EOF
fomoapi.${D}.sslip.io {
    reverse_proxy web:8000
}
EOF

cat >> docker-compose.yml <<'EOF'

  caddy:
    image: caddy:2-alpine
    restart: always
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on: [web]
EOF
# keep gunicorn internal — Caddy is the only public gateway
sed -i 's/- "8000:8000"/- "127.0.0.1:8000:8000"/' docker-compose.yml
# append the caddy volume under volumes:
sed -i 's/^  postgres_data:/  postgres_data:\n  caddy_data:/' docker-compose.yml
```

## 5. Launch + verify

```bash
docker compose build && docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_help

curl https://fomoapi.${D}.sslip.io/health/
docker compose ps        # db, redis, web, celery, celery-beat, caddy
```

- API: `https://fomoapi.<IP>.sslip.io/api/v1/...`
- Admin: `https://fomoapi.<IP>.sslip.io/admin/`
- Snippe webhook URL to configure in the Snippe dashboard:
  `https://fomoapi.<IP>.sslip.io/api/v1/billing/webhooks/snippe/`
- Mobile app: set `baseUrl` in `api_client.dart` to
  `https://fomoapi.<IP>.sslip.io/api/v1`

## 6. Updates

```bash
cd /opt/fomo && git pull
docker compose build && docker compose up -d
docker compose exec web python manage.py migrate
```
