"""
accessibility/subtitles.py
===========================
Sistema de subtitulos / leyendas en pantalla para Echoes.

Sustituye pistas de audio con texto en pantalla:
  - Cuando un enemigo ataca → "[GOLPE]"
  - Cuando el jugador recibe curación → "[CURACIÓN]"
  - Cuando Alex habla → texto del dialogo ya esta en DialogueBox,
    pero este modulo puede mostrar versiones resumidas fuera del cuadro.

Uso desde Game.py::

    subtitulos = SubtitleSystem(screen_w=960, screen_h=640)

    # Registrar un evento con audio (sustitucion textual):
    subtitulos.agregar("Enemigo cercano", duracion=2.0, tipo="peligro")

    # En el game loop:
    subtitulos.tick(dt)
    subtitulos.draw(surface, screen_scale=2)

Parametros de tipo (afectan el color):
  "normal"    -> blanco
  "peligro"   -> rojo
  "apoyo"     -> cian
  "curacion"  -> verde
  "sistema"   -> gris claro
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque, NamedTuple, Optional, Tuple

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False


# ---------------------------------------------------------------------------
# Paleta de colores por tipo
# ---------------------------------------------------------------------------

_COLORES_TIPO: dict[str, Tuple[int, int, int]] = {
    "normal":   (230, 230, 230),
    "peligro":  (255,  80,  80),
    "apoyo":    (100, 220, 255),
    "curacion": ( 80, 230, 130),
    "sistema":  (170, 170, 190),
    "victoria": (255, 220,  60),
}

_COL_BG     = (0, 0, 0, 140)    # RGBA
_MARGEN     = 10
_SEPARACION = 4                  # pixeles entre lineas (logicos)
_MAX_LINEAS = 5                  # maximo de subtitulos visibles a la vez


# ---------------------------------------------------------------------------
# Entrada de subtitulo
# ---------------------------------------------------------------------------

class _Subtitulo(NamedTuple):
    texto:    str
    tipo:     str
    duracion: float   # segundos totales
    creado:   float   # timestamp de creacion


# ---------------------------------------------------------------------------
# SubtitleSystem
# ---------------------------------------------------------------------------

class SubtitleSystem:
    """
    Cola de subtitulos con tiempo de vida individual.

    Los subtitulos mas nuevos aparecen abajo; los expirados desaparecen.

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    font_size : int
        Tamanio de la fuente.
    pos : str
        "bottom"  → alineados al fondo (por defecto)
        "top"     → alineados arriba
    activo : bool
        False desactiva todo (sin draw, sin agregar).
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        font_size: int = 13,
        pos: str = "bottom",
        activo: bool = True,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._font_size = font_size
        self._pos       = pos
        self.activo     = activo

        self._cola: Deque[_Subtitulo] = deque(maxlen=_MAX_LINEAS * 2)
        self._font = None
        self._font_listo = False

    # ------------------------------------------------------------------ #
    # API publica
    # ------------------------------------------------------------------ #

    def agregar(
        self,
        texto: str,
        duracion: float = 3.0,
        tipo: str = "normal",
    ) -> None:
        """
        Agrega un subtitulo a la cola.

        Parametros
        ----------
        texto    : texto a mostrar.
        duracion : segundos visibles.
        tipo     : "normal" | "peligro" | "apoyo" | "curacion" | "sistema" | "victoria"
        """
        if not self.activo:
            return
        sub = _Subtitulo(texto=texto, tipo=tipo, duracion=duracion, creado=time.time())
        self._cola.append(sub)

    def tick(self, dt: float) -> None:
        """Elimina subtitulos expirados. Llamar una vez por frame."""
        if not self.activo:
            return
        ahora = time.time()
        while self._cola and ahora - self._cola[0].creado >= self._cola[0].duracion:
            self._cola.popleft()

    def limpiar(self) -> None:
        """Elimina todos los subtitulos activos."""
        self._cola.clear()

    def draw(self, surface: "pygame.Surface", screen_scale: int = 1) -> None:
        """
        Dibuja los subtitulos activos sobre *surface*.

        No dibuja nada si no hay pygame disponible o si self.activo es False.
        """
        if not self.activo or not _PYGAME_OK or not self._cola:
            return

        self._init_font()
        activos = list(self._cola)[-_MAX_LINEAS:]   # los mas recientes

        m      = _MARGEN * screen_scale
        line_h = self._font.get_linesize() + _SEPARACION * screen_scale
        total_h = line_h * len(activos)

        if self._pos == "bottom":
            y_start = surface.get_height() - m - total_h - int(8 * screen_scale)
        else:
            y_start = m

        for sub in activos:
            color = _COLORES_TIPO.get(sub.tipo, _COLORES_TIPO["normal"])

            # Calcular alpha segun tiempo restante (fade-out en el ultimo 0.5s)
            transcurrido = time.time() - sub.creado
            restante     = sub.duracion - transcurrido
            alpha = 255
            if restante < 0.5:
                alpha = max(0, int(255 * restante / 0.5))

            surf = self._font.render(sub.texto, True, color)
            surf.set_alpha(alpha)

            # Fondo translucido
            bg = pygame.Surface(
                (surf.get_width() + int(6 * screen_scale),
                 surf.get_height() + int(4 * screen_scale)),
                pygame.SRCALPHA,
            )
            bg.fill(_COL_BG)
            bg.set_alpha(min(alpha, 140))

            bx = m
            by = y_start
            surface.blit(bg, (bx, by - int(2 * screen_scale)))
            surface.blit(surf, (bx + int(3 * screen_scale), by))
            y_start += line_h

    # ------------------------------------------------------------------ #
    # Atajos semanticos (para disparar desde el juego sin recordar strings)
    # ------------------------------------------------------------------ #

    def golpe(self, agente: str = "Enemigo") -> None:
        self.agregar(f"[{agente.upper()} ATACÓ]", duracion=1.5, tipo="peligro")

    def curacion(self, cantidad: int = 0) -> None:
        txt = f"[CURACIÓN +{cantidad} HP]" if cantidad else "[CURACIÓN]"
        self.agregar(txt, duracion=2.0, tipo="curacion")

    def apoyo_recibido(self, tipo: str = "") -> None:
        txt = f"[APOYO: {tipo.upper()}]" if tipo else "[APOYO RECIBIDO]"
        self.agregar(txt, duracion=2.0, tipo="apoyo")

    def peligro(self, msg: str = "Cuidado") -> None:
        self.agregar(f"[PELIGRO: {msg}]", duracion=2.5, tipo="peligro")

    def sistema(self, msg: str) -> None:
        self.agregar(msg, duracion=3.0, tipo="sistema")

    def victoria(self) -> None:
        self.agregar("[VICTORIA]", duracion=4.0, tipo="victoria")

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _init_font(self) -> None:
        if self._font_listo:
            return
        self._font = pygame.font.SysFont(None, self._font_size)
        self._font_listo = True

    @property
    def num_activos(self) -> int:
        """Numero de subtitulos actualmente en cola."""
        return len(self._cola)
