#!/usr/bin/env python3
"""
Script de test para reproducir y diagnosticar el bug de enemigos muriendo al atacar.

Pasos:
1. Ejecutar este script como SERVIDOR: python test_enemy_bug.py --server
2. En otra terminal, conectar como CLIENTE: python test_enemy_bug.py --client

El servidor generará logs que mostrarán:
- [ESTADO_REMOTO_NUEVA] con la posición del cliente
- [TARGETING] mostrando a qué apuntan los enemigos
- [DAMAGE] mostrando cuándo los enemigos reciben daño
- [DEATH] mostrando cuándo los enemigos mueren
"""

import sys
import argparse
from CODIGO.Main import main

if __name__ == "__main__":
    # Pasar argumentos directamente al Main.py
    if len(sys.argv) > 1:
        print(f"Test de bug de enemigos. Argumentos: {sys.argv[1:]}")
    sys.argv = [sys.argv[0], "--skip-menu", "--debug"]  # Agregar flags por defecto
    main()
