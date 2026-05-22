#!/bin/bash
# Iniciar Echoes - CLIENTE (macOS)
# Doble-click para ejecutar
# NOTA: Cambia 127.0.0.1 por la IP del servidor si está en otra máquina

cd "$(dirname "$0")/CODIGO"

echo "Iniciando Echoes - CLIENTE (conectando a 127.0.0.1:5555)..."
echo "Asegúrate de que el servidor ya está corriendo..."
echo ""
python3 Main.py --client --host 127.0.0.1 --port 5555 --role ally

echo ""
echo "Presiona ENTER para cerrar..."
read
