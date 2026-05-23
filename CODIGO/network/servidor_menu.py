"""
network/servidor_menu.py
========================
Gestiona la conexión de red para el menú principal en modo SERVIDOR.

El servidor envía su estado del menú al cliente cada vez que cambia algo
(navegación, volumen, etc.). El cliente solo recibe y renderiza.

Protocolo (extends network.protocol con nuevos tipos de mensaje):
    MENU_STATE: Cambio de pantalla del menú
    LOBBY_STATE: Estado del lobby (P2 conectado, etc.)
    CONFIG_STATE: Configuración sincronizada (volumen, etc.)
    START_GAME: Orden de iniciar el juego
"""
from __future__ import annotations

import json
import socket
import threading
import time
from typing import Optional

from dev.logger import log_net


class ServidorMenu:
    """
    Servidor de red que sincroniza el estado del menú principal.

    El servidor escucha en un puerto TCP, acepta UN cliente, y envía
    cambios de estado del menú conforme el usuario navega.

    Atributos
    ---------
    cliente_socket : socket.socket | None
        Socket conectado del cliente.
    cliente_conectado : bool
        True si hay cliente conectado en este momento.
    puerto : int
        Puerto TCP donde escucha.
    """

    PUERTO = 5555

    def __init__(self, puerto: int = PUERTO):
        self.puerto = puerto
        self.cliente_socket: Optional[socket.socket] = None
        self.cliente_conectado = False
        self.server_socket: Optional[socket.socket] = None
        self.ejecutando = True
        self._hilo_espera: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._iniciar_escucha()

    def _iniciar_escucha(self) -> None:
        """Inicia el servidor en un hilo separado."""
        self._hilo_espera = threading.Thread(
            target=self._esperar_cliente,
            daemon=True,
            name="echoes-menu-server-accept"
        )
        self._hilo_espera.start()
        log_net.info(f"[SERVIDOR MENU] Esperando cliente en puerto {self.puerto}...")

    def _esperar_cliente(self) -> None:
        """Espera conexión del cliente en hilo separado."""
        try:
            self.server_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM
            )
            self.server_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1
            )
            self.server_socket.bind(("0.0.0.0", self.puerto))
            self.server_socket.listen(1)

            conn, addr = self.server_socket.accept()
            with self._lock:
                self.cliente_socket = conn
                self.cliente_conectado = True
            log_net.info(f"[SERVIDOR MENU] Cliente conectado desde {addr}")

            # Iniciar recepción de mensajes del cliente
            threading.Thread(
                target=self._recibir_del_cliente,
                daemon=True,
                name="echoes-menu-server-recv"
            ).start()

        except Exception as e:
            if self.ejecutando:
                log_net.error(f"[SERVIDOR MENU] Error: {e}")

    def _recibir_del_cliente(self) -> None:
        """Recibe mensajes del cliente en hilo separado."""
        buffer = ""
        while self.ejecutando and self.cliente_conectado:
            try:
                data = self.cliente_socket.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    try:
                        msg = json.loads(linea)
                        self._procesar_mensaje_cliente(msg)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break
        with self._lock:
            self.cliente_conectado = False
        log_net.info("[SERVIDOR MENU] Cliente desconectado")

    def _procesar_mensaje_cliente(self, msg: dict) -> None:
        """Procesa mensajes recibidos del cliente."""
        tipo = msg.get("type")
        if tipo == "CLIENT_READY":
            log_net.info("[SERVIDOR MENU] Cliente listo")
            # Enviar estado actual del menú al cliente
            self.enviar_estado_menu("principal")

    def enviar(self, msg: dict) -> bool:
        """
        Envía un mensaje al cliente (thread-safe).

        Retorna True si se envió exitosamente.
        """
        with self._lock:
            if not self.cliente_conectado or not self.cliente_socket:
                return False
            try:
                data = json.dumps(msg) + "\n"
                self.cliente_socket.send(data.encode())
                return True
            except Exception as e:
                log_net.error(f"[SERVIDOR MENU] Error al enviar: {e}")
                self.cliente_conectado = False
                return False

    def enviar_estado_menu(
        self,
        pantalla: str,
        datos: Optional[dict] = None
    ) -> bool:
        """
        Sincroniza la pantalla actual al cliente.

        Pantallas: "principal", "lobby", "creditos", "controles", "estadisticas"
        """
        return self.enviar({
            "type": "MENU_STATE",
            "pantalla": pantalla,
            "datos": datos or {}
        })

    def enviar_estado_lobby(self, p2_conectado: bool) -> bool:
        """Envía estado del lobby al cliente."""
        return self.enviar({
            "type": "LOBBY_STATE",
            "p1_listo": True,
            "p2_conectado": p2_conectado,
        })

    def enviar_config(self, volumen: int, **kwargs) -> bool:
        """Sincroniza configuración al cliente."""
        return self.enviar({
            "type": "CONFIG_STATE",
            "volumen": volumen,
            **kwargs
        })

    def enviar_inicio_juego(self, seed: int) -> bool:
        """Ordena al cliente iniciar el juego."""
        return self.enviar({
            "type": "START_GAME",
            "seed": seed
        })

    def cerrar(self) -> None:
        """Cierra el servidor y la conexión del cliente."""
        self.ejecutando = False
        with self._lock:
            if self.cliente_socket:
                try:
                    self.cliente_socket.close()
                except Exception:
                    pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        log_net.info("[SERVIDOR MENU] Servidor cerrado")
