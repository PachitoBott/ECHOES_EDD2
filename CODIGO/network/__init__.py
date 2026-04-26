"""
network -- Multijugador cliente-servidor con sockets (Fase 3, EDD 2 UniNorte)
============================================================================

Modulos disponibles:
  protocol.py  -- Protocolo de mensajes JSON sobre TCP (Mensaje, TipoMensaje, Rol)
  server.py    -- ServidorEchoes: servidor TCP con hilos por cliente
  client.py    -- ClienteEchoes: cliente TCP no bloqueante
  manager.py   -- NetworkManager: capa de alto nivel para Game.py

Roles asimetricos:
    VICTIMA  -- controla el personaje, sufre el ciberacoso
    ALIADO   -- soporte remoto: cura, recursos, revela mapa
"""

from network.protocol import Mensaje, Rol, TipoMensaje
from network.server import ServidorEchoes
from network.client import ClienteEchoes
from network.manager import NetworkManager, EventoRed

__all__ = [
    "Mensaje", "Rol", "TipoMensaje",
    "ServidorEchoes", "ClienteEchoes",
    "NetworkManager", "EventoRed",
]
