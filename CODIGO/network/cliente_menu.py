"""
network/cliente_menu.py
=======================
Gestiona la conexión de red para el menú principal en modo CLIENTE.

El cliente recibe el estado del menú del servidor y lo renderiza.
No toma decisiones de navegación — solo escucha y actualiza el estado.

Protocolo (extends network.protocol con nuevos tipos de mensaje):
    MENU_STATE: Cambio de pantalla del menú
    LOBBY_STATE: Estado del lobby
    CONFIG_STATE: Configuración sincronizada
    START_GAME: Orden de iniciar el juego
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Any, Dict, Optional

import pygame

from dev.logger import log_net


class ClienteMenu:
    """
    Cliente de red que sincroniza el estado del menú principal.

    Se conecta a un servidor, recibe cambios de estado del menú,
    y actualiza su representación local (pantalla actual, volumen, etc.).

    El cliente NO procesa input de navegación del menú — solo ESC para cerrar.

    Atributos
    ---------
    conectado : bool
        True si hay conexión activa con el servidor.
    pantalla_actual : str
        Pantalla que debe renderizarse ("principal", "lobby", etc.)
    config : dict
        Configuración sincronizada (volumen, etc.)
    iniciar_juego : bool
        Flag que indica si el servidor ordenó iniciar el juego.
    seed_juego : int | None
        Seed que envió el servidor para el juego.
    """

    PUERTO = 5555

    def __init__(self, ip_servidor: str = "localhost"):
        self.ip_servidor = ip_servidor
        self.conectado = False
        self.sock: Optional[socket.socket] = None
        self.mensajes_recibidos: list[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.ejecutando = True

        # Estado del menú sincronizado desde servidor
        self.pantalla_actual = "conectando"
        self.config: Dict[str, Any] = {"volumen": 80}
        self.lobby_state: Dict[str, Any] = {}

        # Flag para iniciar el juego
        self.iniciar_juego = False
        self.seed_juego: Optional[int] = None

        self._conectar()

    def _conectar(self) -> None:
        """Intenta conectar al servidor en un hilo separado."""
        hilo = threading.Thread(
            target=self._hilo_conexion,
            daemon=True,
            name="echoes-menu-client-connect"
        )
        hilo.start()

    def _hilo_conexion(self) -> None:
        """Conexión en hilo separado para no bloquear la UI."""
        try:
            self.sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM
            )
            self.sock.connect((self.ip_servidor, self.PUERTO))
            self.conectado = True
            log_net.info(f"[CLIENTE MENU] Conectado a {self.ip_servidor}:{self.PUERTO}")

            # Notificar al servidor que estamos listos
            self.enviar({"type": "CLIENT_READY", "version": "1.0"})

            # Iniciar recepción
            self._recibir_mensajes()

        except Exception as e:
            log_net.error(f"[CLIENTE MENU] No se pudo conectar: {e}")
            self.conectado = False
            self.pantalla_actual = "sin_conexion"

    def _recibir_mensajes(self) -> None:
        """Recibe mensajes del servidor."""
        buffer = ""
        while self.ejecutando and self.conectado:
            try:
                data = self.sock.recv(4096).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    try:
                        msg = json.loads(linea)
                        with self.lock:
                            self.mensajes_recibidos.append(msg)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break
        self.conectado = False

    def procesar_mensajes_pendientes(self) -> None:
        """
        Procesa todos los mensajes recibidos del servidor.

        Debe llamarse desde el game loop principal (hilo principal)
        para evitar race conditions.
        """
        with self.lock:
            mensajes = self.mensajes_recibidos.copy()
            self.mensajes_recibidos.clear()

        for msg in mensajes:
            self._procesar_mensaje(msg)

    def _procesar_mensaje(self, msg: Dict[str, Any]) -> None:
        """Procesa un mensaje del servidor."""
        tipo = msg.get("type")

        if tipo == "MENU_STATE":
            with self.lock:
                self.pantalla_actual = msg.get("pantalla", "principal")
            log_net.info(f"[CLIENTE MENU] Pantalla: {self.pantalla_actual}")

        elif tipo == "LOBBY_STATE":
            with self.lock:
                self.lobby_state = msg

        elif tipo == "CONFIG_STATE":
            volumen = msg.get("volumen")
            if volumen is not None:
                with self.lock:
                    self.config["volumen"] = volumen
                # NO aplicar volumen desde hilo de red, solo setear flag
                # El volumen se aplicará desde el game loop principal
                log_net.info(f"[CLIENTE MENU] Volumen recibido: {volumen}")

        elif tipo == "START_GAME":
            try:
                seed = msg.get("seed", 0)
                print(f"[CLIENTE] Recibido START_GAME: seed={seed}")

                with self.lock:
                    self.iniciar_juego = True
                    self.seed_juego = seed

                print(f"[CLIENTE] Flags seteados, seed={self.seed_juego}")
                log_net.info(f"[CLIENTE MENU] Iniciando juego con seed {self.seed_juego}")

                # Enviar ACK inmediatamente al servidor
                ack = {"type": "ACK_START_GAME", "seed": seed}
                if self.enviar(ack):
                    print(f"[CLIENTE] ACK_START_GAME enviado al servidor")
                    log_net.info("[CLIENTE MENU] ACK_START_GAME enviado")
                else:
                    print(f"[CLIENTE] Error al enviar ACK_START_GAME")
                    log_net.warning("[CLIENTE MENU] Error al enviar ACK_START_GAME")

            except Exception as e:
                print(f"[CLIENTE ERROR] Al procesar START_GAME: {e}")
                import traceback
                traceback.print_exc()

    def enviar(self, msg: Dict[str, Any]) -> bool:
        """
        Envía un mensaje al servidor (thread-safe).

        Retorna True si se envió exitosamente.
        """
        if not self.conectado or not self.sock:
            return False
        try:
            data = json.dumps(msg) + "\n"
            self.sock.send(data.encode())
            return True
        except Exception as e:
            log_net.error(f"[CLIENTE MENU] Error al enviar: {e}")
            return False

    def cerrar(self) -> None:
        """Cierra la conexión con el servidor."""
        self.ejecutando = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        log_net.info("[CLIENTE MENU] Cliente cerrado")
