import subprocess
import sys
import os

print("[SaaS] Iniciando proceso de empaquetado del CRM Multi-Comercio...")

# Asegurar PyInstaller instalado
try:
    import PyInstaller
    print("[OK] PyInstaller ya esta instalado.")
except ImportError:
    print("[SETUP] PyInstaller no esta instalado. Instalando con pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller instalado correctamente.")
    except Exception as e:
        print(f"[ERROR] Al instalar PyInstaller: {e}")
        sys.exit(1)

# Comando de PyInstaller
cmd = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--name=CRM_MultiComercio",
    "--onedir",
    "--console",
    "--add-data", "templates;templates",
    "--add-data", "static;static",
    "app.py"
]

print("[RUN] Ejecutando PyInstaller (esto puede tardar unos minutos)...")
try:
    subprocess.check_call(cmd)
    print("\n[SUCCESS] Compilacion finalizada con exito!")
    print("[PATH] El ejecutable principal se encuentra en: dist/CRM_MultiComercio/CRM_MultiComercio.exe")
    print("[INFO] Asegurate de que antojitos.db se encuentra en el mismo directorio si quieres preservar datos existentes.")
except subprocess.CalledProcessError as e:
    print(f"\n[ERROR] Durante la compilacion de PyInstaller: {e}")
    sys.exit(1)
