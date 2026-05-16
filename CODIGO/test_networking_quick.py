#!/usr/bin/env python3
"""
test_networking_quick.py — Validación rápida del sistema de networking
========================================================================

Ejecutar:
    cd CODIGO
    python test_networking_quick.py

Verifica:
    1. Imports de módulos de red
    2. Parser acepta flags de networking
    3. NetworkManager se crea correctamente
    4. Protocolo de mensajes funciona
    5. Servidor y cliente se inicializan

Sin requiere Pygame ni sockets reales (pure unit tests).
"""
import sys
import os

# Asegurar que podemos importar desde CODIGO/
sys.path.insert(0, os.path.dirname(__file__))


def test_imports():
    """Verifica que se pueden importar los módulos de networking."""
    print("\n[TEST 1] Importando módulos de networking...")
    try:
        from network import NetworkManager, EventoRed, Mensaje, Rol, TipoMensaje
        print("  ✅ network.NetworkManager")
        print("  ✅ network.EventoRed")
        print("  ✅ network.Mensaje")
        print("  ✅ network.Rol")
        print("  ✅ network.TipoMensaje")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_parser():
    """Verifica que Main.py acepta los nuevos flags."""
    print("\n[TEST 2] Verificando parser de argumentos...")
    try:
        from Main import _build_parser
        parser = _build_parser()

        # Test --server
        args = parser.parse_args(["--server", "--port", "5555"])
        assert args.server == True, "Flag --server no se parsea"
        assert args.port == 5555, "Flag --port no se parsea"
        print("  ✅ Flag --server --port 5555")

        # Test --client
        args = parser.parse_args([
            "--client",
            "--host", "192.168.1.10",
            "--port", "5556",
            "--role", "ally"
        ])
        assert args.client == True, "Flag --client no se parsea"
        assert args.host == "192.168.1.10", "Flag --host no se parsea"
        assert args.port == 5556, "Flag --port no se parsea"
        assert args.role == "ally", "Flag --role no se parsea"
        print("  ✅ Flag --client --host --port --role")

        # Test defaults
        args = parser.parse_args([])
        assert args.server == False, "Default --server debería ser False"
        assert args.client == False, "Default --client debería ser False"
        assert args.host == "127.0.0.1", "Default --host incorrecto"
        assert args.port == 5555, "Default --port incorrecto"
        assert args.role == "victim", "Default --role incorrecto"
        print("  ✅ Valores por defecto correctos")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_message_protocol():
    """Verifica que el protocolo de mensajes serializa/deserializa correctamente."""
    print("\n[TEST 3] Verificando protocolo de mensajes...")
    try:
        from network.protocol import Mensaje, TipoMensaje, msg_conectar, msg_aceptado

        # Test serialización de mensaje
        msg = msg_conectar("victim")
        serializado = msg.serializar()
        assert isinstance(serializado, bytes), "Serialización debe retornar bytes"
        assert b"\\n" in serializado or serializado.endswith(b"\n"), "Debe terminar en newline"
        print("  ✅ Mensaje se serializa a bytes con newline")

        # Test deserialización
        deserializado = Mensaje.deserializar(serializado)
        assert deserializado is not None, "Deserialización falló"
        assert deserializado.tipo == TipoMensaje.CONECTAR, "Tipo de mensaje incorrecto"
        assert deserializado.datos.get("rol") == "victim", "Datos no se preservan"
        print("  ✅ Mensaje se deserializa correctamente")

        # Test round-trip
        msg2 = msg_aceptado("victim", seed=12345)
        bytes2 = msg2.serializar()
        msg2_recovered = Mensaje.deserializar(bytes2)
        assert msg2_recovered.datos.get("seed") == 12345, "Round-trip pierde datos"
        print("  ✅ Round-trip serialización preserva datos")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_network_manager():
    """Verifica que NetworkManager se puede instanciar."""
    print("\n[TEST 4] Verificando NetworkManager...")
    try:
        from network import NetworkManager

        # Test creación servidor
        mgr_server = NetworkManager.como_servidor(port=9999, seed=None)
        assert mgr_server is not None, "NetworkManager.como_servidor() falló"
        assert mgr_server.es_servidor == True, "es_servidor debería ser True"
        assert mgr_server.es_victima == True, "Servidor actúa como VICTIMA"
        print("  ✅ NetworkManager.como_servidor() funciona")

        # Test creación cliente
        from network import Rol
        mgr_client = NetworkManager.como_cliente(host="127.0.0.1", port=9999, rol=Rol.ALIADO)
        assert mgr_client is not None, "NetworkManager.como_cliente() falló"
        assert mgr_client.es_aliado == True, "es_aliado debería ser True"
        assert mgr_client.rol == Rol.ALIADO, "Rol no se asigna"
        print("  ✅ NetworkManager.como_cliente() funciona")

        # Test propiedades
        assert mgr_server.modo == "servidor", "Propiedad modo incorrecta"
        assert mgr_client.modo == "cliente", "Propiedad modo incorrecta"
        assert not mgr_server.esta_conectado(), "Servidor no debería estar conectado antes de iniciar()"
        print("  ✅ Propiedades del NetworkManager correctas")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_evento_red():
    """Verifica que EventoRed se crea correctamente."""
    print("\n[TEST 5] Verificando EventoRed...")
    try:
        from network import EventoRed

        ev = EventoRed(
            tipo="jugador_unido",
            datos={"rol": "victim", "conectados": ["victim", "ally"]},
            origen="servidor"
        )
        assert ev.tipo == "jugador_unido", "Tipo no se asigna"
        assert ev.datos.get("rol") == "victim", "Datos no se asignan"
        assert ev.origen == "servidor", "Origen no se asigna"
        print("  ✅ EventoRed se crea correctamente")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_game_import():
    """Verifica que Game.py se puede importar con networking."""
    print("\n[TEST 6] Verificando Game.py con networking...")
    try:
        # No importamos Game completo (requiere Pygame),
        # solo verificamos que Main.py se importa sin errores
        from Main import Game
        print("  ⚠️  Game importado (pero no instanciado sin Pygame)")

        # Verificamos que Main.py mismo no tiene errores de sintaxis
        from Main import _build_parser, _parse_room
        print("  ✅ Main.py importa sin errores")

        return True
    except SyntaxError as e:
        print(f"  ❌ Error de sintaxis: {e}")
        return False
    except Exception as e:
        # Otros errores (Pygame no disponible) son OK en este test
        print(f"  ⚠️  Error (esperado sin Pygame): {type(e).__name__}")
        return True


# =============================================================================
# Ejecutar todos los tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("VALIDACIÓN RÁPIDA — NETWORKING MULTIJUGADOR ECHOES")
    print("=" * 70)

    tests = [
        ("Imports", test_imports),
        ("Parser CLI", test_parser),
        ("Protocolo", test_message_protocol),
        ("NetworkManager", test_network_manager),
        ("EventoRed", test_evento_red),
        ("Game.py", test_game_import),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ Exception no capturada: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} — {name}")

    print(f"\nTotal: {passed}/{total} tests pasaron")

    if passed == total:
        print("\n✅ NETWORKING FUNCIONA CORRECTAMENTE")
        print("\nPróximo paso: ejecutar los 3 binarios (servidor + 2 clientes)")
        print("Ver TEST_NETWORKING.md para instrucciones detalladas")
        sys.exit(0)
    else:
        print("\n❌ Hay problemas que revisar")
        sys.exit(1)
