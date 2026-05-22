"""
network/protocol.py
===================
Protocolo de mensajes para el multijugador de Echoes.

Formato de cable:
    Cada mensaje es un objeto JSON terminado en newline (b'\\n').
    Esto permite leer mensajes completos con readline() sobre un socket
    sin necesidad de un campo de longitud.

    { "tipo": "estado", "datos": {...}, "ts": 1714000000.123 }

Roles asimétricos:
    VICTIMA  — Controla el personaje principal: movimiento, ataques,
               transiciones de sala. Es quien «sufre» el ciberacoso.
    ALIADO   — Rol de soporte: envía recursos, cura, desbloquea objetos
               a distancia. Representa a un amigo que apoya en la red.

Sin librerías externas — solo json y time de la stdlib.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Roles y tipos de mensaje
# ---------------------------------------------------------------------------

class Rol(str, Enum):
    """Roles disponibles en la sesión multijugador."""
    VICTIMA = "victima"
    ALIADO  = "aliado"
    SERVIDOR = "servidor"   # origen de mensajes del servidor


class TipoMensaje(str, Enum):
    """
    Catálogo de todos los tipos de mensaje del protocolo.

    Flujo típico de conexión:
        Cliente  --[conectar]--> Servidor
        Servidor --[aceptado]--> Cliente
        Servidor --[estado]---> Ambos clientes  (cada frame o cambio)
        Cliente  --[accion]---> Servidor
        Servidor --[evento]---> Ambos clientes
        Cliente  --[desconectar]--> Servidor
    """
    # Handshake
    CONECTAR      = "conectar"       # cliente anuncia rol y versión
    ACEPTADO      = "aceptado"       # servidor confirma conexión
    RECHAZADO     = "rechazado"      # servidor rechaza (rol ocupado, etc.)

    # Estado del juego
    ESTADO        = "estado"         # servidor -> clientes: snapshot completo
    DELTA         = "delta"          # servidor -> clientes: solo cambios

    # Acciones de jugadores
    ACCION        = "accion"         # cliente -> servidor: input del jugador
    APOYO         = "apoyo"          # aliado -> servidor: acción de soporte

    # Eventos de juego
    EVENTO        = "evento"         # servidor -> clientes: ocurrió algo

    # Administración
    PING          = "ping"           # keepalive request
    PONG          = "pong"           # keepalive response
    DESCONECTAR   = "desconectar"    # cierre limpio
    ERROR         = "error"          # mensaje de error


# ---------------------------------------------------------------------------
# Estructura de mensaje
# ---------------------------------------------------------------------------

@dataclass
class Mensaje:
    """
    Unidad de comunicación del protocolo Echoes.

    Parámetros
    ----------
    tipo : TipoMensaje | str
        Tipo de mensaje (ver catálogo arriba).
    datos : dict
        Payload específico del tipo.  Siempre un dict, puede estar vacío.
    origen : Rol | str | None
        Quién envió el mensaje.  El servidor lo rellena automáticamente.
    ts : float
        Timestamp UNIX en el momento de creación.
    """
    tipo:   str
    datos:  Dict[str, Any] = field(default_factory=dict)
    origen: Optional[str]  = None
    ts:     float          = field(default_factory=time.time)

    def serializar(self) -> bytes:
        """
        Convierte el mensaje a bytes listos para enviar por el socket.

        El resultado es JSON + '\\n'.  Usar '\\n' como delimitador permite
        que el receptor use socket.makefile().readline() para leer mensajes
        completos sin necesidad de un header de longitud.
        """
        obj = {
            "tipo":   self.tipo,
            "datos":  self.datos,
            "origen": self.origen,
            "ts":     self.ts,
        }
        return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

    @classmethod
    def deserializar(cls, raw: bytes | str) -> Optional["Mensaje"]:
        """
        Parsea bytes/string recibidos desde el socket.

        Retorna None si el formato es inválido (protege al receptor de
        mensajes malformados sin lanzar excepción).
        """
        try:
            texto = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            obj = json.loads(texto.strip())
            return cls(
                tipo   = obj.get("tipo", ""),
                datos  = obj.get("datos", {}),
                origen = obj.get("origen"),
                ts     = obj.get("ts", time.time()),
            )
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            return None

    def __repr__(self) -> str:
        return f"Mensaje(tipo={self.tipo!r}, origen={self.origen!r}, datos={self.datos})"


# ---------------------------------------------------------------------------
# Fábricas de mensajes (evitan errores tipográficos en claves)
# ---------------------------------------------------------------------------

def msg_conectar(rol: str, version: str = "1.0") -> Mensaje:
    """Cliente anuncia que quiere unirse con el rol indicado."""
    return Mensaje(TipoMensaje.CONECTAR, {"rol": rol, "version": version}, origen=rol)


def msg_aceptado(rol: str, seed: int | None = None) -> Mensaje:
    """Servidor confirma la conexión del cliente."""
    return Mensaje(TipoMensaje.ACEPTADO, {"rol": rol, "seed": seed}, origen=Rol.SERVIDOR)


def msg_rechazado(motivo: str) -> Mensaje:
    """Servidor rechaza la conexión e indica el motivo."""
    return Mensaje(TipoMensaje.RECHAZADO, {"motivo": motivo}, origen=Rol.SERVIDOR)


def msg_estado(
    pos_x: float,
    pos_y: float,
    sala: tuple[int, int],
    vidas: int,
    hp: int,
    apoyo: int,
    arma_id: str | None = None,
    enemigos_vivos: int = 0,
    sala_tipo: str = "normal",
    origen: str | None = None,
) -> Mensaje:
    """
    Snapshot completo del estado del juego.

    Lo envía el servidor a ambos clientes en cada tick de red
    (~10-20 veces por segundo).

    Args:
        origen: Rol que envía el estado. Si es None, se usa "servidor"
    """
    return Mensaje(
        TipoMensaje.ESTADO,
        {
            "pos":            [pos_x, pos_y],
            "sala":           list(sala),
            "vidas":          vidas,
            "hp":             hp,
            "apoyo":          apoyo,
            "arma_id":        arma_id,
            "enemigos_vivos": enemigos_vivos,
            "sala_tipo":      sala_tipo,
        },
        origen=origen or Rol.SERVIDOR,
    )


def msg_accion(tipo_accion: str, **kwargs: Any) -> Mensaje:
    """
    Acción enviada por la Víctima al servidor.

    Tipos de acción reconocidos:
        "mover"       — dx, dy (floats)
        "disparar"    — target_x, target_y
        "cambiar_arma"— arma_id
        "transicion"  — direccion ("N"|"S"|"E"|"W")
    """
    return Mensaje(TipoMensaje.ACCION, {"accion": tipo_accion, **kwargs},
                   origen=Rol.VICTIMA)


def msg_apoyo(tipo_apoyo: str, valor: Any = None) -> Mensaje:
    """
    Acción de soporte enviada por el Aliado al servidor.

    Tipos reconocidos:
        "curar"        — valor: int (puntos de HP a restaurar)
        "dar_apoyo"    — valor: int (puntos de apoyo/monedas)
        "revelar_mapa" — valor: None (descubre todas las salas en el minimapa)
        "escudo"       — valor: float (segundos de invulnerabilidad)
    """
    return Mensaje(TipoMensaje.APOYO, {"apoyo": tipo_apoyo, "valor": valor},
                   origen=Rol.ALIADO)


def msg_evento(nombre: str, **kwargs: Any) -> Mensaje:
    """
    Evento de juego difundido por el servidor a todos los clientes.

    Ejemplos: "enemigo_derrotado", "sala_limpia", "jugador_murio",
              "apoyo_aplicado", "nueva_sala".
    """
    return Mensaje(TipoMensaje.EVENTO, {"evento": nombre, **kwargs},
                   origen=Rol.SERVIDOR)


def msg_ping() -> Mensaje:
    return Mensaje(TipoMensaje.PING, {})


def msg_pong() -> Mensaje:
    return Mensaje(TipoMensaje.PONG, {})


def msg_desconectar(motivo: str = "normal") -> Mensaje:
    return Mensaje(TipoMensaje.DESCONECTAR, {"motivo": motivo})


def msg_error(descripcion: str) -> Mensaje:
    return Mensaje(TipoMensaje.ERROR, {"descripcion": descripcion},
                   origen=Rol.SERVIDOR)


def msg_enemigo_muerto(pos_x: float, pos_y: float, tipo: str, sala: tuple[int, int], enemy_id: str = None) -> Mensaje:
    """
    Evento: Un enemigo fue eliminado.

    Se envía cuando un jugador mata a un enemigo. El servidor lo broadcast
    a todos los clientes para que actualicen su estado local.

    Args:
        pos_x, pos_y: Posición del enemigo (para encontrarlo en la otra computadora)
        tipo: Nombre de clase del enemigo (e.g., "BasicEnemy", "TankEnemy")
        sala: Tuple (i, j) indicando en qué sala murió
        enemy_id: ID único del enemigo (para búsqueda exacta sin confusiones de posición)

    Returns:
        Mensaje EVENTO con evento='enemigo_muerto' + datos de ubicación, tipo e ID
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "enemigo_muerto",
            "pos_x": pos_x,
            "pos_y": pos_y,
            "enemy_type": tipo,
            "sala": sala,
            "enemy_id": enemy_id,  # Nuevo: enviar el ID para búsqueda exacta
        },
        origen=Rol.SERVIDOR,
    )


