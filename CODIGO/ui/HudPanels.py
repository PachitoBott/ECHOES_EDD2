from __future__ import annotations

from pathlib import Path
from typing import Tuple
import os

import pygame

from core.asset_paths import assets_dir as get_assets_dir


# ========================================================================
# Función global para cargar corazones desde spritesheet
# ========================================================================

def cargar_corazones(ruta: str, render_size: int = 64) -> dict:
    """
    Carga los 3 estados del corazón desde el spritesheet.

    Args:
        ruta: ruta al archivo Hearts_sprite_sheet.png (512×171)
        render_size: tamaño final del corazón escalado (default 64×64)

    Returns:
        Dict con 3 superficies escaladas: {"lleno", "medio", "vacio"}

    El spritesheet contiene 3 frames horizontales:
    - Frame 0 (0-170px): corazón lleno (rojo brillante)
    - Frame 1 (170-341px): corazón medio (partido)
    - Frame 2 (341-512px): corazón vacío (solo contorno)
    """
    try:
        sheet = pygame.image.load(ruta).convert_alpha()
    except pygame.error as e:
        print(f"Error cargando spritesheet de corazones: {e}")
        raise

    w_total = sheet.get_width()    # 512
    h_total = sheet.get_height()   # 171
    frame_w = w_total // 3         # ~170px por corazón
    frame_h = h_total              # 171px

    estados = {}
    nombres = ["lleno", "medio", "vacio"]

    for i, nombre in enumerate(nombres):
        # Extraer frame del spritesheet
        surface = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
        surface.blit(sheet, (0, 0),
                     pygame.Rect(i * frame_w, 0, frame_w, frame_h))

        # Escalar a tamaño final con scale (nearest-neighbor para pixel art nítido)
        estados[nombre] = pygame.transform.scale(
            surface, (render_size, render_size)
        )

    return estados


def get_estado_corazones(lives: int) -> list:
    """
    Convierte los puntos de vida al estado visual de cada corazón.

    Sistema de 3 corazones:
    - Cada corazón tiene 2 puntos de vida internos
    - Vida máxima = 3 corazones × 2 puntos = 6 puntos totales
    - El daño se aplica de DERECHA A IZQUIERDA
      (el corazón derecho se daña primero, el izquierdo último)

    Args:
        lives: puntos de vida actuales (0-6)

    Returns:
        Lista de 3 strings ordenados izquierda a derecha:
        [corazon_izq, corazon_centro, corazon_der]
        donde cada valor es "lleno", "medio" o "vacio"

    EJEMPLOS (daño de derecha a izquierda):
        6 vidas -> [lleno,  lleno,  lleno ]  (todos llenos)
        5 vidas -> [lleno,  lleno,  medio ]  (der pasa a medio)
        4 vidas -> [lleno,  lleno,  vacio ]  (der pasa a vacío)
        3 vidas -> [lleno,  medio,  vacio ]  (centro pasa a medio)
        2 vidas -> [lleno,  vacio,  vacio ]  (centro pasa a vacío)
        1 vida  -> [medio,  vacio,  vacio ]  (izq pasa a medio)
        0 vidas -> [vacio,  vacio,  vacio ]  (todos vacíos - GAME OVER)
    """
    # Calcular puntos de vida en cada corazón
    # Los corazones se LLENAN de izquierda a derecha al ganar vidas
    # Los corazones se VACÍAN de derecha a izquierda al perder vidas
    #
    # Distribución de vidas por corazón:
    # - Vidas 0-1:  IZQ obtiene estos puntos primero
    # - Vidas 2-3:  CENTRO obtiene estos puntos después
    # - Vidas 4-5:  DER obtiene estos puntos último
    # - Vida 6:     Todos llenan (2 cada uno)

    if lives <= 2:
        # Primeras 2 vidas van al corazón IZQUIERDO
        puntos_izq = lives
        puntos_centro = 0
        puntos_der = 0
    elif lives <= 4:
        # Siguientes 2 vidas van al corazón CENTRO
        puntos_izq = 2
        puntos_centro = lives - 2
        puntos_der = 0
    else:
        # Últimas 2 vidas van al corazón DERECHO
        puntos_izq = 2
        puntos_centro = 2
        puntos_der = lives - 4

    # Convertir puntos a estados visuales
    estados = []
    for puntos in [puntos_izq, puntos_centro, puntos_der]:
        if puntos == 2:
            estados.append("lleno")
        elif puntos == 1:
            estados.append("medio")
        else:  # puntos == 0
            estados.append("vacio")

    return estados


