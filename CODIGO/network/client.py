"""
network/client.py
=================
Cliente TCP para el multijugador de Echoes.

El cliente corre su bucle de recepción en un hilo de fondo (daemon),
por lo que el game loop NUNCA se bloquea esperando datos de red.

Uso típico (desde Game.py o desde un script separado)::

    cliente = ClienteEchoes(host="192.168.1.10", port=5555, rol="victima")
    if not cliente.conectar():
        print("No se pudo conectar")
        sys.exit(1)

    while corriendo:
        for msg in cliente.tick():
            manejar_mensaje(msg)
        cliente.enviar(msg_accion("mover", dx=1.0, dy=0.0))
        time.sleep(1/60)

    cliente.desconectar()

Sin librerías externas — solo socket, threading, queue de la stdlib.
"""
from __future__ import annotations

import queue
import socket
import threading
import time
from typing import List, Optional

from network.protocol import (
    Mensaje, Rol, TipoMensaje,
    msg_conectar, msg_ping, msg_desconectar,
)
from dev.logger import log_net


class ClienteEchoes:
    """
    Cliente TCP para la sesión multijugador de Echoes.

    Parámetros
    ----------
    host : str
        IP o hostname del servidor.
    port : int
        Puerto TCP del servidor.
    rol : str
        Rol que solicita este cliente ("victima" o "aliado").
    timeout_conexion : float
        Segundos máximos de espera para establecer la conexión TCP.
    """

    INTERVALO_PING = 5.0    # segundos entre pings automáticos
    PUERTO_DEFAULT = 5555

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = PUERTO_DEFAULT,
        rol: str = Rol.VICTIMA,
        timeout_conexion: float = 5.0,
    ) -> None:
        self.host              = host
        self.port              = port
        self.rol               = rol
        self._timeout_conexion = timeout_conexion

        self._conectado   = False
        self._sock: Optional[socket.socket] = None
        self._file        = None
        self._lock_envio  = threading.Lock()
        self._cola_in: "queue.Queue[Mensaje]" = queue.Queue()

        # Datos recibidos en el handshake
        self.seed: Optional[int] = None

        # Último ping enviado (para keepalive)
        self._ultimo_ping: float = 0.0

        self._hilo_recv: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #

    def conectar(self) -> bool:
        """
        Establece la conexión TCP y realiza el handshake con el servidor.

        Retorna True si la conexión fue aceptada, False en caso contrario.
        Bloqueante hasta que el servidor responde o salta el timeout.
        """
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self._timeout_conexion)
            self._sock.connect((self.host, self.port))
            log_net.info("Socket conectado a %s:%d", self.host, self.port)

            # Enviar solicitud de rol
            self._sock.sendall(msg_conectar(self.rol).serializar())

            # Esperar respuesta del servidor
            file_ = self._sock.makefile("rb")
            linea = file_.readline()
            respuesta = Mensaje.deserializar(linea)

            if respuesta is None:
                log_net.error("Respuesta invalida del servidor durante handshake")
                self._sock.close()
                return False

            if respuesta.tipo == TipoMensaje.RECHAZADO:
                motivo = respuesta.datos.get("motivo", "desconocido")
                log_net.error("Conexion rechazada: %s", motivo)
                self._sock.close()
                return False

            if respuesta.tipo != TipoMensaje.ACEPTADO:
                log_net.error("Tipo de respuesta inesperado: %s", respuesta.tipo)
                self._sock.close()
                return False

            # Handshake exitoso
            self.seed = respuesta.datos.get("seed")
            self._sock.settimeout(None)   # modo bloqueante normal
            self._file = file_
            self._conectado = True
            self._ultimo_ping = time.time()

            log_net.info(
                "Conectado como %s | seed=%s | servidor=%s:%d",
                self.rol, self.seed, self.host, self.port
            )

            # Lanzar hilo de recepción
            self._hilo_recv = threading.Thread(
                target=self._recv_loop,
                name=f"echoes-client-recv-{self.rol}",
                daemon=True,
            )
            self._hilo_recv.start()
            return True

        except (OSError, TimeoutError, ConnectionRefusedError) as exc:
            log_net.error("No se pudo conectar a %s:%d — %s", self.host, self.port, exc)
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
            return False

    def desconectar(self, motivo: str = "normal") -> None:
        """Envía un mensaje de desconexión limpia y cierra el socket."""
        if self._conectado:
            try:
                self.enviar(msg_desconectar(motivo))
            except OSError:
                pass
        self._conectado = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        log_net.info("Cliente desconectado (%s)", motivo)

    # ------------------------------------------------------------------ #
    # Game loop API
    # ------------------------------------------------------------------ #

    def tick(self) -> List[Mensaje]:
        """
        Devuelve todos los mensajes recibidos desde el último tick.

        No bloquea. Llamar una vez por frame del game loop.
        """
        mensajes: List[Mensaje] = []
        while True:
            try:
                mensajes.append(self._cola_in.get_nowait())
            except queue.Empty:
                break

        # Keepalive automático
        ahora = time.time()
        if self._conectado and (ahora - self._ultimo_ping) >= self.INTERVALO_PING:
            self.enviar(msg_ping())
            self._ultimo_ping = ahora

        return mensajes

    def enviar(self, msg: Mensaje) -> bool:
        """
        Envía un mensaje al servidor.

        Thread-safe. Retorna False si la conexión está cerrada.
        """
        if not self._conectado or self._sock is None:
            return False
        with self._lock_envio:
            try:
                self._sock.sendall(msg.serializar())
                return True
            except (OSError, BrokenPipeError):
                self._conectado = False
                log_net.warning("Error al enviar — conexion perdida")
                return False

    def esta_conectado(self) -> bool:
        return self._conectado

    # ------------------------------------------------------------------ #
    # Hilo de recepción
    # ------------------------------------------------------------------ #

    def _recv_loop(self) -> None:
        """Lee mensajes del servidor línea a línea en un hilo de fondo."""
        log_net.info("Hilo de recepcion del cliente iniciado")
        try:
            while self._conectado:
                try:
                    linea = self._file.readline()
                except OSError:
                    break

                if not linea:   # EOF = servidor cerró la conexión
                    log_net.info("Servidor cerro la conexion")
                    break

                msg = Mensaje.deserializar(linea)
                if msg is None:
                    log_net.warning("Mensaje malformado recibido, ignorado")
                    continue

                # Responder PING automáticamente
                if msg.tipo == TipoMensaje.PING:
                    self.enviar(
                        Mensaje(TipoMensaje.PONG, {}, origen=self.rol)
                    )
                    continue

                self._cola_in.put(msg)

        except Exception as exc:
            log_net.warning("Error en recv_loop del cliente: %s", exc)
        finally:
            self._conectado = False
            log_net.info("Hilo de recepcion del cliente terminado")

    # ------------------------------------------------------------------ #
    # Representación
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        estado = "conectado" if self._conectado else "desconectado"
        return f"ClienteEchoes(rol={self.rol!r}, {estado}, {self.host}:{self.port})"
