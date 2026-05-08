@echo off
REM Iniciar Echoes - Script batch
REM Haz doble-clic para ejecutar el juego

echo Iniciando Echoes...
python Main.py

if errorlevel 1 (
    echo.
    echo Error al iniciar el juego. Presiona una tecla para cerrar.
    pause
)
