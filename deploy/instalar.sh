#!/usr/bin/env bash
# Instala el blog en un servidor Ubuntu 22.04 / 24.04 propio (ej. el cloud
# server de DonWeb) y lo deja publicado con HTTPS en un dominio.
#
# Se corre UNA vez, como el usuario normal (no root), que tenga sudo:
#
#     bash instalar.sh blog.ieaustral.com correo@ejemplo.com
#
# Qué hace, en orden (se puede volver a correr: no rompe lo que ya está):
#   1. instala Python, git, Nginx y certbot (Let's Encrypt);
#   2. clona (o actualiza) el repo en ~/instituto-app y crea el venv;
#   3. crea el .env si no existe (genera la SECRET_KEY, pide la clave del panel);
#   4. deja un servicio de systemd (instituto-blog) que corre gunicorn en el
#      puerto local 8001 y lo relanza solo si se cae o se reinicia el server;
#   5. configura Nginx para pasar el dominio a ese puerto y saca el
#      certificado HTTPS con renovación automática.
# Los datos (instance/instituto.db + instance/uploads/) NO los toca: se
# copian aparte, ver DEPLOY.md sección 9.
set -euo pipefail

DOMINIO="${1:-}"
CORREO="${2:-}"
REPO="https://github.com/pcorradi04/instituto-app.git"
DIR="$HOME/instituto-app"
SERVICIO="instituto-blog"
PUERTO=8001

if [[ -z "$DOMINIO" || -z "$CORREO" ]]; then
  echo "Uso: bash instalar.sh <dominio> <correo para Let's Encrypt>"
  echo "Ej.: bash instalar.sh blog.ieaustral.com pcorradi04@gmail.com"
  exit 1
fi
if [[ "$(id -u)" -eq 0 ]]; then
  echo "Corré este script como tu usuario normal (con sudo disponible), no como root."
  exit 1
fi

echo "== 1/5 Paquetes del sistema"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx

echo "== 2/5 Código y entorno de Python"
if [[ -d "$DIR/.git" ]]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"
[[ -d venv ]] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
mkdir -p instance/uploads

echo "== 3/5 Configuración (.env)"
if [[ -f .env ]]; then
  echo "   .env ya existe: se deja como está."
else
  read -r -s -p "   Clave para entrar al panel de administración: " CLAVE; echo
  SECRET="$(venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
  cat > .env <<EOF
# Generado por deploy/instalar.sh el $(date +%F). Ver .env.example para las demás opciones.
ADMIN_PASSWORD=$CLAVE
SECRET_KEY=$SECRET
SECURE_COOKIES=1
BEHIND_PROXY=1
SITE_URL=https://$DOMINIO
EOF
  chmod 600 .env
  echo "   .env creado."
fi

echo "== 4/5 Servicio $SERVICIO (gunicorn en 127.0.0.1:$PUERTO)"
sudo tee /etc/systemd/system/$SERVICIO.service >/dev/null <<EOF
[Unit]
Description=Blog del Instituto de Energía (Flask + gunicorn)
After=network.target

[Service]
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/gunicorn app:app --bind 127.0.0.1:$PUERTO --workers 2 --timeout 60
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now $SERVICIO
sudo systemctl restart $SERVICIO
sleep 2
if curl -fsS -o /dev/null http://127.0.0.1:$PUERTO/; then
  echo "   La app responde en el puerto $PUERTO."
else
  echo "   La app NO responde. Mirá el error con: sudo journalctl -u $SERVICIO -n 50"
  exit 1
fi

echo "== 5/5 Nginx + HTTPS para $DOMINIO"
sudo tee /etc/nginx/sites-available/$SERVICIO >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMINIO;
    client_max_body_size 12m;   # imágenes de hasta 10 MB

    location / {
        proxy_pass         http://127.0.0.1:$PUERTO;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_set_header   X-Forwarded-Host  \$host;
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/$SERVICIO /etc/nginx/sites-enabled/$SERVICIO
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
# certbot agrega el bloque HTTPS a la config de arriba y la redirección de http a https.
sudo certbot --nginx -d "$DOMINIO" -m "$CORREO" --agree-tos --no-eff-email --redirect --non-interactive || {
  echo "   certbot falló. Suele ser porque el dominio todavía no apunta a este servidor o el puerto 80 está cerrado."
  echo "   El sitio queda andando por http://$DOMINIO ; cuando se resuelva, repetí: sudo certbot --nginx -d $DOMINIO"
  exit 1
}

echo
echo "Listo: https://$DOMINIO  (panel: https://$DOMINIO/admin/)"
echo "Datos: copiá instance/instituto.db y instance/uploads/ desde PythonAnywhere a $DIR/instance/ y reiniciá con:"
echo "    sudo systemctl restart $SERVICIO"
echo "Actualizar más adelante:  bash $DIR/deploy/actualizar.sh"
