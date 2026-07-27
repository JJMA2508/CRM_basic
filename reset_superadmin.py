"""
Script de recuperación de acceso al Superadmin.
Ejecutar con: py -3 reset_superadmin.py
"""
from werkzeug.security import generate_password_hash
import sqlite3
import os

# ── Configuración ──────────────────────────────────────────────────────────
DB_PATH    = os.path.join(os.path.dirname(__file__), 'antojitos.db')
EMAIL      = 'super@saas.com'          # ← correo del superadmin
NUEVA_CLAVE = input('Escribe la nueva contraseña para el superadmin: ').strip()

if not NUEVA_CLAVE or len(NUEVA_CLAVE) < 6:
    print('❌ La contraseña debe tener al menos 6 caracteres.')
    exit(1)

# ── Actualizar en la base de datos ─────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

cur.execute('SELECT id, email FROM usuarios WHERE email = ?', (EMAIL,))
usuario = cur.fetchone()

if not usuario:
    print(f'❌ No se encontró ningún usuario con el correo: {EMAIL}')
    conn.close()
    exit(1)

nuevo_hash = generate_password_hash(NUEVA_CLAVE)
cur.execute('UPDATE usuarios SET password_hash = ? WHERE email = ?', (nuevo_hash, EMAIL))
conn.commit()
conn.close()

print(f'✅ Contraseña del superadmin ({EMAIL}) actualizada exitosamente.')
print('   Reinicia el servidor y usa la nueva clave para entrar.')
