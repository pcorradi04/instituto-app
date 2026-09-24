#!/usr/bin/env bash
# Trae la última versión del blog desde GitHub y reinicia el servicio.
# Reemplaza al "git pull + Reload" de PythonAnywhere. Se corre en el
# servidor, como el usuario que instaló:
#
#     bash ~/instituto-app/deploy/actualizar.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"
echo "== Código"
git pull --ff-only
echo "== Dependencias"
venv/bin/pip install -q -r requirements.txt
echo "== Reinicio del servicio"
sudo systemctl restart instituto-blog
sleep 2
if curl -fsS -o /dev/null http://127.0.0.1:8001/; then
  echo "OK: la app responde. Versión: $(git log -1 --format='%h %s')"
else
  echo "La app NO responde. Mirá el error con: sudo journalctl -u instituto-blog -n 50"
  exit 1
fi
