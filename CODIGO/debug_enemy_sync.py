#!/usr/bin/env python3
"""
Debug: Verificar que los archivos tienen la sincronización de enemigos
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("="*70)
print("DEBUG: VERIFICAR SINCRONIZACIÓN DE ENEMIGOS")
print("="*70)

# Check 1: Protocol tiene msg_enemigo_muerto?
print("\n[1] Verificando protocol.py...")
try:
    with open("network/protocol.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "def msg_enemigo_muerto" in content:
            print("  OK - msg_enemigo_muerto() existe en protocol.py")
        else:
            print("  ERROR - msg_enemigo_muerto() NO ENCONTRADO en protocol.py")
            print("  SOLUCIÓN: Copiar protocol.py de Computadora 1")
except Exception as e:
    print(f"  ERROR leyendo protocol.py: {e}")

# Check 2: Game.py tiene _handle_remote_enemy_death?
print("\n[2] Verificando Game.py...")
try:
    with open("Game.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "def _handle_remote_enemy_death" in content:
            print("  OK - _handle_remote_enemy_death() existe en Game.py")
        else:
            print("  ERROR - _handle_remote_enemy_death() NO ENCONTRADO en Game.py")
            print("  SOLUCIÓN: Copiar Game.py de Computadora 1")
        
        if 'ev.tipo == "enemigo_muerto"' in content:
            print("  OK - Handler para 'enemigo_muerto' existe en Game.py")
        else:
            print("  ERROR - Handler para 'enemigo_muerto' NO ENCONTRADO")
            print("  SOLUCIÓN: Copiar Game.py de Computadora 1")
            
        if "self.net.enviar(event_msg)" in content:
            print("  OK - Envío de evento existe en _handle_collisions()")
        else:
            print("  ERROR - Envío de evento NO ENCONTRADO en _handle_collisions()")
            print("  SOLUCIÓN: Copiar Game.py de Computadora 1")
except Exception as e:
    print(f"  ERROR leyendo Game.py: {e}")

# Check 3: NetworkManager tiene enviar()?
print("\n[3] Verificando network/manager.py...")
try:
    with open("network/manager.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "def enviar(self, mensaje: Mensaje)" in content:
            print("  OK - enviar() método existe en NetworkManager")
        else:
            print("  ERROR - enviar() método NO ENCONTRADO en NetworkManager")
            print("  SOLUCIÓN: Copiar manager.py de Computadora 1")
except Exception as e:
    print(f"  ERROR leyendo manager.py: {e}")

print("\n" + "="*70)
print("RESUMEN:")
print("="*70)
print("""
Si ves algún ERROR arriba:

1. Los ARCHIVOS NO ESTÁN ACTUALIZADOS en esta computadora
2. Necesitas COPIAR estos archivos de Computadora 1:
   - CODIGO/network/protocol.py
   - CODIGO/Game.py
   - CODIGO/network/manager.py

3. DESPUÉS de copiar, vuelve a correr este script

Si TODO está OK:
   - Los archivos están bien
   - El problema está en el comportamiento del programa
   - Necesitamos ver los LOGS detallados del servidor
""")