def msg_proyectil_disparado(
    pos_x: float,
    pos_y: float,
    dir_x: float,
    dir_y: float,
    weapon_id: str,
    sala: tuple[int, int],
) -> Mensaje:
    """
    Evento: Un jugador disparó un proyectil.

    Enviado cuando un jugador dispara, para que otros jugadores vean la bala.

    Args:
        pos_x, pos_y: Posición inicial de la bala
        dir_x, dir_y: Dirección normalizada (vector unitario)
        weapon_id: ID del arma (para identificar tipo de bala)
        sala: (i, j) en qué sala se dispara
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "proyectil_disparado",
            "pos_x": pos_x,
            "pos_y": pos_y,
            "dir_x": dir_x,
            "dir_y": dir_y,
            "weapon_id": weapon_id,
            "sala": sala,
        },
        origen=Rol.SERVIDOR,
    )


def msg_enemigo_danado(
    pos_x: float,
    pos_y: float,
    enemy_type: str,
    damage: int,
    sala: tuple[int, int],
) -> Mensaje:
    """
    Evento: Un enemigo recibió daño.

    Enviado cuando un proyectil golpea un enemigo, para sincronizar HP.

    Args:
        pos_x, pos_y: Posición del enemigo
        enemy_type: Nombre de clase del enemigo
        damage: Cantidad de daño
        sala: (i, j) ubicación
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "tipo": "enemigo_danado",
            "pos_x": pos_x,
            "pos_y": pos_y,
            "enemy_type": enemy_type,
            "damage": damage,
            "sala": sala,
        },
        origen=Rol.SERVIDOR,
    )


