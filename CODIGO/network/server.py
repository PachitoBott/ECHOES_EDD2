"""
network/server.py
=================
Servidor TCP para la sesión multijugador de Echoes.

Arquitectura:
    - Un hilo principal de aceptacion (_accept_loop) espera nuevas conexiones.
    - Por cada cliente aceptado se lanza un hilo de recepcion (_recv_loop).
    - Todas las colas son thread-safe (queue.Queue).
    - El game loop llama a tick() una vez por frame para procesar mensajes
      sin bloquear.

Capacidad: máximo 2 jugadores simultáneos (Víctima + Aliado).

Sin librerías externas — solo socket, threading, queue de la stdlib.
"""
from __future__ import annotations

import queue
import socket
import threading
import time
from typing import Dict, List, Optional

from network.protocol import (
    Mensaje, Rol, TipoMensaje,
    msg_aceptado, msg_rechazado, msg_error, msg_evento, msg_pong,
    validar,
)
from dev.logger import log_net


# ---------------------------------------------------------------------------
# Conexión de un cliente individual
# ---------------------------------------------------------------------------

class _ConexionCliente:
    """
    Envuelve un socket conectado con su hilo de recepción.

    Atributos públicos (de solo lectura desde fuera):
        rol         : Rol del jugador (VICTIMA o ALIADO)
        conectado   : True mientras el socket sigue activo
        ultimo_ping : timestamp del último PING/PONG recibido
    """

    TIMEOUT_PING = 15.0   # segundos sin respuesta antes de considerar caído

    def __init__(
        self,
        conn: socket.socket,
        addr: tuple,
        rol: str,
        cola_in: "queue.Queue[Mensaje]",
    ) -> None:
        self.conn       = conn
        self.addr       = addr
        self.rol        = rol
        self.conectado  = True
        self.ultimo_ping: float = time.time()
        self._cola_in   = cola_in   # cola compartida con el servidor
        self._lock      = threading.Lock()

        # Usamos makefile para leer líneas completas cómodamente
        self._file = conn.makefile("rb")

    # ------------------------------------------------------------------ #
    # Envío
    # ------------------------------------------------------------------ #

    def enviar(self, msg: Mensaje) -> bool:
        """
        Serializa y envía un mensaje al cliente.

        Thread-safe. Retorna False si la conexión ya está cerrada.
        """
        if not self.conectado:
            return False
        with self._lock:
            try:
                self.conn.sendall(msg.serializar())
                return True
            except (OSError, BrokenPipeError):
                self.conectado = False
                return False

    # ------------------------------------------------------------------ #
    # Recepción (hilo dedicado)
    # ------------------------------------------------------------------ #

    def iniciar_hilo_recepcion(self) -> threading.Thread:
        hilo = threading.Thread(
            target=self._recv_loop,
            name=f"echoes-recv-{self.rol}",
            daemon=True,
        )
        hilo.start()
        return hilo

    def _recv_loop(self) -> None:
        """Lee mensajes línea a línea hasta que el cliente se desconecte."""
        log_net.info("Recepcion iniciada para %s (%s)", self.rol, self.addr)
        try:
            while self.conectado:
                try:
                    linea = self._file.readline()
                except OSError:
                    break

                if not linea:           # EOF = cliente cerró la conexión
                    break

                msg = Mensaje.deserializar(linea)
                if msg is None:
                    log_net.warning("Mensaje malformado de %s, ignorado", self.rol)
                    continue

                # El servidor rellena el campo origen para que los handlers
                # sepan quién envió el mensaje.
                msg.origen = self.rol

                # Responder PING automáticamente
                if msg.tipo == TipoMensaje.PING:
                    self.ultimo_ping = time.time()
                    self.enviar(msg_pong())
                    continue

                if msg.tipo == TipoMensaje.PONG:
                    self.ultimo_ping = time.time()
                    continue

                if msg.tipo == TipoMensaje.DESCONECTAR:
                    log_net.info("%s solicitó desconexión limpia", self.rol)
                    break

                self._cola_in.put(msg)

        except Exception as exc:
            log_net.warning("Error en recv_loop de %s: %s", self.rol, exc)
        finally:
            self.conectado = False
            self._file.close()
            try:
                self.conn.close()
            except OSError:
                pass
            log_net.info("Conexion cerrada: %s (%s)", self.rol, self.addr)

    def cerrar(self) -> None:
        self.conectado = False
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.conn.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Servidor principal
# ---------------------------------------------------------------------------

