@echo off
REM Iniciar Echoes - CLIENTE
REM Haz doble-clic para conectarte al servidor multijugador

cd /d "%~dp0CODIGO"

echo Iniciando Echoes - CLIENTE (conectando a 127.0.0.1:5555)...
echo Asegúrate de que el servidor ya está corriendo...
echo.
python Main.py --client --host 127.0.0.1 --port 5555 --role ally

if errorlevel 1 (
    echo.
    echo Error al conectar al servidor. Presiona una tecla para cerrar.
    pause
)
