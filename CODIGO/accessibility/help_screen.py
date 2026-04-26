"""
accessibility/help_screen.py
==============================
Pantalla de ayuda superpuesta para Echoes.

Muestra:
  - Controles del teclado.
  - Descripcion de armas / habilidades.
  - Objetivo del juego (contextual segun etapa).
  - Informacion de accesibilidad.

Uso desde Game.py::

    ayuda = HelpScreen(screen_w=960, screen_h=640)

    # Toggle con F1:
    if event.key == pygame.K_F1:
        ayuda.toggle()

    # Game loop (consume input mientras esta visible):
    if ayuda.visible:
        consumido = ayuda.handle_event(evento)
        ayuda.draw(surface, screen_scale=2)
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False


# ---------------------------------------------------------------------------
# Colores
# ---------------------------------------------------------------------------

_COL_BG        = (8, 12, 28, 230)    # RGBA
_COL_TITULO    = (100, 200, 255)
_COL_SECCION   = (180, 220, 255)
_COL_TEXTO     = (210, 210, 220)
_COL_TECLA_BG  = (40, 55, 90)
_COL_TECLA     = (230, 200, 100)
_COL_BORDE     = (80, 120, 200)
_COL_SEPARADOR = (50, 70, 130)


# ---------------------------------------------------------------------------
# Contenido de ayuda
# ---------------------------------------------------------------------------

_SECCIONES = [
    {
        "titulo": "CONTROLES",
        "items": [
            ("[WASD / Flechas]",  "Mover al personaje"),
            ("[Q]",               "Usar arma 1 (Bloqueo)"),
            ("[W]",               "Usar arma 2 (Reporte)"),
            ("[E]",               "Hablar con NPC cercano"),
            ("[F1]",              "Abrir / cerrar esta ayuda"),
            ("[Esc]",             "Saltar cinematica / cerrar menu"),
            ("[1-9]",             "Elegir opcion de dialogo"),
            ("[Espacio]",         "Avanzar dialogo"),
        ],
    },
    {
        "titulo": "ARMAS",
        "items": [
            ("Bloqueo",    "Corta el contacto con un acosador. Daño moderado."),
            ("Reporte",    "Llama la atencion de la plataforma. Daño alto."),
            ("Evidencia",  "Documentas el acoso. Potencia los ataques futuros."),
            ("Apoyo",      "El aliado te da fuerza. Restaura algo de salud."),
        ],
    },
    {
        "titulo": "OBJETIVO",
        "items": [
            ("Etapa 1", "Explora el dungeon. Habla con Alex para consejos."),
            ("Etapa 2", "El acoso escala. Bloquea y reporta mas rapido."),
            ("Etapa 3", "Derrota al Coordinador del odio usando evidencia."),
            ("Final",   "Presentar evidencias y sobrevivir = victoria."),
        ],
    },
    {
        "titulo": "ACCESIBILIDAD",
        "items": [
            ("Subtitulos",     "Texto en pantalla para cada evento sonoro."),
            ("Alertas visuales", "Bordes de color como indicadores auditivos."),
            ("Paleta de color", "Modos para daltonismo y alto contraste."),
            ("Textos grandes",  "Aumenta el tamanio de fuente en Config.py."),
        ],
    },
]


# ---------------------------------------------------------------------------
# HelpScreen
# ---------------------------------------------------------------------------

class HelpScreen:
    """
    Pantalla de ayuda superpuesta (overlay).

    Se puede abrir/cerrar con toggle() o visible directamente.

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    font_size : int
        Tamanio de fuente base.
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        font_size: int = 13,
    ) -> None:
        self.screen_w  = screen_w
        self.screen_h  = screen_h
        self._font_size = font_size
        self._visible   = False

        self._font: Any = None
        self._font_titulo: Any = None
        self._font_seccion: Any = None
        self._fuentes_listas = False

        # Scroll
        self._scroll_y  = 0
        self._max_scroll = 0

    # ------------------------------------------------------------------ #
    # Control
    # ------------------------------------------------------------------ #

    def toggle(self) -> None:
        """Abre si cerrado, cierra si abierto."""
        self._visible = not self._visible
        if self._visible:
            self._scroll_y = 0

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, v: bool) -> None:
        self._visible = v

    def cerrar(self) -> None:
        self._visible = False

    # ------------------------------------------------------------------ #
    # Input
    # ------------------------------------------------------------------ #

    def handle_event(self, event: "pygame.event.Event") -> bool:
        """
        Procesa eventos mientras la ayuda esta visible.

        Retorna True si el evento fue consumido.
        """
        if not self._visible or not _PYGAME_OK:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_F1):
                self.cerrar()
                return True
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self._scroll_y = min(self._scroll_y + 20, self._max_scroll)
                return True
            if event.key in (pygame.K_UP, pygame.K_w):
                self._scroll_y = max(self._scroll_y - 20, 0)
                return True

        if event.type == pygame.MOUSEWHEEL:
            self._scroll_y = max(0, min(
                self._scroll_y - event.y * 15,
                self._max_scroll
            ))
            return True

        return True   # mientras la ayuda este abierta, consume todo

    # ------------------------------------------------------------------ #
    # Draw
    # ------------------------------------------------------------------ #

    def draw(self, surface: "pygame.Surface", screen_scale: int = 1) -> None:
        """Dibuja la pantalla de ayuda sobre *surface*."""
        if not self._visible or not _PYGAME_OK:
            return

        self._init_fuentes()
        w = surface.get_width()
        h = surface.get_height()
        m = int(20 * screen_scale)

        # Fondo semitransparente
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill(_COL_BG)
        surface.blit(bg, (0, 0))

        # Borde
        pygame.draw.rect(surface, _COL_BORDE, (m // 2, m // 2, w - m, h - m), 2)

        # ---- Titulo ----
        titulo = self._font_titulo.render("AYUDA — ECHOES", True, _COL_TITULO)
        surface.blit(titulo, (m, m))
        cierre = self._font.render("[F1 / Esc] Cerrar  |  [↑↓] Scroll", True, _COL_SEPARADOR)
        surface.blit(cierre, (w - cierre.get_width() - m, m))

        y = m + titulo.get_height() + int(10 * screen_scale) - self._scroll_y
        contenido_start = y + self._scroll_y   # para calcular max_scroll

        # ---- Secciones ----
        col_ancho = (w - 2 * m - int(20 * screen_scale)) // 2
        col2_x    = m + col_ancho + int(20 * screen_scale)

        total_contenido = 0
        for i, seccion in enumerate(_SECCIONES):
            col_x = m if i % 2 == 0 else col2_x
            if i == 2:                             # segunda fila de secciones
                y_sec = contenido_start + int(total_contenido * 0.5)
            else:
                y_sec = y

            # Titulo de seccion
            s_tit = self._font_seccion.render(seccion["titulo"], True, _COL_SECCION)
            pygame.draw.line(
                surface, _COL_SEPARADOR,
                (col_x, y_sec + s_tit.get_height() + 2),
                (col_x + col_ancho, y_sec + s_tit.get_height() + 2), 1
            )
            surface.blit(s_tit, (col_x, y_sec))
            y_item = y_sec + s_tit.get_height() + int(8 * screen_scale)

            for tecla, desc in seccion["items"]:
                # Tecla / etiqueta
                tecla_surf = self._font.render(tecla, True, _COL_TECLA)
                tk_bg = pygame.Surface(
                    (tecla_surf.get_width() + int(6 * screen_scale),
                     tecla_surf.get_height() + int(2 * screen_scale)),
                    pygame.SRCALPHA,
                )
                tk_bg.fill((*_COL_TECLA_BG, 200))
                surface.blit(tk_bg, (col_x, y_item))
                surface.blit(tecla_surf, (col_x + int(3 * screen_scale), y_item + int(1 * screen_scale)))

                # Descripcion
                desc_x = col_x + tecla_surf.get_width() + int(12 * screen_scale)
                desc_surf = self._font.render(desc, True, _COL_TEXTO)
                surface.blit(desc_surf, (desc_x, y_item))

                y_item += tecla_surf.get_height() + int(5 * screen_scale)

            total_contenido = max(total_contenido, y_item - y)

        self._max_scroll = max(0, total_contenido - h + 2 * m)

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _init_fuentes(self) -> None:
        if self._fuentes_listas:
            return
        self._font         = pygame.font.SysFont(None, self._font_size)
        self._font_titulo  = pygame.font.SysFont(None, self._font_size + 8)
        self._font_seccion = pygame.font.SysFont(None, self._font_size + 2)
        self._fuentes_listas = True
