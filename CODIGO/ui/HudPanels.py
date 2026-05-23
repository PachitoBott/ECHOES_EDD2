from __future__ import annotations

from pathlib import Path
from typing import Tuple
import os

import pygame

from core.asset_paths import assets_dir as get_assets_dir


# ========================================================================
# Función global para cargar corazones desde spritesheet
# ========================================================================

def cargar_corazones(ruta: str, render_size: int | None = None) -> dict:
    """
    Carga los 3 estados del corazón desde el spritesheet.

    Args:
        ruta: ruta al archivo corazones.png (120×20 para 5 corazones, o 72×20 para 3)
        render_size: NO SE USA - los corazones se cargan en tamaño raw (24×20)

    Returns:
        Dict con 3 superficies sin escalar: {"lleno", "medio", "vacio"}

    El spritesheet contiene 3 frames horizontales:
    - Frame 0 (0-23px): corazón lleno (rojo brillante)
    - Frame 1 (24-47px): corazón medio (partido)
    - Frame 2 (48-71px): corazón vacío (solo contorno)
    Cada frame es exactamente 24×20 píxeles (SIN ESCALAR)
    """
    try:
        sheet = pygame.image.load(ruta).convert_alpha()
    except pygame.error as e:
        print(f"Error cargando spritesheet de corazones: {e}")
        raise

    w_total = sheet.get_width()    # 120 (para 5 corazones) o 72 (para 3)
    h_total = sheet.get_height()   # 20
    frame_w = 24                   # 24px por frame (ancho fijo)
    frame_h = h_total              # 20px

    estados = {}
    nombres = ["lleno", "medio", "vacio"]

    for i, nombre in enumerate(nombres):
        # Extraer frame del spritesheet (sin escalar - raw size 24×20)
        surface = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
        surface.blit(sheet, (0, 0),
                     pygame.Rect(i * frame_w, 0, frame_w, frame_h))

        # NO escalar - usar tamaño raw
        estados[nombre] = surface

    return estados


def cargar_iconos_poderes(ruta: str) -> dict:
    """
    Carga los 4 iconos de poderes desde el spritesheet.

    Args:
        ruta: ruta al archivo iconos_pwr.png (formato: 4 iconos en fila horizontal)

    Returns:
        Dict con 4 superficies escaladas a 28×28: {
            "red_apoyo": Surface,      # Index 0 - Green cross
            "modo_privado": Surface,   # Index 1 - Blue eye
            "emp": Surface,            # Index 2 - Yellow lightning
            "eco_señal": Surface       # Index 3 - Red double book
        }

    El spritesheet contiene 4 frames horizontales, cada uno será
    escalado a 28×28 píxeles para su uso en el HUD.
    """
    try:
        sheet = pygame.image.load(ruta).convert_alpha()
    except pygame.error as e:
        print(f"Error cargando spritesheet de iconos: {e}")
        raise

    w_total = sheet.get_width()
    h_total = sheet.get_height()
    frame_w = w_total // 4  # 4 iconos en horizontal
    frame_h = h_total

    iconos = {}
    nombres = ["red_apoyo", "modo_privado", "emp", "eco_señal"]

    for i, nombre in enumerate(nombres):
        # Extraer frame del spritesheet
        surface = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
        surface.blit(sheet, (0, 0),
                     pygame.Rect(i * frame_w, 0, frame_w, frame_h))

        # Escalar a 28×28 píxeles
        scaled = pygame.transform.scale(surface, (28, 28))
        iconos[nombre] = scaled

    return iconos