class HudPanels:
    """Administrador de los paneles gráficos del HUD.

    Por defecto busca tres imágenes PNG dentro de ``assets/ui`` con los nombres:

    * ``panel_inventario.png`` — marco principal para la información del jugador.
    * ``panel_minimapa.png`` — marco que "abraza" al minimapa cuadrado.
    * ``panel_esquina.png`` — adorno decorativo para la esquina inferior izquierda.

    Una vez instanciada, puedes ajustar la escala o las posiciones modificando los
    atributos públicos ``inventory_panel_position``, ``inventory_content_offset``,
    ``minimap_panel_offset`` y ``corner_panel_margin``.

    Para la escala, hay tres multiplicadores independientes:

    * :attr:`inventory_scale`
    * :attr:`minimap_scale`
    * :attr:`corner_scale`

    Usa :meth:`set_inventory_scale`, :meth:`set_minimap_scale` y
    :meth:`set_corner_scale` para recalcular cada superficie de manera
    individual, o :meth:`set_scale` para aplicar el mismo factor a los tres
    paneles a la vez.
    """

    INVENTORY_FILENAME = "panel_inventario.png"
    MINIMAP_FILENAME = "panel_minimapa.png"
    CORNER_FILENAME = "panel_esquina.png"
    CORNER_INVERSE_FILENAME = "panel_esquina_inverso.png"

    def __init__(self, *, scale: float = 1.0, assets_dir: str | Path | None = None) -> None:
        self.scale = scale
        self.assets_dir = Path(assets_dir) if assets_dir is not None else get_assets_dir("ui")

        self.inventory_scale = 0.4
        self.minimap_scale = 0.6
        self.corner_scale = 0.8

        self.inventory_panel_position = pygame.Vector2(10, 160)
        self.inventory_content_offset = pygame.Vector2(28, 36)
        self.minimap_panel_offset = pygame.Vector2(-80, 20)
        self.minimap_margin = pygame.Vector2(16, 100)
        self.minimap_anchor = "top-right"
        self.corner_panel_margin = pygame.Vector2(-70, 70)
        self.corner_inverse_panel_margin = pygame.Vector2(-120, 70)

        self._inventory_original: pygame.Surface | None = None
        self._minimap_original: pygame.Surface | None = None
        self._corner_original: pygame.Surface | None = None
        self._corner_inverse_original: pygame.Surface | None = None

        self.inventory_panel: pygame.Surface | None = None
        self.minimap_panel: pygame.Surface | None = None
        self.corner_panel: pygame.Surface | None = None
        self.corner_inverse_panel: pygame.Surface | None = None

        self._load_assets()
        self._apply_scale()

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------
    def _load_assets(self) -> None:
        self._inventory_original = self._load_surface(self.assets_dir / self.INVENTORY_FILENAME)
        self._minimap_original = self._load_surface(self.assets_dir / self.MINIMAP_FILENAME)
        self._corner_original = self._load_surface(self.assets_dir / self.CORNER_FILENAME)
        self._corner_inverse_original = self._load_surface(self.assets_dir / self.CORNER_INVERSE_FILENAME)

    def _load_surface(self, path: Path) -> pygame.Surface | None:
        try:
            surface = pygame.image.load(path.as_posix()).convert_alpha()
        except FileNotFoundError:
            print(f"[HUD] Advertencia: no se encontró la imagen '{path}'. Se usará un marcador transparente.")
            surface = None
        except pygame.error as exc:  # pragma: no cover - depende de SDL
            print(f"[HUD] Error al cargar '{path}': {exc}. Se usará un marcador transparente.")
            surface = None
        return surface

    def set_scale(self, scale: float) -> None:
        self.scale = scale
        self.inventory_scale = scale
        self.minimap_scale = scale
        self.corner_scale = scale
        self._apply_scale()

    def set_inventory_scale(self, scale: float) -> None:
        self.inventory_scale = scale
        self._apply_scale()

    def set_minimap_scale(self, scale: float) -> None:
        self.minimap_scale = scale
        self._apply_scale()

    def set_minimap_anchor(self, anchor: str, margin: Tuple[float, float] | pygame.Vector2 | None = None) -> None:
        """Define la esquina/base desde la que se posiciona el minimapa.

        ``anchor`` puede ser uno de ``"top-left"``, ``"top-right"``,
        ``"bottom-left"``, ``"bottom-right"`` o ``"corner"``. Este
        último centra el panel del minimapa dentro del panel de esquina
        (si existe) y permite aplicar un ``margin`` adicional como ajuste
        fino.
        """

        self.minimap_anchor = anchor
        if margin is not None:
            if isinstance(margin, pygame.Vector2):
                self.minimap_margin.update(margin)
            else:
                self.minimap_margin.update(*margin)

    def set_corner_scale(self, scale: float) -> None:
        self.corner_scale = scale
        self._apply_scale()

    def _apply_scale(self) -> None:
        self.inventory_panel = self._scale_surface(self._inventory_original, self.inventory_scale)
        self.minimap_panel = self._scale_surface(self._minimap_original, self.minimap_scale)
        self.corner_panel = self._scale_surface(self._corner_original, self.corner_scale)
        self.corner_inverse_panel = self._scale_surface(self._corner_inverse_original, self.corner_scale)

    def _scale_surface(self, surface: pygame.Surface | None, scale: float) -> pygame.Surface | None:
        if surface is None:
            return None
        if scale == 1.0:
            return surface.copy()
        width = max(1, int(surface.get_width() * scale))
        height = max(1, int(surface.get_height() * scale))
        return pygame.transform.smoothscale(surface, (width, height))

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def blit_inventory_panel(self, surface: pygame.Surface) -> pygame.Rect:
        panel_surface = self.inventory_panel
        position = self.inventory_panel_position
        if panel_surface is not None:
            rect = panel_surface.get_rect(topleft=(int(position.x), int(position.y)))
            surface.blit(panel_surface, rect.topleft)
        else:
            rect = pygame.Rect(int(position.x), int(position.y), 0, 0)
        return rect

    def inventory_content_anchor(self) -> Tuple[int, int]:
        """Devuelve el punto superior-izquierdo sugerido para dibujar el texto."""

        return (
            int(self.inventory_panel_position.x + self.inventory_content_offset.x),
            int(self.inventory_panel_position.y + self.inventory_content_offset.y),
        )

    def blit_minimap_panel(
        self,
        surface: pygame.Surface,
        minimap_surface: pygame.Surface,
        minimap_position: Tuple[int, int],
    ) -> pygame.Rect:
        panel_surface = self.minimap_panel
        offset = self.minimap_panel_offset
        minimap_rect = minimap_surface.get_rect(topleft=minimap_position)
        surface.blit(minimap_surface, minimap_rect.topleft)
        if panel_surface is not None:
            panel_pos = (
                minimap_rect.left + int(offset.x),
                minimap_rect.top + int(offset.y),
            )
            surface.blit(panel_surface, panel_pos)
        
        return minimap_rect

    def corner_panel_rect(self, surface: pygame.Surface) -> pygame.Rect:
        panel_surface = self.corner_panel
        if panel_surface is None:
            return pygame.Rect(0, 0, 0, 0)
        x = int(self.corner_panel_margin.x)
        y = surface.get_height() - panel_surface.get_height() - int(self.corner_panel_margin.y)
        return panel_surface.get_rect(topleft=(x, y))

    def blit_corner_panel(self, surface: pygame.Surface) -> pygame.Rect:
        rect = self.corner_panel_rect(surface)
        if rect.width and rect.height and self.corner_panel is not None:
            surface.blit(self.corner_panel, rect.topleft)
        return rect

    def corner_inverse_panel_rect(self, surface: pygame.Surface) -> pygame.Rect:
        panel_surface = self.corner_inverse_panel
        if panel_surface is None:
            return pygame.Rect(0, 0, 0, 0)
        x = surface.get_width() - panel_surface.get_width() - int(self.corner_inverse_panel_margin.x)
        y = surface.get_height() - panel_surface.get_height() - int(self.corner_inverse_panel_margin.y)
        return panel_surface.get_rect(topleft=(x, y))

    def blit_corner_inverse_panel(self, surface: pygame.Surface) -> pygame.Rect:
        rect = self.corner_inverse_panel_rect(surface)
        if rect.width and rect.height and self.corner_inverse_panel is not None:
            surface.blit(self.corner_inverse_panel, rect.topleft)
        return rect

    def compute_minimap_position(
        self,
        target_surface: pygame.Surface,
        minimap_surface: pygame.Surface,
    ) -> Tuple[int, int]:
        """Calcula la posición topleft para el minimapa según el anchor."""

        sw, sh = target_surface.get_size()
        mw, mh = minimap_surface.get_size()
        margin_x = int(self.minimap_margin.x)
        margin_y = int(self.minimap_margin.y)
        anchor = (self.minimap_anchor or "top-right").lower()

        if anchor == "top-left":
            x = margin_x
            y = margin_y
        elif anchor == "top-right":
            x = sw - mw - margin_x
            y = margin_y
        elif anchor == "bottom-left":
            x = margin_x
            y = sh - mh - margin_y
        elif anchor == "corner":
            corner_rect = self.corner_panel_rect(target_surface)
            panel_surface = self.minimap_panel
            if panel_surface is not None and corner_rect.width and corner_rect.height:
                panel_w, panel_h = panel_surface.get_size()
                offset_x = int(self.minimap_panel_offset.x)
                offset_y = int(self.minimap_panel_offset.y)
                x = corner_rect.left + (corner_rect.width - panel_w) // 2 - offset_x + margin_x
                y = corner_rect.top + (corner_rect.height - panel_h) // 2 - offset_y + margin_y
            else:
                x = sw - mw - margin_x
                y = margin_y
        else:  # bottom-right por defecto / fallback
            x = sw - mw - margin_x
            y = sh - mh - margin_y

        return (x, y)


