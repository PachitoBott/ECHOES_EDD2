"""
narrative/npc.py
================
Entidad NPC interactiva para Echoes.

Responsabilidades:
  - Posicion en el mundo del dungeon.
  - Detectar cuando el jugador esta cerca (radio de interaccion).
  - Dibujarse sobre la superficie del juego.
  - Disparar el DialogueSystem cuando el jugador interactua.

Uso desde Game.py::

    alex = NPC(
        nombre="Alex",
        id_arbol="alex",
        tile_x=5, tile_y=3,
        tile_size=32,
        dialogue_system=ds,
    )

    # Game loop:
    alex.update(player_tile_x, player_tile_y, estado_juego)
    alex.draw(surface, camara_x, camara_y, screen_scale)

    # Interaccion (tecla E o similar):
    if alex.puede_interactuar and not ds.activo:
        alex.interactuar(estado_juego)
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import pygame
    _PYGAME_DISPONIBLE = True
except ImportError:
    _PYGAME_DISPONIBLE = False

from narrative.dialogue_system import DialogueSystem


# ---------------------------------------------------------------------------
# Colores y constantes visuales
# ---------------------------------------------------------------------------

_COL_NPC_CUERPO   = (80, 160, 230)
_COL_NPC_BORDE    = (200, 230, 255)
_COL_INTERACCION  = (255, 255, 100, 180)   # RGBA
_COL_NOMBRE_BG    = (10, 15, 35, 200)
_COL_NOMBRE_TEXT  = (180, 220, 255)
_COL_HINT_TEXT    = (220, 220, 100)

_RADIO_INTERACCION = 2.0    # distancia en tiles para poder hablar


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------

class NPC:
    """
    Personaje no jugador con dialogo y representacion visual.

    Parametros
    ----------
    nombre : str
        Nombre del NPC (se muestra sobre el sprite).
    id_arbol : str
        ID del ArbolDialogo en el DialogueSystem.
    tile_x, tile_y : int
        Posicion en coordenadas de tiles del dungeon.
    tile_size : int
        Tamano de cada tile en pixeles logicos.
    dialogue_system : DialogueSystem
        Instancia del sistema de dialogos compartida con el juego.
    callback_fin : callable | None
        Funcion opcional que se llama cuando el dialogo termina.
    sprite_color : tuple
        Color RGB del sprite (circulo) del NPC.
    """

    def __init__(
        self,
        nombre: str,
        id_arbol: str,
        tile_x: int,
        tile_y: int,
        tile_size: int,
        dialogue_system: DialogueSystem,
        callback_fin: Optional[Callable[[], None]] = None,
        sprite_color: Tuple[int, int, int] = _COL_NPC_CUERPO,
    ) -> None:
        self.nombre           = nombre
        self.id_arbol         = id_arbol
        self.tile_x           = tile_x
        self.tile_y           = tile_y
        self.tile_size        = tile_size
        self._ds              = dialogue_system
        self._callback_fin    = callback_fin
        self._sprite_color    = sprite_color

        # Estado
        self._puede_interactuar = False
        self._ya_hablo_hoy      = False    # se resetea por NarrativeManager
        self._visible           = True
        self._anim_timer        = 0.0      # para animacion de flotacion

        # Fuente (inicializada lazy)
        self._font: Any = None

    # ------------------------------------------------------------------ #
    # Propiedades
    # ------------------------------------------------------------------ #

    @property
    def puede_interactuar(self) -> bool:
        return self._puede_interactuar and self._visible

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, v: bool) -> None:
        self._visible = v

    def resetear_dialogo(self) -> None:
        """Permite que el NPC sea hablado de nuevo (usar entre etapas)."""
        self._ya_hablo_hoy = False

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    def update(
        self,
        player_tile_x: float,
        player_tile_y: float,
        estado_juego: Optional[Dict[str, Any]] = None,
        dt: float = 0.0,
    ) -> None:
        """
        Actualiza el estado del NPC cada frame.

        Parametros
        ----------
        player_tile_x, player_tile_y : float
            Posicion actual del jugador en tiles.
        estado_juego : dict | None
            Estado del juego (para pasarlo al dialogo al interactuar).
        dt : float
            Delta de tiempo en segundos (para animaciones).
        """
        if not self._visible:
            self._puede_interactuar = False
            return

        # Distancia al jugador
        dx = player_tile_x - self.tile_x
        dy = player_tile_y - self.tile_y
        dist = math.sqrt(dx * dx + dy * dy)
        self._puede_interactuar = dist <= _RADIO_INTERACCION

        # Animacion de flotacion
        self._anim_timer = (self._anim_timer + dt) % (2 * math.pi)

    def interactuar(
        self,
        estado_juego: Optional[Dict[str, Any]] = None,
        nombre_npc: Optional[str] = None,
    ) -> bool:
        """
        Inicia la conversacion con este NPC.

        Retorna True si el dialogo comenzo.
        """
        if not self._puede_interactuar or not self._visible:
            return False

        ok = self._ds.iniciar(
            id_arbol=self.id_arbol,
            nombre_npc=nombre_npc or self.nombre,
            estado_juego=estado_juego or {},
            callback_fin=self._callback_fin,
        )
        if ok:
            self._ya_hablo_hoy = True
        return ok

    # ------------------------------------------------------------------ #
    # Draw
    # ------------------------------------------------------------------ #

    def draw(
        self,
        surface: "pygame.Surface",
        cam_x: int = 0,
        cam_y: int = 0,
        screen_scale: int = 1,
    ) -> None:
        """
        Dibuja el NPC en *surface*.

        Parametros
        ----------
        surface     : superficie de pantalla.
        cam_x, cam_y: desplazamiento de la camara en pixeles logicos.
        screen_scale: factor de escala.
        """
        if not self._visible or not _PYGAME_DISPONIBLE:
            return

        ts = self._tile_size_real(screen_scale)

        # Posicion en pantalla
        px = int((self.tile_x * self.tile_size - cam_x) * screen_scale)
        py = int((self.tile_y * self.tile_size - cam_y) * screen_scale)

        # Flotacion animada (+/- 3 pixeles)
        py += int(math.sin(self._anim_timer) * 3 * screen_scale)

        radio = max(4, ts // 2 - 2)

        # Circulo del NPC
        pygame.draw.circle(surface, self._sprite_color, (px + ts // 2, py + ts // 2), radio)
        pygame.draw.circle(surface, _COL_NPC_BORDE,    (px + ts // 2, py + ts // 2), radio, 2)

        # Nombre flotante
        if self._font is None:
            self._font = pygame.font.SysFont(None, max(10, int(11 * screen_scale)))

        nombre_surf = self._font.render(self.nombre, True, _COL_NOMBRE_TEXT)
        nx = px + ts // 2 - nombre_surf.get_width() // 2
        ny = py - nombre_surf.get_height() - int(4 * screen_scale)

        # Fondo del nombre
        bg = pygame.Surface(
            (nombre_surf.get_width() + int(6 * screen_scale),
             nombre_surf.get_height() + int(4 * screen_scale)),
            pygame.SRCALPHA,
        )
        bg.fill(_COL_NOMBRE_BG)
        surface.blit(bg, (nx - int(3 * screen_scale), ny - int(2 * screen_scale)))
        surface.blit(nombre_surf, (nx, ny))

        # Indicador de interaccion
        if self._puede_interactuar and not self._ds.activo:
            hint_font = pygame.font.SysFont(None, max(8, int(10 * screen_scale)))
            hint = hint_font.render("[E] Hablar", True, _COL_HINT_TEXT)
            hx = px + ts // 2 - hint.get_width() // 2
            hy = py - nombre_surf.get_height() - hint.get_height() - int(8 * screen_scale)
            surface.blit(hint, (hx, hy))

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _tile_size_real(self, screen_scale: int) -> int:
        return self.tile_size * screen_scale

    def posicion_pixel(self, cam_x: int, cam_y: int, screen_scale: int) -> Tuple[int, int]:
        """Retorna la posicion en pixeles reales del centro del NPC."""
        ts = self._tile_size_real(screen_scale)
        px = int((self.tile_x * self.tile_size - cam_x) * screen_scale) + ts // 2
        py = int((self.tile_y * self.tile_size - cam_y) * screen_scale) + ts // 2
        return (px, py)
