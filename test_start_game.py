"""
Test script para reproducir el bug de START_GAME en el cliente.
Simula:
1. Servidor se conecta al ClienteMenu
2. Servidor envía START_GAME al cliente después de unos segundos
3. Observamos cómo responde el cliente
"""

import json
import socket
import threading
import time
import sys

def simple_server(port=5555):
    """Servidor TCP que envía START_GAME después de 3 segundos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(1)

    print(f"[TEST SERVER] Esperando cliente en puerto {port}...")
    client_socket, addr = server_socket.accept()
    print(f"[TEST SERVER] Cliente conectado desde {addr}")

    # Recibir CLIENT_READY
    data = client_socket.recv(1024).decode()
    print(f"[TEST SERVER] Recibido: {data.strip()}")

    # Enviar MENU_STATE
    msg = {"type": "MENU_STATE", "pantalla": "principal"}
    client_socket.send(json.dumps(msg).encode() + b"\n")
    print(f"[TEST SERVER] Enviado: {msg}")

    # Esperar 3 segundos
    print("[TEST SERVER] Esperando 3 segundos...")
    time.sleep(3)

    # Enviar START_GAME
    msg = {"type": "START_GAME", "seed": 12345}
    client_socket.send(json.dumps(msg).encode() + b"\n")
    print(f"[TEST SERVER] ¡Enviado START_GAME!: {msg}")

    # Esperar a que el cliente responda
    time.sleep(5)

    client_socket.close()
    server_socket.close()
    print("[TEST SERVER] Servidor cerrado")

if __name__ == "__main__":
    # Lanzar servidor en background
    server_thread = threading.Thread(target=simple_server, daemon=True)
    server_thread.start()

    # Esperar a que servidor esté listo
    time.sleep(1)

    # Lanzar cliente
    print("\n[MAIN] Ejecutando cliente...")
    sys.argv = ["Main.py", "--client", "--host", "127.0.0.1", "--port", "5555", "--role", "victim"]

    # Importar y ejecutar el cliente
    from Main import _build_parser, _parse_room
    from Config import CFG
    from Game import Game

    parser = _build_parser()
    args = parser.parse_args()

    try:
        import pygame
        from ui.selector_modo import SelectorModo
        from network.servidor_menu import ServidorMenu
        from network.cliente_menu import ClienteMenu
        from dev.logger import log_game

        role_map = {"victim": "victima", "ally": "aliado"}
        role_normalizado = role_map.get(args.role, args.role)

        pygame.init()
        screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption("ECHOES — Test")

        # Cliente mode
        cliente_menu = ClienteMenu(ip_servidor="127.0.0.1")
        log_game.info(f"[TEST] Cliente conectando a 127.0.0.1:5555")

        # Esperar a que se conecte
        time.sleep(1)

        # Crear game
        game = Game(CFG, debug_mode=False, mode="offline", skip_intro=False)
        game._cliente_menu = cliente_menu

        # Correr el menú
        print("[MAIN] Corriendo game...")
        game.run()

    except Exception as e:
        print(f"[MAIN ERROR] {e}")
        import traceback
        traceback.print_exc()

    server_thread.join(timeout=10)
    print("[MAIN] Test completado")
