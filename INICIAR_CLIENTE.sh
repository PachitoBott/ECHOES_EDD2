#!/bin/bash
# Iniciar Echoes - CLIENTE (macOS/Linux)
# Haz: chmod +x INICIAR_CLIENTE.sh
# Luego: ./INICIAR_CLIENTE.sh

cd "$(dirname "$0")/CODIGO"

echo "Iniciando Echoes - CLIENTE (conectando a 127.0.0.1:5555)..."
echo "Asegúrate de que el servidor ya está corriendo..."
echo ""
python3 Main.py --client --host 127.0.0.1 --port 5555 --role ally

if [ $? -ne 0 ]; then
    echo ""
    echo "Error al conectar al servidor. Presiona Ctrl+C para cerrar."
    read
fi