def msg_enemies_state(enemies_list: list[dict], room_id: tuple[int, int]) -> Mensaje:
    """
    Sincronización continua: Estado de todos los enemigos en una sala.

    El host envía esto periódicamente (cada ~50ms) para que el cliente
    mantenga las posiciones de enemigos sincronizadas.

    Args:
        enemies_list: Lista de dicts con: {
            "id": str (enemy_id único),
            "tipo": str (nombre de clase),
            "x": float,
            "y": float,
            "health": int,
            "vivo": bool,
            "animator_state": str (estado actual del animator: "idle", "run", "shoot", "attack"),
            "facing_right": bool (dirección del sprite),
        }
        room_id: Tupla (i, j) de la sala actual
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "enemies_state",
            "enemies": enemies_list,
            "room_id": list(room_id),
        },
        origen=Rol.SERVIDOR,
    )


def msg_bullet_fired_by_client(
    player_id: int,
    x: float,
    y: float,
    dir_x: float,
    dir_y: float,
    damage: int,
) -> Mensaje:
    """
    Disparo del cliente: Enviado para que el servidor procese colisiones.

    Args:
        player_id: ID del jugador que dispara (2 para ALIADO)
        x, y: Posición inicial de la bala
        dir_x, dir_y: Dirección normalizada
        damage: Daño de la bala
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "bullet_fired_by_client",
            "player_id": player_id,
            "x": x,
            "y": y,
            "dir_x": dir_x,
            "dir_y": dir_y,
            "damage": damage,
        },
        origen=Rol.ALIADO,
    )


def msg_enemy_projectiles_state(projectiles_list: list[dict], room_id: tuple[int, int]) -> Mensaje:
    """
    Sincronización continua: Estado de todas las balas de enemigos.

    El host envía esto periódicamente para que el cliente vea los proyectiles enemigas.

    Args:
        projectiles_list: Lista de dicts con: {
            "id": str (identificador único),
            "x": float,
            "y": float,
            "dx": float (dirección X normalizada),
            "dy": float (dirección Y normalizada),
            "vivo": bool,
        }
        room_id: Tupla (i, j) de la sala actual
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "enemy_projectiles_state",
            "projectiles": projectiles_list,
            "room_id": list(room_id),
        },
        origen=Rol.SERVIDOR,
    )


def msg_transicion_completada(
    sala_nueva: tuple[int, int],
    pos_victima: tuple[float, float],
    pos_aliado: tuple[float, float],
) -> Mensaje:
    """
    Evento: Transición de sala completada.

    El servidor notifica al cliente que la transición se completó y ambos
    jugadores están en la nueva sala.

    Args:
        sala_nueva: Tupla (i, j) de la nueva sala
        pos_victima: Posición (x, y) donde aparece el VICTIMA
        pos_aliado: Posición (x, y) donde aparece el ALIADO
    """
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "transicion_completada",
            "sala_nueva": list(sala_nueva),
            "pos_victima": list(pos_victima),
            "pos_aliado": list(pos_aliado),
        },
        origen=Rol.SERVIDOR,
    )


# ---------------------------------------------------------------------------
# Validación básica (usada por servidor para sanear mensajes entrantes)
# ---------------------------------------------------------------------------

# Claves requeridas en datos según tipo de mensaje
_REQUERIDOS: dict[str, list[str]] = {
    TipoMensaje.CONECTAR:    ["rol"],
    TipoMensaje.ACCION:      ["accion"],
    TipoMensaje.APOYO:       ["apoyo"],
}


def validar(msg: Mensaje) -> bool:
    """
    Verifica que el mensaje tiene las claves mínimas en datos.

    Retorna True si es válido, False si falta alguna clave requerida.
    """
    requeridos = _REQUERIDOS.get(msg.tipo, [])
    return all(k in msg.datos for k in requeridos)