class ServidorEchoes:
    """
    Servidor TCP para la sesión multijugador de Echoes.

    Uso típico (servidor en una terminal)::

        servidor = ServidorEchoes(host="0.0.0.0", port=5555)
        servidor.iniciar()

        while True:
            for msg in servidor.tick():
                # procesar acciones de los clientes
                ...
            servidor.broadcast(msg_estado(...))
            time.sleep(1/20)   # 20 ticks por segundo

        servidor.detener()

    Parámetros
    ----------
    host : str
        Dirección en la que escuchar.  "0.0.0.0" = todas las interfaces.
    port : int
        Puerto TCP (por defecto 5555).
    seed : int | None
        Seed del dungeon que se comunica a los clientes al conectarse.
    """

    MAX_JUGADORES = 2
    PUERTO_DEFAULT = 5555

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = PUERTO_DEFAULT,
        seed: int | None = None,
    ) -> None:
        self.host    = host
        self.port    = port
        self.seed    = seed
        self._activo = False

        # Cola de mensajes entrantes de todos los clientes
        self._cola_in: "queue.Queue[Mensaje]" = queue.Queue()

        # Conexiones activas indexadas por rol
        self._clientes: Dict[str, _ConexionCliente] = {}
        self._lock_clientes = threading.Lock()

        # Socket de escucha
        self._server_sock: Optional[socket.socket] = None
        self._hilo_accept: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #

    def iniciar(self) -> None:
        """
        Abre el socket y lanza el hilo de aceptación.

        Llama a este método antes del game loop.
        """
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR permite reutilizar el puerto si el proceso se reinicia
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(self.MAX_JUGADORES)
        self._server_sock.settimeout(1.0)   # para que _accept_loop pueda salir limpio
        self._activo = True

        self._hilo_accept = threading.Thread(
            target=self._accept_loop,
            name="echoes-accept",
            daemon=True,
        )
        self._hilo_accept.start()
        log_net.info("Servidor escuchando en %s:%d", self.host, self.port)

    def detener(self) -> None:
        """Cierra todas las conexiones y el socket de escucha."""
        self._activo = False
        with self._lock_clientes:
            for cliente in self._clientes.values():
                cliente.cerrar()
            self._clientes.clear()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        log_net.info("Servidor detenido")

    # ------------------------------------------------------------------ #
    # Game loop API
    # ------------------------------------------------------------------ #

    def tick(self) -> List[Mensaje]:
        """
        Procesa y devuelve todos los mensajes recibidos desde el último tick.

        Llamar una vez por frame (o por tick de red). No bloquea.
        """
        mensajes: List[Mensaje] = []
        while True:
            try:
                msg = self._cola_in.get_nowait()
                if validar(msg):
                    mensajes.append(msg)
                else:
                    log_net.warning("Mensaje invalido recibido de %s: %s", msg.origen, msg)
            except queue.Empty:
                break
        self._verificar_timeouts()
        return mensajes

    def broadcast(self, msg: Mensaje) -> None:
        """Envía el mensaje a todos los clientes conectados."""
        with self._lock_clientes:
            clientes = list(self._clientes.values())
        for cliente in clientes:
            cliente.enviar(msg)

    def enviar_a(self, rol: str, msg: Mensaje) -> bool:
        """Envía el mensaje sólo al cliente con el rol indicado."""
        with self._lock_clientes:
            cliente = self._clientes.get(rol)
        if cliente is None:
            return False
        return cliente.enviar(msg)

    # ------------------------------------------------------------------ #
    # Estado de la sesión
    # ------------------------------------------------------------------ #

    def roles_conectados(self) -> List[str]:
        """Devuelve la lista de roles actualmente conectados."""
        with self._lock_clientes:
            return [
                rol for rol, c in self._clientes.items() if c.conectado
            ]

    def esta_listo(self) -> bool:
        """True si ambos roles (Víctima y Aliado) están conectados."""
        conectados = self.roles_conectados()
        return Rol.VICTIMA in conectados and Rol.ALIADO in conectados

    def num_conectados(self) -> int:
        return len(self.roles_conectados())

    # ------------------------------------------------------------------ #
    # Hilo de aceptación
    # ------------------------------------------------------------------ #

    def _accept_loop(self) -> None:
        """Acepta nuevas conexiones y las autentica con el handshake."""
        log_net.info("Hilo de aceptacion iniciado")
        while self._activo:
            try:
                conn, addr = self._server_sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            log_net.info("Nueva conexion desde %s", addr)
            hilo = threading.Thread(
                target=self._handshake,
                args=(conn, addr),
                daemon=True,
            )
            hilo.start()

    def _handshake(self, conn: socket.socket, addr: tuple) -> None:
        """
        Realiza el handshake inicial con un nuevo cliente.

        Espera un mensaje CONECTAR, verifica el rol y responde con
        ACEPTADO o RECHAZADO.
        """
        conn.settimeout(5.0)   # 5 segundos para completar el handshake
        try:
            file_ = conn.makefile("rb")
            linea = file_.readline()
            msg = Mensaje.deserializar(linea)

            if msg is None or msg.tipo != TipoMensaje.CONECTAR:
                conn.sendall(msg_rechazado("Se esperaba mensaje CONECTAR").serializar())
                conn.close()
                return

            rol = msg.datos.get("rol", "").lower()
            if rol not in (Rol.VICTIMA, Rol.ALIADO):
                conn.sendall(
                    msg_rechazado(f"Rol desconocido: {rol!r}. Use 'victima' o 'aliado'").serializar()
                )
                conn.close()
                return

            with self._lock_clientes:
                if rol in self._clientes and self._clientes[rol].conectado:
                    conn.sendall(
                        msg_rechazado(f"El rol '{rol}' ya está ocupado").serializar()
                    )
                    conn.close()
                    return
                # Contamos directamente dentro del lock para evitar deadlock
                # (roles_conectados() también adquiere _lock_clientes)
                num_activos = sum(1 for c in self._clientes.values() if c.conectado)
                if num_activos >= self.MAX_JUGADORES:
                    conn.sendall(msg_rechazado("Sesion llena").serializar())
                    conn.close()
                    return

                # Confirmar conexion
                conn.settimeout(None)   # modo bloqueante normal
                conn.sendall(msg_aceptado(rol, self.seed).serializar())

                cliente = _ConexionCliente(conn, addr, rol, self._cola_in)
                self._clientes[rol] = cliente
                cliente.iniciar_hilo_recepcion()
                roles_ahora = [r for r, c in self._clientes.items() if c.conectado]

            log_net.info("Jugador conectado: rol=%s addr=%s", rol, addr)

            # Notificar a los demás que alguien se unió (fuera del lock)
            self.broadcast(
                msg_evento("jugador_unido", rol=rol, conectados=roles_ahora)
            )

        except (OSError, TimeoutError) as exc:
            log_net.warning("Handshake fallido desde %s: %s", addr, exc)
            try:
                conn.close()
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Mantenimiento de conexiones
    # ------------------------------------------------------------------ #

    def _verificar_timeouts(self) -> None:
        """Detecta clientes caídos por inactividad y los desconecta."""
        ahora = time.time()
        with self._lock_clientes:
            caidos = [
                rol for rol, c in self._clientes.items()
                if c.conectado and (ahora - c.ultimo_ping) > _ConexionCliente.TIMEOUT_PING
            ]
        for rol in caidos:
            log_net.warning("Timeout en cliente %s — desconectando", rol)
            with self._lock_clientes:
                cliente = self._clientes.get(rol)
            if cliente:
                cliente.cerrar()
            self.broadcast(msg_evento("jugador_desconectado", rol=rol, motivo="timeout"))
