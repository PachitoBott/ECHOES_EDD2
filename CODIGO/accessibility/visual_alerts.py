"""
accessibility/visual_alerts.py
================================
Alertas visuales que sustituyen o complementan las pistas de audio.

Cada alerta es un flash de color en la pantalla (borde o fondo semitransparente)
que pulsa y desaparece.  Util para:
  - Jugadores con discapacidad auditiva.
  - Entornos sin sonido (aula, biblioteca).

Tipos de alerta predefinidos
------------------------------
  "golpe"     -> borde rojo pulsante (el jugador recibio daño)
  "curacion"  -> borde verde (el jugador se curo)
  "apoyo"     -> borde cian (apoyo recibido del aliado)
  "peligro"   -> parpadeo rojo suave (enemigo muy cercano)
  "victoria"  -> destello dorado
  "error"     -> borde naranja (accion fallida)

Uso desde Game.py::

    alertas = VisualAlertSystem(screen_w=960, screen_h=640)

    # Disparar una alerta:
    alertas.alertar("golpe")

    # Game loop:
    alertas.tick(dt)
    alertas.draw(surface, screen_scale=2)
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False


# ---------------------------------------------------------------------------
# Definicion de alertas
# ---------------------------------------------------------------------------

class _DefAlerta:
    """Configuracion de un tipo de alerta."""

    __slots__ = ("color", "duracion", "grosor", "pulsos")

    def __init__(
        self,
        color: Tuple[int, int, int],
        duracion: float = 0.6,
        grosor: int = 8,
        pulsos: int = 2,
    ) -> None:
        self.color    = color
        self.duracion = duracion
        self.grosor   = grosor
        self.pulsos   = pulsos    # cuantas veces parpadea


_DEFS: Dict[str, _DefAlerta] = {
    "golpe":    _DefAlerta((220,  50,  50), duracion=0.5, grosor=10, pulsos=2),
    "curacion": _DefAlerta(( 60, 200,  80), duracion=0.6, grosor=8,  pulsos=1),
    "apoyo":    _DefAlerta(( 60, 180, 255), duracion=0.6, grosor=8,  pulsos=1),
    "peligro":  _DefAlerta((200,  30,  30), duracion=1.0, grosor=6,  pulsos=3),
    "victoria": _DefAlerta((255, 210,  40), duracion=1.2, grosor=12, pulsos=2),
    "error":    _DefAlerta((230, 130,  30), duracion=0.4, grosor=6,  pulsos=1),
}


# ---------------------------------------------------------------------------
# Instancia de alerta activa
# ---------------------------------------------------------------------------

class _AlertaActiva:
    __slots__ = ("defn", "inicio")

    def __init__(self, defn: _DefAlerta) -> None:
        self.defn  = defn
        self.inicio = time.time()

    @property
    def expirada(self) -> bool:
        return time.time() - self.inicio >= self.defn.duracion

    def alpha(self) -> int:
        """Alpha del borde (0-255) segun progreso y pulsos."""
        progreso = (time.time() - self.inicio) / self.defn.duracion
        # Onda sinusoidal: pulsos completos en la duracion
        onda = math.sin(progreso * math.pi * self.defn.pulsos)
        # Fade-out global
        fade = 1.0 - progreso
        return max(0, min(255, int(abs(onda) * fade * 230)))


# ---------------------------------------------------------------------------
# VisualAlertSystem
# ---------------------------------------------------------------------------

class VisualAlertSystem:
    """
    Gestor de alertas visuales con borde pulsante.

    Puede haber multiples alertas activas simultaneamente.

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    activo : bool
        False desactiva todo el sistema.
    """

    MAX_ALERTAS = 4   # maximas alertas simultaneas (evitar sobrecarga visual)

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        activo: bool = True,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.activo   = activo
        self._alertas: List[_AlertaActiva] = []

    # ------------------------------------------------------------------ #
    # API publica
    # ------------------------------------------------------------------ #

    def alertar(self, tipo: str) -> None:
        """
        Dispara una alerta del tipo indicado.

        Si el tipo no esta registrado, no hace nada (no lanza excepcion).
        """
        if not self.activo:
            return
        defn = _DEFS.get(tipo)
        if defn is None:
            return
        # No acumular demasiadas alertas del mismo tipo
        mismas = sum(1 for a in self._alertas if a.defn is defn)
        if mismas >= 2:
            return
        if len(self._alertas) >= self.MAX_ALERTAS:
            self._alertas.pop(0)
        self._alertas.append(_AlertaActiva(defn))

    def registrar_tipo(
        self,
        nombre: str,
        color: Tuple[int, int, int],
        duracion: float = 0.6,
        grosor: int = 8,
        pulsos: int = 1,
    ) -> None:
        """Registra un tipo de alerta personalizado."""
        _DEFS[nombre] = _DefAlerta(color, duracion, grosor, pulsos)

    def tick(self, dt: float) -> None:
        """Elimina alertas expiradas. Llamar una vez por frame."""
        self._alertas = [a for a in self._alertas if not a.expirada]

    def draw(self, surface: "pygame.Surface", screen_scale: int = 1) -> None:
        """Dibuja los bordes pulsantes sobre *surface*."""
        if not self.activo or not _PYGAME_OK or not self._alertas:
            return

        w = surface.get_width()
        h = surface.get_height()

        for alerta in self._alertas:
            alpha = alerta.alpha()
            if alpha <= 0:
                continue

            grosor = alerta.defn.grosor * screen_scale
            color  = alerta.defn.color

            # Dibujar 4 rectangulos (bordes de la pantalla)
            borde_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            # Arriba
            pygame.draw.rect(borde_surf, (*color, alpha), (0, 0, w, grosor))
            # Abajo
            pygame.draw.rect(borde_surf, (*color, alpha), (0, h - grosor, w, grosor))
            # Izquierda
            pygame.draw.rect(borde_surf, (*color, alpha), (0, 0, grosor, h))
            # Derecha
            pygame.draw.rect(borde_surf, (*color, alpha), (w - grosor, 0, grosor, h))
            surface.blit(borde_surf, (0, 0))

    # ------------------------------------------------------------------ #
    # Atajos semanticos
    # ------------------------------------------------------------------ #

    def on_golpe(self)    -> None: self.alertar("golpe")
    def on_curacion(self) -> None: self.alertar("curacion")
    def on_apoyo(self)    -> None: self.alertar("apoyo")
    def on_peligro(self)  -> None: self.alertar("peligro")
    def on_victoria(self) -> None: self.alertar("victoria")
    def on_error(self)    -> None: self.alertar("error")

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #

    @property
    def num_activas(self) -> int:
        return len(self._alertas)

    def hay_alerta(self, tipo: str) -> bool:
        defn = _DEFS.get(tipo)
        return any(a.defn is defn for a in self._alertas)

    def tipos_disponibles(self) -> List[str]:
        return list(_DEFS.keys())
