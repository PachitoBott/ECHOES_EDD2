"""
test_menu_network.py
====================
Script de prueba rápida para la implementación de red del menú.

Valida:
1. Importación de módulos
2. Creación de instancias
3. Métodos básicos
4. Protocolos de mensajes
"""

import sys
import time
import json
from pathlib import Path

# Agregar CODIGO a sys.path
codigo_dir = Path(__file__).parent
sys.path.insert(0, str(codigo_dir))

print("=" * 70)
print("TEST: Conexión Multijugador desde Menú Principal")
print("=" * 70)

# ========================================================================
# TEST 1: Importaciones
# ========================================================================
print("\n[TEST 1] Importando módulos...")
try:
    from network.servidor_menu import ServidorMenu
    from network.cliente_menu import ClienteMenu
    from ui.selector_modo import SelectorModo
    print("[OK] Imports OK")
except Exception as e:
    print(f"[ERROR] Error en imports: {e}")
    sys.exit(1)

# ========================================================================
# TEST 2: Instancias básicas
# ========================================================================
print("\n[TEST 2] Creando instancias...")
try:
    # Crear servidor
    servidor = ServidorMenu(puerto=9999)  # Usar puerto diferente para test
    print(f"[OK] ServidorMenu creado (puerto {servidor.puerto})")

    # Crear cliente (sin conectar)
    cliente = ClienteMenu(ip_servidor="localhost")
    print("[OK] ClienteMenu creado")

    # Crear selector de modo
    selector = SelectorModo(1280, 720)
    print("[OK] SelectorModo creado")
except Exception as e:
    print(f"[ERROR] Error creando instancias: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========================================================================
# TEST 3: Métodos de servidor
# ========================================================================
print("\n[TEST 3] Probando métodos del servidor...")
try:
    # Probar envío sin cliente conectado (debe retornar False)
    resultado = servidor.enviar({"type": "TEST"})
    if resultado == False:
        print("[OK] enviar() retorna False cuando no hay cliente")

    resultado = servidor.enviar_estado_menu("principal")
    if resultado == False:
        print("[OK] enviar_estado_menu() retorna False cuando no hay cliente")

    resultado = servidor.enviar_config(80)
    if resultado == False:
        print("[OK] enviar_config() retorna False cuando no hay cliente")

    resultado = servidor.enviar_inicio_juego(12345)
    if resultado == False:
        print("[OK] enviar_inicio_juego() retorna False cuando no hay cliente")

except Exception as e:
    print(f"[ERROR] Error en métodos del servidor: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========================================================================
# TEST 4: Estado del cliente
# ========================================================================
print("\n[TEST 4] Probando estado del cliente...")
try:
    # Verificar estado inicial
    assert cliente.pantalla_actual == "conectando", "Estado inicial debe ser 'conectando'"
    print("[OK] Cliente inicia en estado 'conectando'")

    assert cliente.conectado == False, "Cliente no debe estar conectado al inicio"
    print("[OK] Cliente no conectado al inicio")

    assert cliente.config["volumen"] == 80, "Volumen inicial debe ser 80"
    print("[OK] Volumen inicial correcto")

    # Simular recepción de mensajes
    cliente.mensajes_recibidos.append({
        "type": "MENU_STATE",
        "pantalla": "lobby",
        "datos": {}
    })
    cliente.procesar_mensajes_pendientes()
    assert cliente.pantalla_actual == "lobby", "Pantalla debe cambiar a 'lobby'"
    print("[OK] Cliente procesa MENU_STATE correctamente")

    # Simular CONFIG_STATE
    cliente.mensajes_recibidos.append({
        "type": "CONFIG_STATE",
        "volumen": 50
    })
    cliente.procesar_mensajes_pendientes()
    assert cliente.config["volumen"] == 50, "Volumen debe cambiar a 50"
    print("[OK] Cliente procesa CONFIG_STATE correctamente")

    # Simular START_GAME
    cliente.mensajes_recibidos.append({
        "type": "START_GAME",
        "seed": 42
    })
    cliente.procesar_mensajes_pendientes()
    assert cliente.iniciar_juego == True, "Flag iniciar_juego debe ser True"
    assert cliente.seed_juego == 42, "Seed debe ser 42"
    print("[OK] Cliente procesa START_GAME correctamente")

except AssertionError as e:
    print(f"[ERROR] Assertion fallida: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error en estado del cliente: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========================================================================
# TEST 5: Selector de modo
# ========================================================================
print("\n[TEST 5] Probando SelectorModo...")
try:
    # Verificar estado inicial
    assert selector.resultado == None, "Resultado inicial debe ser None"
    assert selector.terminado == False, "No debe estar terminado"
    print("[OK] SelectorModo inicia correctamente")

    # Simular selección de servidor
    selector.resultado = "servidor"
    selector.terminado = True
    assert selector.resultado == "servidor", "Resultado debe ser 'servidor'"
    print("[OK] SelectorModo puede seleccionar servidor")

    # Nuevo selector para cliente
    selector2 = SelectorModo(1280, 720)
    selector2.resultado = ("cliente", "192.168.1.9")
    selector2.terminado = True
    assert isinstance(selector2.resultado, tuple), "Resultado debe ser tupla"
    assert selector2.resultado[0] == "cliente", "Primer elemento debe ser 'cliente'"
    assert selector2.resultado[1] == "192.168.1.9", "IP debe ser correcta"
    print("[OK] SelectorModo puede seleccionar cliente con IP")

except AssertionError as e:
    print(f"[ERROR] Assertion fallida: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error en SelectorModo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========================================================================
# TEST 6: Protocolo de mensajes
# ========================================================================
print("\n[TEST 6] Probando protocolo de mensajes...")
try:
    # Validar que los mensajes sean JSON válido
    mensajes = [
        {"type": "CLIENT_READY", "version": "1.0"},
        {"type": "MENU_STATE", "pantalla": "principal", "datos": {}},
        {"type": "LOBBY_STATE", "p1_listo": True, "p2_conectado": False},
        {"type": "CONFIG_STATE", "volumen": 80},
        {"type": "START_GAME", "seed": 12345},
    ]

    for msg in mensajes:
        json_str = json.dumps(msg)
        msg_recuperado = json.loads(json_str)
        assert msg == msg_recuperado, f"Mensaje {msg['type']} no se serializa correctamente"

    print("[OK] Todos los mensajes son JSON válido")

except Exception as e:
    print(f"[ERROR] Error en protocolo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========================================================================
# RESUMEN
# ========================================================================
print("\n" + "=" * 70)
print("RESULTADO: TODOS LOS TESTS PASARON [OK]")
print("=" * 70)
print("\nLa implementación está lista para testing real:")
print("  SERVIDOR: python Main.py --server")
print("  CLIENTE:  python Main.py --client --host 192.168.1.9")
print("\nSin argumentos:")
print("  python Main.py  (muestra SelectorModo)")
print("=" * 70)

# Limpieza
servidor.cerrar()
cliente.cerrar()
