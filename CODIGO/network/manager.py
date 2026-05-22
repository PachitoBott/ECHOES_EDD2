"""
network/manager.py
==================
Capa de alto nivel que conecta el módulo de red con Game.py.

NetworkManager abstrae si se está corriendo como servidor o como cliente,
y expone una API uniforme que el game loop puede usar sin saber los detalles
del socket subyacente.

Roles asimétricos en Echoes:
    VICTIMA:  Controla el personaje.  Envía su posición, sala actual, HP.
              Recibe acciones de soporte del Aliado.
    ALIADO:   Rol de soporte.  Ve el estado del juego pero no controla el
              personaje directamente.  Puede enviar recursos (curación,
              apoyo económico, revelar mapa) al servidor que los aplica
              sobre la Víctima.

Integración con Game.py (ejemplo)::

    # En Game.__init__:
    self.net: NetworkManager | None = None

    # Para activar como servidor:
    self.net = NetworkManager.como_servidor(port=5555, seed=self.current_seed)
    self.net.iniciar()

    # Para activar como cliente:
    self.net = NetworkManager.como_cliente(host="192.168.1.5", port=5555,
                                            rol="aliado")
    if not self.net.iniciar():
        print("No se pudo conectar")

    # En Game._update (una vez por frame):
    if self.net:
        eventos = self.net.tick(estado_local)
        for ev in eventos:
            self._aplicar_evento_red(ev)

    # Para enviar apoyo (desde el Aliado):
    if self.net and self.net.es_aliado:
        self.net.enviar_apoyo("curar", valor=2)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from network.protocol import (
    Mensaje, Rol, TipoMensaje,
    msg_estado, msg_accion, msg_apoyo, msg_evento,
)
from network.server import ServidorEchoes
from network.client import ClienteEchoes
from dev.logger import log_net


# ---------------------------------------------------------------------------
# Evento de red normalizado (lo que recibe Game.py)
# ---------------------------------------------------------------------------

class EventoRed:
    """
    Representa un evento de red ya procesado, listo para que Game.py lo maneje.

    Atributos
    ---------
    tipo : str
        Nombre del evento (ej. "apoyo_recibido", "jugador_unido", "estado").
    datos : dict
        Payload del evento.
    origen : str | None
        Rol que originó el evento.
    """

    def __init__(self, tipo: str, datos: Dict[str, Any], origen: str | None = None) -> None:
        self.tipo   = tipo
        self.datos  = datos
        self.origen = origen

    def __repr__(self) -> str:
        return f"EventoRed(tipo={self.tipo!r}, origen={self.origen!r})"


# ---------------------------------------------------------------------------
# NetworkManager
# ---------------------------------------------------------------------------

class NetworkManager:
    """
    Gestor de red de alto nivel para Echoes.

    Modos de operación:
        SERVIDOR: Hospeda la sesión.  Recibe acciones de ambos roles y
                  difunde el estado del juego.
        CLIENTE:  Se conecta a un servidor.  Envía acciones propias y
                  recibe el estado del juego.

    Parámetros (usa los classmethods como_servidor / como_cliente)
    """

    # Intervalo mínimo entre envíos de estado al servidor (evita saturar la red)
    INTERVALO_ESTADO = 1.0 / 20.0   # 20 Hz

    def __init__(self) -> None:
        self._modo:      str = "ninguno"          # "servidor" | "cliente"
        self._rol:       str = Rol.VICTIMA        # rol de este proceso
        self._servidor:  Optional[ServidorEchoes] = None
        self._cliente:   Optional[ClienteEchoes]  = None
        self._iniciado:  bool = False
        self._ultimo_estado: float = 0.0

    # ------------------------------------------------------------------ #
    # Constructores alternativos
    # ------------------------------------------------------------------ #

    @classmethod
    def como_servidor(
        cls,
        host: str = "0.0.0.0",
        port: int = ServidorEchoes.PUERTO_DEFAULT,
        seed: int | None = None,
    ) -> "NetworkManager":
        """
        Crea un NetworkManager en modo SERVIDOR.

        El servidor también actúa como la Víctima (controla el juego localmente).
        El Aliado se conecta remotamente.
        """
        mgr = cls()
        mgr._modo     = "servidor"
        mgr._rol      = Rol.VICTIMA
        mgr._servidor = ServidorEchoes(host=host, port=port, seed=seed)
        return mgr

    @classmethod
    def como_cliente(
        cls,
        host: str = "127.0.0.1",
        port: int = ClienteEchoes.PUERTO_DEFAULT,
        rol: str = Rol.ALIADO,
        timeout: float = 5.0,
    ) -> "NetworkManager":
        """
        Crea un NetworkManager en modo CLIENTE.

        El cliente puede ser la Víctima o el Aliado según el rol indicado.
        """
        mgr = cls()
        mgr._modo    = "cliente"
        mgr._rol     = rol
        mgr._cliente = ClienteEchoes(host=host, port=port, rol=rol,
                                      timeout_conexion=timeout)
        return mgr

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #

    def iniciar(self) -> bool:
        """
        Inicia la conexión de red.

        En modo servidor: abre el socket y espera jugadores.
        En modo cliente: intenta conectarse al servidor.

        Retorna True si tuvo éxito.
        """
        if self._modo == "servidor":
            self._servidor.iniciar()
            self._iniciado = True
            log_net.info("NetworkManager iniciado como SERVIDOR")
            return True

        if self._modo == "cliente":
            ok = self._cliente.conectar()
            if ok:
                self._iniciado = True
                log_net.info("NetworkManager iniciado como CLIENTE (rol=%s)", self._rol)
            return ok

        return False

    def detener(self) -> None:
        """Cierra todas las conexiones de red."""
        if self._servidor:
            self._servidor.detener()
        if self._cliente:
            self._cliente.desconectar()
        self._iniciado = False
        log_net.info("NetworkManager detenido")

    # ------------------------------------------------------------------ #
    # Game loop API
    # ------------------------------------------------------------------ #

    def tick(self, estado_local: Dict[str, Any] | None = None) -> List[EventoRed]:
        """
        Procesa mensajes entrantes y opcionalmente envía el estado local.

        Llamar UNA VEZ por frame del game loop.

        Parámetros
        ----------
        estado_local : dict | None
            Estado actual del juego (posición, HP, sala, etc.).
            Si se proporciona y ha pasado suficiente tiempo, se envía al servidor.

        Retorna
        -------
        list[EventoRed] — eventos que el juego debe manejar este frame.
        """
        if not self._iniciado:
            return []

        eventos: List[EventoRed] = []

        # Obtener mensajes crudos
        if self._modo == "servidor" and self._servidor:
            mensajes = self._servidor.tick()
        elif self._modo == "cliente" and self._cliente:
            mensajes = self._cliente.tick()
        else:
            mensajes = []

        # Traducir a EventoRed
        for msg in mensajes:
            ev = self._traducir(msg)
            if ev:
                eventos.append(ev)

            # El servidor retransmite el estado a todos los clientes
            if self._modo == "servidor":
                self._reenviar_a_clientes(msg)

        # Cliente envía su estado al servidor (VICTIMA o ALIADO)
        if (
            self._modo == "cliente"
            and estado_local is not None
        ):
            ahora = time.time()
            if ahora - self._ultimo_estado >= self.INTERVALO_ESTADO:
                # Usar msg_estado con el rol del cliente como origen
                msg_st = msg_estado(
                    pos_x=float(estado_local.get("pos_x", 0)),
                    pos_y=float(estado_local.get("pos_y", 0)),
                    sala=tuple(estado_local.get("sala", (0, 0))),
                    vidas=int(estado_local.get("vidas", 0)),
                    hp=int(estado_local.get("hp", 0)),
                    apoyo=int(estado_local.get("apoyo", 0)),
                    arma_id=estado_local.get("arma_id"),
                    enemigos_vivos=int(estado_local.get("enemigos_vivos", 0)),
                    sala_tipo=str(estado_local.get("sala_tipo", "normal")),
                    origen=self._rol,  # Enviar con el rol del cliente
                )
                self._cliente.enviar(msg_st)
                self._ultimo_estado = ahora

        # Servidor (VICTIMA) envía su estado a todos los clientes
        if (
            self._modo == "servidor"
            and self._rol == Rol.VICTIMA
            and estado_local is not None
            and self._servidor is not None
        ):
            ahora = time.time()
            if ahora - self._ultimo_estado >= self.INTERVALO_ESTADO:
                msg_estado_servidor = msg_estado(
                    pos_x=float(estado_local.get("pos_x", 0)),
                    pos_y=float(estado_local.get("pos_y", 0)),
                    sala=tuple(estado_local.get("sala", (0, 0))),
                    vidas=int(estado_local.get("vidas", 0)),
                    hp=int(estado_local.get("hp", 0)),
                    apoyo=int(estado_local.get("apoyo", 0)),
                    arma_id=estado_local.get("arma_id"),
                    enemigos_vivos=int(estado_local.get("enemigos_vivos", 0)),
                    sala_tipo=str(estado_local.get("sala_tipo", "normal")),
                    origen=Rol.VICTIMA,  # Servidor envía como VICTIMA
                )
                self._servidor.broadcast(msg_estado_servidor)
                self._ultimo_estado = ahora

        return eventos

    def enviar_apoyo(self, tipo_apoyo: str, valor: Any = None) -> bool:
        """
        Envía una acción de soporte desde el Aliado al servidor.

        Solo tiene efecto si este proceso es el Aliado.

        Tipos reconocidos: "curar", "dar_apoyo", "revelar_mapa", "escudo".
        """
        if self._rol != Rol.ALIADO:
            log_net.warning("enviar_apoyo() llamado desde un rol que no es Aliado")
            return False
        msg = msg_apoyo(tipo_apoyo, valor)
        return self._enviar(msg)

    def enviar_accion(self, tipo_accion: str, **kwargs: Any) -> bool:
        """
        Envía una acción de juego desde la Víctima al servidor.

        Solo tiene efecto si este proceso es la Víctima cliente.
        """
        if self._rol != Rol.VICTIMA or self._modo != "cliente":
            return False
        msg = msg_accion(tipo_accion, **kwargs)
        return self._enviar(msg)

    def broadcast_evento(self, nombre: str, **kwargs: Any) -> None:
        """
        (Solo modo servidor) Difunde un evento a todos los clientes.
        """
        if self._modo == "servidor" and self._servidor:
            self._servidor.broadcast(msg_evento(nombre, **kwargs))

    def enviar(self, mensaje: Mensaje) -> bool:
        """
        Envía un mensaje Mensaje a través de la red.

        - Si es servidor: broadcast a todos los clientes
        - Si es cliente: envía al servidor

        Args:
            mensaje: Objeto Mensaje a enviar

        Returns:
            True si se envió exitosamente, False si fallo
        """
        return self._enviar(mensaje)

    # ------------------------------------------------------------------ #
    # Propiedades de estado
    # ------------------------------------------------------------------ #

    @property
    def es_servidor(self) -> bool:
        return self._modo == "servidor"

    @property
    def es_aliado(self) -> bool:
        return self._rol == Rol.ALIADO

    @property
    def es_victima(self) -> bool:
        return self._rol == Rol.VICTIMA

    @property
    def rol(self) -> str:
        return self._rol

    @property
    def modo(self) -> str:
        return self._modo

    def esta_conectado(self) -> bool:
        if self._modo == "servidor":
            return self._servidor is not None and self._iniciado
        if self._modo == "cliente":
            return self._cliente is not None and self._cliente.esta_conectado()
        return False

    def roles_conectados(self) -> List[str]:
        """(Solo servidor) Roles actualmente conectados."""
        if self._modo == "servidor" and self._servidor:
            return self._servidor.roles_conectados()
        return []

    def sesion_lista(self) -> bool:
        """True si ambos roles están conectados (solo útil en modo servidor)."""
        if self._modo == "servidor" and self._servidor:
            return self._servidor.esta_listo()
        return False

    # ------------------------------------------------------------------ #
    # Handlers de acciones de apoyo (servidor aplica efectos sobre el juego)
    # ------------------------------------------------------------------ #

    def aplicar_apoyo(
        self,
        tipo_apoyo: str,
        valor: Any,
        player: Any,
    ) -> Optional[str]:
        """
        Aplica una acción de soporte del Aliado sobre el jugador Víctima.

        Llamar desde Game._aplicar_evento_red() cuando llega un EventoRed
        de tipo "apoyo_recibido".

        Parámetros
        ----------
        tipo_apoyo : str
            Tipo de apoyo ("curar", "dar_apoyo", "escudo", "revelar_mapa").
        valor : Any
            Magnitud del efecto (int, float o None).
        player : Player
            Objeto jugador sobre el que aplicar el efecto.

        Retorna
        -------
        str con descripción del efecto aplicado, o None si tipo desconocido.
        """
        if tipo_apoyo == "curar":
            cantidad = int(valor or 1)
            hp_actual = getattr(player, "hp", 0)
            max_hp = getattr(player, "max_hp", hp_actual)
            nuevo_hp = min(max_hp, hp_actual + cantidad)
            player.hp = nuevo_hp
            log_net.info("Apoyo: curar +%d HP (%d -> %d)", cantidad, hp_actual, nuevo_hp)
            return f"Aliado te curó +{cantidad} HP"

        if tipo_apoyo == "dar_apoyo":
            cantidad = int(valor or 10)
            gold_actual = getattr(player, "gold", 0)
            player.gold = gold_actual + cantidad
            log_net.info("Apoyo: dar_apoyo +%d monedas", cantidad)
            return f"Aliado te envió {cantidad} de apoyo"

        if tipo_apoyo == "escudo":
            duracion = float(valor or 3.0)
            actual = getattr(player, "invulnerable_timer", 0.0)
            player.invulnerable_timer = max(actual, duracion)
            log_net.info("Apoyo: escudo %.1fs de invulnerabilidad", duracion)
            return f"Aliado te protegió por {duracion:.1f}s"

        if tipo_apoyo == "revelar_mapa":
            # El dungeon se debe pasar desde Game; aquí solo señalizamos
            log_net.info("Apoyo: revelar_mapa solicitado")
            return "Aliado reveló el mapa"

        log_net.warning("Tipo de apoyo desconocido: %s", tipo_apoyo)
        return None

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _enviar(self, msg: Mensaje) -> bool:
        """Envía un mensaje a través del canal activo."""
        if self._modo == "servidor" and self._servidor:
            self._servidor.broadcast(msg)
            return True
        if self._modo == "cliente" and self._cliente:
            return self._cliente.enviar(msg)
        return False

    def _enviar_estado_victima(self, estado: Dict[str, Any]) -> None:
        """Empaqueta el estado local en msg_estado y lo envía al servidor."""
        try:
            msg = msg_estado(
                pos_x          = float(estado.get("pos_x", 0)),
                pos_y          = float(estado.get("pos_y", 0)),
                sala           = tuple(estado.get("sala", (0, 0))),
                vidas          = int(estado.get("vidas", 0)),
                hp             = int(estado.get("hp", 0)),
                apoyo          = int(estado.get("apoyo", 0)),
                arma_id        = estado.get("arma_id"),
                enemigos_vivos = int(estado.get("enemigos_vivos", 0)),
                sala_tipo      = str(estado.get("sala_tipo", "normal")),
            )
            self._cliente.enviar(msg)
        except (KeyError, TypeError, ValueError) as exc:
            log_net.warning("No se pudo empaquetar estado: %s", exc)

    def _traducir(self, msg: Mensaje) -> Optional[EventoRed]:
        """Convierte un Mensaje crudo en un EventoRed normalizado."""
        if msg.tipo == TipoMensaje.ACEPTADO:
            # Cliente recibe confirmación de conexión con seed
            return EventoRed("aceptado", msg.datos, msg.origen)

        if msg.tipo == TipoMensaje.ESTADO:
            return EventoRed("estado", msg.datos, msg.origen)

        if msg.tipo == TipoMensaje.APOYO:
            return EventoRed(
                "apoyo_recibido",
                {"apoyo": msg.datos.get("apoyo"), "valor": msg.datos.get("valor")},
                msg.origen,
            )

        if msg.tipo == TipoMensaje.ACCION:
            return EventoRed(
                "accion_recibida",
                msg.datos,
                msg.origen,
            )

        if msg.tipo == TipoMensaje.EVENTO:
            return EventoRed(
                msg.datos.get("evento", "evento_desconocido"),
                {k: v for k, v in msg.datos.items() if k != "evento"},
                msg.origen,
            )

        if msg.tipo == TipoMensaje.ERROR:
            log_net.error("Error del servidor: %s", msg.datos.get("descripcion"))
            return EventoRed("error_red", msg.datos, msg.origen)

        return None   # Tipos que no necesitan propagarse al juego (PING/PONG)

    def _reenviar_a_clientes(self, msg: Mensaje) -> None:
        """
        (Servidor) Retransmite mensajes relevantes a todos los clientes.

        El servidor actúa como intermediario: lo que envía la Víctima lo
        recibe el Aliado (y viceversa) para que ambos tengan contexto.
        """
        if not self._servidor:
            return
        # Solo retransmitir acciones y estados de jugadores
        if msg.tipo in (TipoMensaje.ACCION, TipoMensaje.APOYO, TipoMensaje.ESTADO):
            self._servidor.broadcast(msg)

    def __repr__(self) -> str:
        estado = "activo" if self._iniciado else "inactivo"
        return f"NetworkManager(modo={self._modo!r}, rol={self._rol!r}, {estado})"
