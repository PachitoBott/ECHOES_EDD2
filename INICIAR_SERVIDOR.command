#!/bin/bash
# Iniciar Echoes - SERVIDOR (macOS)
# Doble-click para ejecutar

cd "$(dirname "$0")/CODIGO"

echo "Iniciando Echoes - SERVIDOR (puerto 5555)..."
echo "Espera a que el cliente se conecte..."
echo ""
python3 Main.py --server --port 5555

echo ""
echo "Presiona ENTER para cerrar..."
read
