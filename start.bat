@echo off
title Antojitos y Mas - CRM
color 0D
echo.
echo  =====================================================
echo   Heladeria Antojitos y Mas ^| Sistema CRM
echo  =====================================================
echo.

cd /d "%~dp0"

REM Verificar si existe la carpeta compilada de PyInstaller
if exist "dist\CRM_MultiComercio\CRM_MultiComercio.exe" (
    echo  [SaaS] Iniciando version empaquetada (.exe) de CRM Multi-Comercio...
    echo  -------------------------------------------------------
    echo  Acceso LOCAL:  http://localhost:5000
    echo  -------------------------------------------------------
    start http://localhost:5000
    start "" "dist\CRM_MultiComercio\CRM_MultiComercio.exe"
    exit /b 0
)

REM Si no está empaquetada, correr en modo desarrollo con Python
REM Verificar si Python existe
python --version >nul 2>&1
if errorlevel 1 (
    py -3 --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] Python no encontrado en el sistema.
        echo  Por favor instala Python 3.8+ o ejecuta la version compilada en dist/.
        pause
        exit /b 1
    )
)

REM Instalar dependencias si faltan
echo  Verificando dependencias en modo desarrollo...
py -3 -m pip install -r requirements.txt --quiet

echo.
echo  Iniciando servidor en modo desarrollo...
echo  -------------------------------------------------------
echo  Acceso LOCAL:  http://localhost:5000
echo  -------------------------------------------------------
echo  Para cerrar el servidor presiona: Ctrl + C
echo.

start http://localhost:5000
py -3 app.py

pause