def get_estado_corazones(lives: int) -> list:
    """
    Convierte los puntos de vida al estado visual de cada corazón.

    Sistema de 5 corazones:
    - Cada corazón tiene 2 puntos de vida internos
    - Vida máxima = 5 corazones × 2 puntos = 10 puntos totales
    - El daño se aplica de DERECHA A IZQUIERDA
      (el corazón derecho se daña primero, el izquierdo último)

    Args:
        lives: puntos de vida actuales (0-10)

    Returns:
        Lista de 5 strings ordenados izquierda a derecha:
        [corazon_1, corazon_2, corazon_3, corazon_4, corazon_5]
        donde cada valor es "lleno", "medio" o "vacio"

    EJEMPLOS (daño de derecha a izquierda):
        10 vidas -> [lleno,  lleno,  lleno,  lleno,  lleno ]  (todos llenos)
        9 vidas  -> [lleno,  lleno,  lleno,  lleno,  medio ]  (der pasa a medio)
        8 vidas  -> [lleno,  lleno,  lleno,  lleno,  vacio ]  (der pasa a vacío)
        etc...
        0 vidas  -> [vacio,  vacio,  vacio,  vacio,  vacio ]  (todos vacíos - GAME OVER)
    """
    # Distribuir vidas de izquierda a derecha, 2 puntos por corazón
    puntos = []
    for i in range(5):
        # Cada corazón tiene hasta 2 puntos
        vida_corazon = min(2, max(0, lives - i * 2))
        puntos.append(vida_corazon)

    # Convertir puntos a estados visuales
    estados = []
    for p in puntos:
        if p == 2:
            estados.append("lleno")
        elif p == 1:
            estados.append("medio")
        else:  # p == 0
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

        # --- Sistema de animación del personaje ---
        self._animaciones: dict = {}
        self._personaje_sprites: dict = {}  # Almacena sprites P2 cuando estén disponibles
        self._cargar_animaciones_personaje()

        # --- Sistema de iconos de poderes ---
        self._iconos_poderes: dict = {}  # Almacena los 4 iconos escalados
        self._cargar_iconos_poderes()

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

    def _cargar_animaciones_personaje(self) -> None:
        """Carga las animaciones del personaje (idle para P1, placeholder para P2)."""
        try:
            from systems.animation import AnimationManager
            # Cargar animaciones de Daniel
            self._animaciones = AnimationManager.load_from_json(
                "assets/sprites/player/animations.json",
                "assets/sprites/player"
            )
        except Exception as e:
            print(f"[WARNING] HUDPanel: No se pudieron cargar animaciones: {e}")
            self._animaciones = {}

    def _cargar_iconos_poderes(self) -> None:
        """Carga los iconos de poderes del spritesheet."""
        try:
            self._iconos_poderes = cargar_iconos_poderes("assets/ui/iconos_pwr.png")
        except Exception as e:
            print(f"[WARNING] HUDPanel: No se pudieron cargar iconos de poderes: {e}")
            self._iconos_poderes = {}

    def update(self, dt: float) -> None:
        """Actualiza las animaciones del panel (llamar cada frame del juego)."""
        if "idle" in self._animaciones:
            self._animaciones["idle"].update(dt)

    def set_personaje_p2_sprites(self, sprite_dict: dict) -> None:
        """
        Establece sprites personalizados para P2.

        Args:
            sprite_dict: dict con sprites del P2 (para futuros personajes)
        """
        self._personaje_sprites = sprite_dict

    def render(self, surface: pygame.Surface, player_data: dict, es_p2: bool = False) -> pygame.Rect:
        """
        Dibuja el panel completo: PNG de fondo + sprite animado + corazones + monedas + iconos de poderes.

        Args:
            surface: superficie donde dibujar
            player_data: {
                "health": int,          # vidas actuales (0-6)
                "max_health": int,      # vidas máximas (6)
                "coins": int,           # monedas/microchips
                "red_apoyo": bool,      # tiene Red de Apoyo (opcional)
                "modo_privado": bool,   # tiene Modo Privado (opcional)
                "emp": bool,            # tiene EMP (opcional)
                "eco_señal": bool       # tiene Eco de Señal (opcional)
            }
            es_p2: True si es panel P2 (muestra placeholder si no hay sprites)

        Returns:
            El rect ocupado por el panel
        """
        # 1. Fondo (PNG del panel o placeholder)
        self._dibujar_fondo(surface)

        # 2. Sprite animado del personaje (izquierda, centrado verticalmente)
        self._render_personaje(surface, es_p2=es_p2)

        # 3. Corazones de vida (derecha superior)
        lives = player_data.get("health", 6)
        self._render_corazones(surface, lives)

        # 4. Monedas (derecha inferior)
        coins = player_data.get("coins", 0)
        self._render_monedas(surface, coins, es_p2=es_p2)

        # 5. Iconos de poderes (columna vertical en el borde derecho)
        powers = {
            "red_apoyo": player_data.get("red_apoyo", False),
            "modo_privado": player_data.get("modo_privado", False),
            "emp": player_data.get("emp", False),
            "eco_señal": player_data.get("eco_señal", False)
        }
        self._render_iconos_poderes(surface, powers)

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
        Renderiza los corazones dentro del panel (5 corazones máximo).

        Args:
            surface: superficie donde dibujar
            lives: puntos de vida actuales (0-10)

        Los corazones se renderizan de izquierda a derecha.
        El daño ocurre de derecha a izquierda (corazón derecho se daña primero).
        """
        # Cargar corazones una sola vez (en caché global)
        if not hasattr(self, '_corazones_cargados'):
            global _CORAZONES_CACHE
            if '_CORAZONES_CACHE' not in globals():
                # Usar ruta relativa desde CODIGO/ - nuevo sprite corazones.png
                _CORAZONES_CACHE = cargar_corazones(
                    "assets/ui/corazones.png"
                )
            self._corazones_cargados = _CORAZONES_CACHE

        corazones = self._corazones_cargados

        # Obtener los estados de los corazones (5 corazones)
        estados = get_estado_corazones(lives)
        num_corazones = len(estados)

        # Configuración de posicionamiento - raw size 24×20 (SIN ESCALAR)
        CORAZON_W = 24
        CORAZON_H = 20
        GAP = 4         # separación entre corazones (píxeles)
        OFFSET_Y = 35   # margen superior dentro del panel

        # Calcular ancho total de corazones para centrarlos horizontalmente
        total_hearts_width = num_corazones * CORAZON_W + (num_corazones - 1) * GAP
        panel_width = self.rect.width
        OFFSET_X = (panel_width - total_hearts_width) // 2  # Centrar horizontalmente

        # Renderizar los corazones (izquierda a derecha)
        for i, estado in enumerate(estados):
            sprite = corazones[estado]
            x = int(self.rect.x + OFFSET_X + i * (CORAZON_W + GAP))
            y = int(self.rect.y + OFFSET_Y)
            surface.blit(sprite, (x, y))

    def _render_personaje(self, surface: pygame.Surface, es_p2: bool = False) -> None:
        """
        Renderiza el sprite animado del personaje (izquierda del panel, centrado verticalmente).

        Args:
            surface: superficie donde dibujar
            es_p2: True si es panel P2 (mostrar placeholder si no hay sprites)
        """
        # Tamaño del sprite: 64x64 base, escalado a 163x163 (15% más pequeño que 192)
        SPRITE_SIZE_BASE = 64  # Tamaño base de la animación
        SPRITE_SIZE_SCALED = 163  # Tamaño final en HUD (192 × 0.85 = 163, 15% más pequeño)
        SPRITE_MARGIN = 15  # Margen desde el borde izquierdo (-10px a la izquierda)

        # Posición X (izquierda-centro del panel, +5px a la derecha)
        x = self.rect.x + SPRITE_MARGIN

        # Posición Y (centrado verticalmente en el panel, -30px arriba)
        panel_center_y = self.rect.y + self.rect.height // 2
        y = int(panel_center_y - SPRITE_SIZE_SCALED // 2 - 30)  # -30px hacia arriba

        if es_p2:
            # Panel P2: mostrar placeholder hasta que lleguen sprites
            placeholder = pygame.Surface((SPRITE_SIZE_SCALED, SPRITE_SIZE_SCALED))
            placeholder.fill((100, 100, 100))  # Gris oscuro
            pygame.draw.rect(placeholder, (150, 150, 150), placeholder.get_rect(), 2)
            # Texto "P2"
            try:
                font = pygame.font.SysFont(None, 48)
                text = font.render("P2", True, (200, 200, 200))
                text_rect = text.get_rect(center=(SPRITE_SIZE_SCALED // 2, SPRITE_SIZE_SCALED // 2))
                placeholder.blit(text, text_rect)
            except:
                pass
            surface.blit(placeholder, (x, y))
        else:
            # Panel P1: mostrar animación de Daniel (idle) escalada a 128x128
            if "idle" in self._animaciones:
                frame = self._animaciones["idle"].current_frame()
                # Escalar el frame a 128x128 para coincidir con el jugador
                scaled_frame = pygame.transform.scale(frame, (SPRITE_SIZE_SCALED, SPRITE_SIZE_SCALED))
                surface.blit(scaled_frame, (x, y))
            else:
                # Placeholder si no hay animaciones cargadas
                placeholder = pygame.Surface((SPRITE_SIZE_SCALED, SPRITE_SIZE_SCALED))
                placeholder.fill((80, 80, 80))  # Gris más oscuro
                pygame.draw.rect(placeholder, (150, 150, 150), placeholder.get_rect(), 2)
                surface.blit(placeholder, (x, y))

    def _render_monedas(self, surface: pygame.Surface, coins: int, es_p2: bool = False) -> None:
        """
        Renderiza el icono de moneda + cantidad en la parte inferior del panel.
        Se calcula desde rect.bottom para garantizar que siempre está dentro.

        Args:
            surface: superficie donde dibujar
            coins: cantidad de monedas/microchips
            es_p2: True si es panel P2 (ajusta márgenes según tamaño del panel)
        """
        # Cargar icono de moneda (más grande que antes)
        try:
            if not hasattr(self, '_moneda_icon_cached'):
                moneda_path = "assets/ui/chip_moneda.png"
                moneda_img = pygame.image.load(moneda_path).convert_alpha()
                # Escalar a 48x48 píxeles (mucho más visible)
                self._moneda_icon_cached = pygame.transform.scale(moneda_img, (48, 48))
        except Exception as e:
            self._moneda_icon_cached = None

        # Parámetros de posicionamiento (ajustados según el panel)
        ICON_SIZE = 48  # Más grande
        MARGEN_INF = 72  # Margen desde el borde inferior del panel

        # P1 (497x221): márgenes más grandes a la derecha
        # P2 (450x200): márgenes más pequeños para caber en el panel
        MARGEN_IZQ = 120 if es_p2 else 200  # Ajustado para P2
        TEXT_MARGIN_LEFT = 12  # Espacio entre icono y número

        # Calcular Y desde el FONDO del panel hacia arriba
        # Esto garantiza que siempre esté dentro del panel, sin importar la altura
        icon_y = self.rect.bottom - ICON_SIZE - MARGEN_INF

        # Calcular X (alineado desde la izquierda con margen)
        icon_x = self.rect.x + MARGEN_IZQ

        # Dibujar icono
        if self._moneda_icon_cached:
            surface.blit(self._moneda_icon_cached, (icon_x, icon_y))
        else:
            # Placeholder: rectángulo amarillo
            pygame.draw.rect(surface, (255, 200, 0),
                           (icon_x, icon_y, ICON_SIZE, ICON_SIZE))

        # Dibujar cantidad de monedas (texto) con fuente más grande
        try:
            # Fuente mucho más grande (36pt) para mejor legibilidad
            font = pygame.font.SysFont(None, 36)
            coins_text = font.render(str(coins), True, (230, 220, 200))

            # Posición del texto (a la derecha del icono, centrado verticalmente)
            text_x = icon_x + ICON_SIZE + TEXT_MARGIN_LEFT
            text_y = icon_y + (ICON_SIZE - coins_text.get_height()) // 2

            # Dibujar sombra (mejora la legibilidad sobre fondo oscuro)
            shadow_font = pygame.font.SysFont(None, 36)
            shadow_text = shadow_font.render(str(coins), True, (0, 0, 0))
            surface.blit(shadow_text, (text_x + 1, text_y + 1))

            # Dibujar texto principal
            surface.blit(coins_text, (text_x, text_y))
        except Exception as e:
            print(f"[WARNING] HUDPanel: No se pudo renderizar cantidad de monedas: {e}")

    def _render_iconos_poderes(self, surface: pygame.Surface, powers: dict) -> None:
        """
        Renderiza los iconos de poderes activos en una columna vertical en el borde derecho del panel.

        Args:
            surface: superficie donde dibujar
            powers: dict con estado de poderes {
                "red_apoyo": int (cantidad de curaciones acumuladas),
                "modo_privado": bool,
                "emp": bool,
                "eco_señal": bool
            }

        Los iconos aparecen solo si el poder correspondiente tiene un valor positivo o True (jugador ha comprado el item).
        Se apilan verticalmente en el lado derecho del panel, con margen pequeño.
        Para red_apoyo, muestra un número pequeño en la esquina inferior derecha indicando cantidad.
        """
        if not self._iconos_poderes:
            return  # Sin iconos cargados, no renderizar

        # Parámetros de posicionamiento
        ICON_SIZE = 28  # Tamaño de cada icono (ya escalado en cargar_iconos_poderes)
        MARGEN_DERECHO = 102  # Margen desde el borde derecho del panel
        MARGEN_SUPERIOR = 45  # Margen desde el borde superior del panel
        GAP_VERTICAL = 4  # Separación entre iconos

        # Posición X (alineada al borde derecho del panel, con margen)
        icon_x = self.rect.right - ICON_SIZE - MARGEN_DERECHO

        # Posición Y inicial (superior del panel, con margen)
        icon_y = self.rect.y + MARGEN_SUPERIOR

        # Orden de renderizado: red_apoyo, modo_privado, emp, eco_señal
        orden_iconos = ["red_apoyo", "modo_privado", "emp", "eco_señal"]

        for nombre_poder in orden_iconos:
            # Obtener el valor del poder (puede ser int para red_apoyo, bool para otros)
            poder_valor = powers.get(nombre_poder, 0 if nombre_poder == "red_apoyo" else False)

            # Renderizar si tiene un valor positivo (red_apoyo) o True (otros)
            render_icon = (nombre_poder == "red_apoyo" and poder_valor > 0) or (nombre_poder != "red_apoyo" and poder_valor)

            if render_icon and nombre_poder in self._iconos_poderes:
                icono = self._iconos_poderes[nombre_poder]
                surface.blit(icono, (int(icon_x), int(icon_y)))

                # Si es red_apoyo y tiene cantidad > 0, mostrar número pequeño en esquina inferior derecha
                if nombre_poder == "red_apoyo" and poder_valor > 0:
                    try:
                        # Fuente pequeña para el contador
                        font_contador = pygame.font.SysFont(None, 16)
                        text_contador = font_contador.render(str(poder_valor), True, (255, 255, 255))

                        # Posición: esquina inferior derecha del icono
                        count_x = int(icon_x + ICON_SIZE - text_contador.get_width() - 2)
                        count_y = int(icon_y + ICON_SIZE - text_contador.get_height() - 2)

                        # Dibujar fondo oscuro para mejor legibilidad
                        bg_rect = text_contador.get_rect(topleft=(count_x - 1, count_y - 1))
                        pygame.draw.rect(surface, (0, 0, 0), bg_rect.inflate(4, 2))

                        # Dibujar número
                        surface.blit(text_contador, (count_x, count_y))
                    except Exception:
                        pass

                # Mover hacia abajo para el siguiente icono
                icon_y += ICON_SIZE + GAP_VERTICAL

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