# ========================================================================
# Nueva estructura: HUDPanel para los dos paneles de jugadores
# ========================================================================

class HUDPanel:
    """
    Panel del HUD que muestra vida y monedas de un jugador.
    El sprite del panel se carga desde un archivo PNG.
    Si el PNG no existe, muestra un rectángulo de color placeholder.
    """

    # Tamaños predeterminados (se ajustan cuando lleguen los PNGs reales)
    DEFAULT_WIDTH = 450
    DEFAULT_HEIGHT = 200
    MARGIN = 16

    # Colores para placeholders
    PLACEHOLDER_COLOR = (255, 200, 0)  # Amarillo brillante para visibility
    PLACEHOLDER_BORDER_COLOR = (255, 255, 255)  # Borde blanco

    def __init__(self, player_id: int, anchor: str,
                 panel_image_path: str | None = None,
                 screen_width: int = 960,
                 screen_height: int = 640,
                 custom_x: int | None = None,
                 custom_y: int | None = None,
                 custom_width: int | None = None,
                 custom_height: int | None = None):
        """
        Inicializa un panel de HUD para un jugador.

        Args:
            player_id: 1 o 2
            anchor: "top_left" o "bottom_left"
            panel_image_path: ruta al PNG del panel (puede ser None)
            screen_width: ancho de la pantalla lógica
            screen_height: alto de la pantalla lógica
            custom_x: posición X personalizada (sobreescribe el anchor)
            custom_y: posición Y personalizada (sobreescribe el anchor)
            custom_width: ancho personalizado (sobreescribe DEFAULT_WIDTH)
            custom_height: alto personalizado (sobreescribe DEFAULT_HEIGHT)
        """
        self.player_id = player_id
        self.anchor = anchor
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.custom_x = custom_x
        self.custom_y = custom_y
        self.panel_image = None

        # Usar tamaños personalizados si se proporcionan, sino usar defaults
        width = custom_width if custom_width is not None else self.DEFAULT_WIDTH
        height = custom_height if custom_height is not None else self.DEFAULT_HEIGHT
        self.rect = pygame.Rect(0, 0, width, height)

        if panel_image_path:
            self._cargar_panel(panel_image_path)

        self._actualizar_posicion()

    def _cargar_panel(self, path: str) -> None:
        """Carga el PNG del panel y lo redimensiona al tamaño estándar."""
        if path and os.path.exists(path):
            try:
                self.panel_image = pygame.image.load(path).convert_alpha()
                # Redimensionar imagen al tamaño estándar (240x80)
                self.panel_image = pygame.transform.smoothscale(
                    self.panel_image,
                    (self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
                )
            except pygame.error:
                self.panel_image = None

    def _actualizar_posicion(self) -> None:
        """Actualiza la posición del panel según el anchor o custom_x/custom_y."""
        # Posición X
        if self.custom_x is not None:
            self.rect.x = self.custom_x
        elif self.anchor == "top_left":
            self.rect.x = self.MARGIN
        else:
            # Default: top_left
            self.rect.x = self.MARGIN

        # Posición Y
        if self.custom_y is not None:
            self.rect.y = self.custom_y
        elif self.anchor == "top_left":
            self.rect.y = self.MARGIN
        elif self.anchor == "bottom_left":
            self.rect.y = self.screen_height - self.rect.height - self.MARGIN
        else:
            # Default: top_left
            self.rect.y = self.MARGIN

    def render(self, surface: pygame.Surface, player_data: dict) -> pygame.Rect:
        """
        Dibuja el panel completo: PNG de fondo + corazones de vida + monedas.

        Args:
            surface: superficie donde dibujar
            player_data: {
                "health": int,          # vidas actuales (0-6)
                "max_health": int,      # vidas máximas (6)
                "coins": int            # monedas/microchips
            }

        Returns:
            El rect ocupado por el panel
        """
        # 1. Fondo (PNG del panel o placeholder)
        self._dibujar_fondo(surface)

        # 2. Corazones de vida (3 corazones, daño de derecha a izquierda)
        lives = player_data.get("health", 6)
        self._render_corazones(surface, lives)

        # 3. Monedas (TODO: implementar después)
        # coins = player_data.get("coins", 0)
        # self._render_monedas(surface, coins)

        return self.rect

    def _dibujar_fondo(self, surface: pygame.Surface) -> None:
        """Dibuja el PNG del panel o un rectángulo placeholder."""
        if self.panel_image:
            surface.blit(self.panel_image, self.rect)
        else:
            # Placeholder temporal: rectángulo de color
            pygame.draw.rect(surface, self.PLACEHOLDER_COLOR, self.rect)
            pygame.draw.rect(surface, self.PLACEHOLDER_BORDER_COLOR, self.rect, 2)

    def _render_corazones(self, surface: pygame.Surface, lives: int) -> None:
        """
        Renderiza los 3 corazones dentro del panel.

        Args:
            surface: superficie donde dibujar
            lives: puntos de vida actuales (0-6)

        Los corazones se renderizan de izquierda a derecha.
        El daño ocurre de derecha a izquierda (corazón derecho se daña primero).
        """
        # Cargar corazones una sola vez (en caché global)
        if not hasattr(self, '_corazones_cargados'):
            global _CORAZONES_CACHE
            if '_CORAZONES_CACHE' not in globals():
                _CORAZONES_CACHE = cargar_corazones(
                    "CODIGO/assets/ui/Hearts_sprite_sheet.png",
                    render_size=64
                )
            self._corazones_cargados = _CORAZONES_CACHE

        corazones = self._corazones_cargados

        # Obtener los estados de los 3 corazones
        estados = get_estado_corazones(lives)

        # Configuración de posicionamiento
        CORAZON_W = 64
        CORAZON_H = 64
        GAP = 8         # separación entre corazones (píxeles)
        OFFSET_X = 20   # margen izquierdo dentro del panel
        OFFSET_Y = 15   # margen superior dentro del panel

        # Renderizar los 3 corazones (izquierda a derecha)
        for i, estado in enumerate(estados):
            sprite = corazones[estado]
            x = int(self.rect.x + OFFSET_X + i * (CORAZON_W + GAP))
            y = int(self.rect.y + OFFSET_Y)
            surface.blit(sprite, (x, y))

    def set_panel_image(self, path: str) -> None:
        """
        Permite cambiar el PNG del panel en caliente.
        Llamar cuando lleguen los archivos PNG reales.
        """
        self._cargar_panel(path)
        self._actualizar_posicion()

    def actualizar_tamaño_pantalla(self, screen_width: int, screen_height: int) -> None:
        """Actualiza el tamaño de la pantalla y reposiciona el panel."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._actualizar_posicion()
