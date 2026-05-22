@echo off
REM Iniciar Echoes - SERVIDOR
REM Haz doble-clic para ejecutar el servidor multijugador

cd /d "%~dp0CODIGO"

echo Iniciando Echoes - SERVIDOR (puerto 5555)...
echo Espera a que el cliente se conecte...
echo.
python Main.py --server --port 5555

if errorlevel 1 (
    echo.
    echo Error al iniciar el servidor. Presiona una tecla para cerrar.
    pause
)
