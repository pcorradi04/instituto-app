#!/usr/bin/env bash
# Copia de resguardo de TODO el contenido del blog (base de datos + imágenes)
# en ~/backups-blog/blog-AAAA-MM-DD.tar.gz, conservando las últimas 30.
# Para que corra solo todas las noches (3:15), una vez:
#
#     (crontab -l 2>/dev/null; echo "15 3 * * * bash $HOME/instituto-app/deploy/backup.sh") | crontab -
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/backups-blog"
mkdir -p "$DEST"
# La base se copia con el comando .backup de sqlite (copia consistente aunque
# alguien esté guardando en ese momento); las imágenes, tal cual.
TMP="$(mktemp -d)"
"$DIR/venv/bin/python" - "$DIR/instance/instituto.db" "$TMP/instituto.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
PY
cp -r "$DIR/instance/uploads" "$TMP/uploads" 2>/dev/null || mkdir -p "$TMP/uploads"
tar -czf "$DEST/blog-$(date +%F).tar.gz" -C "$TMP" .
rm -rf "$TMP"
ls -1t "$DEST"/blog-*.tar.gz | tail -n +31 | xargs -r rm -f
echo "Backup: $DEST/blog-$(date +%F).tar.gz"
