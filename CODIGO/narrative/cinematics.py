"""
narrative/cinematics.py
=======================
Sistema de cinematicas para Echoes.

Responsabilidades:
  - Cargar secuencias de paneles desde cinematics.json.
  - Renderizar cada panel con fade-in / fade-out usando pygame.
  - Exponer una API sencilla que el game loop puede llamar sin bloquearse:

        cs = CinematicSystem(screen_w, screen_h)
        cs.reproducir("intro")

        # en el game loop:
        if cs.activo:
            cs.tick(dt)
            cs.draw(surface, screen_scale)
            # (bloquea el input del juego mientras dura)

Formato del JSON (cinematics.json):
  {
    "intro": {
      "id": "intro",
      "etapa": 0,
      "paneles": [
        {
          "texto":       "...",
          "duracion":    3.5,          # segundos visibles (sin contar fades)
          "color_fondo": [R, G, B],
          "color_texto": [R, G, B],
          "fade_in":     1.0,          # segundos de fade-in
          "fade_out":    0.8,          # segundos de fade-out
          "subtitulo":   "opcional"    # linea secundaria mas pequena
        },
        ...
      ]
    },
    ...
  }

Sin librerias externas — solo pygame de la stdlib del proyecto.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import pygame
    _PYGAME_DISPONIBLE = True
except ImportError:                 # entorno de tests sin pygame
    _PYGAME_DISPONIBLE = False


# ---------------------------------------------------------------------------
# Panel de cinematica (modelo de datos)
# ---------------------------------------------------------------------------

class _Panel:
    """Un cuadro de texto dentro de una secuencia cinematica."""

    __slots__ = (
        "texto", "duracion", "color_fondo", "color_texto",
        "fade_in", "fade_out", "subtitulo",
    )

    def __init__(
        self,
        texto: str,
        duracion: float,
        color_fondo: Tuple[int, int, int],
        color_texto: Tuple[int, int, int],
        fade_in: float = 1.0,
        fade_out: float = 0.8,
        subtitulo: str = "",
    ) -> None:
        self.texto       = texto
        self.duracion    = duracion
        self.color_fondo = color_fondo
        self.color_texto = color_texto
        self.fade_in     = max(0.0, fade_in)
        self.fade_out    = max(0.0, fade_out)
        self.subtitulo   = subtitulo

    @classmethod
    def desde_dict(cls, d: Dict[str, Any]) -> "_Panel":
        cf = d.get("color_fondo", [8, 12, 28])
        ct = d.get("color_texto", [220, 220, 220])
        return cls(
            texto=d.get("texto", ""),
            duracion=float(d.get("duracion", 3.0)),
            color_fondo=(int(cf[0]), int(cf[1]), int(cf[2])),
            color_texto=(int(ct[0]), int(ct[1]), int(ct[2])),
            fade_in=float(d.get("fade_in", 1.0)),
            fade_out=float(d.get("fade_out", 0.8)),
            subtitulo=d.get("subtitulo", ""),
        )


# ---------------------------------------------------------------------------
# Secuencia cinematica
# ---------------------------------------------------------------------------

class Cinematica:
    """Coleccion de paneles que forman una cinematica."""

    def __init__(self, id_: str, etapa: int, paneles: List[_Panel]) -> None:
        self.id     = id_
        self.etapa  = etapa
        self.paneles: List[_Panel] = paneles

    @classmethod
    def desde_dict(cls, d: Dict[str, Any]) -> "Cinematica":
        paneles = [_Panel.desde_dict(p) for p in d.get("paneles", [])]
        return cls(
            id_=d.get("id", ""),
            etapa=int(d.get("etapa", 0)),
            paneles=paneles,
        )

    @property
    def duracion_total(self) -> float:
        return sum(p.fade_in + p.duracion + p.fade_out for p in self.paneles)


# ---------------------------------------------------------------------------
# CinematicSystem
# ---------------------------------------------------------------------------

class CinematicSystem:
    """
    Gestor de cinematicas integrado con el game loop.

    Uso desde Game.py::

        cs = CinematicSystem(960, 640)
        cs.cargar_json("narrative/data/cinematics.json")

        # Reproducir:
        cs.reproducir("intro", callback_fin=lambda: ...)

        # Game loop:
        if cs.activo:
            cs.tick(dt)
            cs.draw(surface, screen_scale=2)

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    font_size : int
        Tamanio de la fuente del texto principal.
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        font_size: int = 22,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._font_size = font_size

        self._cinematicas: Dict[str, Cinematica] = {}

        # Estado de reproduccion
        self._activo            = False
        self._cinem_actual: Optional[Cinematica] = None
        self._panel_idx         = 0
        self._tiempo_panel      = 0.0   # segundos transcurridos en este panel
        self._callback_fin: Optional[Callable[[], None]] = None

        # Fuentes (inicializadas cuando se necesitan si pygame esta disponible)
        self._font: Any = None
        self._font_sub: Any = None
        self._fuentes_listas = False

    # ------------------------------------------------------------------ #
    # Carga
    # ------------------------------------------------------------------ #

    def cargar_json(self, ruta: str | Path) -> None:
        """Carga todas las cinematicas del archivo JSON."""
        ruta = Path(ruta)
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        for key, val in data.items():
            cinem = Cinematica.desde_dict(val)
            self._cinematicas[key] = cinem

    def registrar(self, id_: str, cinematica: Cinematica) -> None:
        """Registra una cinematica ya construida."""
        self._cinematicas[id_] = cinematica

    # ------------------------------------------------------------------ #
    # Control
    # ------------------------------------------------------------------ #

    def reproducir(
        self,
        id_cinematica: str,
        callback_fin: Optional[Callable[[], None]] = None,
    ) -> bool:
        """
        Inicia la reproduccion de una cinematica.

        Retorna True si la cinematica existe, False si no.
        """
        cinem = self._cinematicas.get(id_cinematica)
        if cinem is None or not cinem.paneles:
            return False

        self._cinem_actual = cinem
        self._panel_idx    = 0
        self._tiempo_panel = 0.0
        self._activo       = True
        self._callback_fin = callback_fin
        return True

    def saltar(self) -> None:
        """El jugador presiono Skip — termina inmediatamente."""
        self._finalizar()

    @property
    def activo(self) -> bool:
        return self._activo

    def cinematica_actual_id(self) -> Optional[str]:
        return self._cinem_actual.id if self._cinem_actual else None

    # ------------------------------------------------------------------ #
    # Game loop
    # ------------------------------------------------------------------ #

    def tick(self, dt: float) -> None:
        """
        Avanza el tiempo del panel actual.

        Debe llamarse una vez por frame mientras cs.activo sea True.
        """
        if not self._activo or self._cinem_actual is None:
            return

        paneles = self._cinem_actual.paneles
        if self._panel_idx >= len(paneles):
            self._finalizar()
            return

        panel = paneles[self._panel_idx]
        duracion_panel = panel.fade_in + panel.duracion + panel.fade_out
        self._tiempo_panel += dt

        if self._tiempo_panel >= duracion_panel:
            self._tiempo_panel -= duracion_panel
            self._panel_idx += 1
            if self._panel_idx >= len(paneles):
                self._finalizar()

    def draw(self, surface: "pygame.Surface", screen_scale: int = 1) -> None:
        """
        Dibuja el panel actual sobre *surface*.

        Calcula el alpha de fade-in / fade-out y aplica sobre el texto
        y el fondo del panel.
        """
        if not self._activo or self._cinem_actual is None:
            return
        if not _PYGAME_DISPONIBLE:
            return

        paneles = self._cinem_actual.paneles
        if self._panel_idx >= len(paneles):
            return

        panel = paneles[self._panel_idx]
        self._inicializar_fuentes()

        # ---- calcular alpha ----
        t = self._tiempo_panel
        fi = panel.fade_in
        dur = panel.duracion
        fo = panel.fade_out

        if t < fi:
            alpha = int(255 * (t / fi)) if fi > 0 else 255
        elif t < fi + dur:
            alpha = 255
        else:
            resto = t - fi - dur
            alpha = int(255 * (1.0 - resto / fo)) if fo > 0 else 0
        alpha = max(0, min(255, alpha))

        # ---- fondo de pantalla con color del panel ----
        w = surface.get_width()
        h = surface.get_height()

        fondo = pygame.Surface((w, h))
        fondo.fill(panel.color_fondo)
        fondo.set_alpha(alpha)
        surface.fill((0, 0, 0))   # negro de base
        surface.blit(fondo, (0, 0))

        # ---- texto principal ----
        cx = w // 2
        cy = h // 2

        lineas = panel.texto.split("\n")
        line_h = self._font.get_linesize()
        total_h = line_h * len(lineas)
        if panel.subtitulo:
            total_h += self._font_sub.get_linesize() + int(10 * screen_scale)

        y_start = cy - total_h // 2

        for linea in lineas:
            surf = self._font.render(linea, True, panel.color_texto)
            surf.set_alpha(alpha)
            rect = surf.get_rect(centerx=cx, y=y_start)
            surface.blit(surf, rect)
            y_start += line_h

        # ---- subtitulo ----
        if panel.subtitulo:
            y_start += int(10 * screen_scale)
            sub_col = tuple(max(0, c - 60) for c in panel.color_texto)
            surf_sub = self._font_sub.render(panel.subtitulo, True, sub_col)
            surf_sub.set_alpha(alpha)
            rect_sub = surf_sub.get_rect(centerx=cx, y=y_start)
            surface.blit(surf_sub, rect_sub)

        # ---- pista "Skip" ----
        if alpha > 60:
            hint_font = pygame.font.SysFont(None, max(12, self._font_size - 8))
            hint = hint_font.render("[Esc] Saltar", True, (120, 120, 120))
            hint.set_alpha(min(alpha, 180))
            surface.blit(hint, (int(8 * screen_scale), int(8 * screen_scale)))

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _inicializar_fuentes(self) -> None:
        if self._fuentes_listas:
            return
        self._font     = pygame.font.SysFont(None, self._font_size)
        self._font_sub = pygame.font.SysFont(None, max(12, self._font_size - 6))
        self._fuentes_listas = True

    def _finalizar(self) -> None:
        self._activo = False
        self._cinem_actual = None
        if callable(self._callback_fin):
            self._callback_fin()
            self._callback_fin = None

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #

    def ids_disponibles(self) -> List[str]:
        """Retorna los IDs de todas las cinematicas cargadas."""
        return list(self._cinematicas.keys())

    def obtener(self, id_: str) -> Optional[Cinematica]:
        return self._cinematicas.get(id_)
