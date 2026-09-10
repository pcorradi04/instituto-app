"""
Archivo de configuración WSGI para PythonAnywhere.

NO se usa en tu máquina. En PythonAnywhere, pestaña "Web" → sección "Code"
→ link "WSGI configuration file": borrá todo lo que hay ahí y pegá este
archivo entero, reemplazando USUARIO por tu nombre de usuario de
PythonAnywhere. Ver DEPLOY.md para el paso a paso completo.
"""
import os
import sys

# Carpeta donde quedó el repo después del `git clone`.
project_home = "/home/USUARIO/instituto-app"

if project_home not in sys.path:
    sys.path.insert(0, project_home)
os.chdir(project_home)

# app.py lee solo el archivo .env que esté en su misma carpeta
# (ADMIN_PASSWORD, SECRET_KEY, SECURE_COOKIES...), no hace falta cargarlo acá.
from app import app as application  # noqa: E402,F401
