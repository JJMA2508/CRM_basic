"""
Archivo WSGI para PythonAnywhere.
INSTRUCCIONES:
  1. Copia este contenido en el archivo WSGI de PythonAnywhere
     (pestaña Web → sección Code → clic en el archivo wsgi.py)
  2. Cambia TU_USUARIO por tu username real de PythonAnywhere
  3. Clic en Save
  4. Clic en Reload (botón verde)
"""
import sys
import os

# ── Cambia TU_USUARIO por tu username de PythonAnywhere ──────────────────────
USUARIO = 'TU_USUARIO'
# ─────────────────────────────────────────────────────────────────────────────

path = f'/home/{USUARIO}/antojitos_crm'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from app import create_app
application = create_app()
