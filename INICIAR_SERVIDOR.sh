#!/bin/bash
# Iniciar Echoes - SERVIDOR (macOS/Linux)
# Haz: chmod +x INICIAR_SERVIDOR.sh
# Luego: ./INICIAR_SERVIDOR.sh

cd "$(dirname "$0")/CODIGO"

echo "Iniciando Echoes - SERVIDOR (puerto 5555)..."
echo "Espera a que el cliente se conecte..."
echo ""
python3 Main.py --server --port 5555

if [ $? -ne 0 ]; then
    echo ""
    echo "Error al iniciar el servidor. Presiona Ctrl+C para cerrar."
    read
fi
