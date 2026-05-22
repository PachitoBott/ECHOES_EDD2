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
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import pygame
    _PYGAME_DISPONIBLE = True
except ImportError:                 # entorno de tests sin pygame
    _PYGAME_DISPONIBLE = False

from core.asset_paths import assets_dir
from narrative.text_renderer import TextRenderer
from narrative.text_box import TextBox

log_cinematics = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Panel de cinematica (modelo de datos)
# ---------------------------------------------------------------------------

class _Panel:
    """Un cuadro de texto dentro de una secuencia cinematica."""

    __slots__ = (
        "texto", "duracion", "color_fondo", "color_texto",
        "fade_in", "fade_out", "subtitulo", "image_path", "_cached_image",
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
        image_path: str = "",
    ) -> None:
        self.texto       = texto
        self.duracion    = duracion
        self.color_fondo = color_fondo
        self.color_texto = color_texto
        self.fade_in     = max(0.0, fade_in)
        self.fade_out    = max(0.0, fade_out)
        self.subtitulo   = subtitulo
        self.image_path  = image_path
        self._cached_image = None

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
            image_path=d.get("image", ""),
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

        # Nuevos sistemas: typewriter y banda visual
        self._text_renderer: Optional[TextRenderer] = None
        self._text_box: Optional[TextBox] = None
        self._config: Dict[str, Any] = self._load_config_from_json("narrative/cutscene_config.json")

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
        Si la misma cinemática ya está en reproducción, no la reinicia.
        """
        cinem = self._cinematicas.get(id_cinematica)
        if cinem is None or not cinem.paneles:
            log_cinematics.warning(f"Cinemática '{id_cinematica}' no encontrada o sin paneles")
            return False

        # Si la misma cinemática está en reproducción, no reiniciar
        if self._activo and self._cinem_actual and self._cinem_actual.id == id_cinematica:
            log_cinematics.debug(f"Cinemática '{id_cinematica}' ya está en reproducción, no reiniciando")
            return True

        log_cinematics.info(f"[PLAY] Reproduciendo cinematica '{id_cinematica}' con {len(cinem.paneles)} paneles")
        self._cinem_actual = cinem
        self._panel_idx    = 0
        self._tiempo_panel = 0.0
        self._activo       = True
        self._callback_fin = callback_fin
        self._setup_panel()  # Inicializar textRenderer y textBox
        return True

    def saltar(self) -> None:
        """El jugador presiono Skip — termina inmediatamente."""
        self._finalizar()

    def siguiente_panel(self) -> None:
        """El jugador presiono Espacio — avanza al siguiente panel o completa el texto actual."""
        if not self._activo or self._cinem_actual is None:
            return

        # Si el texto actual aun no se ha mostrado completamente, completarlo al instante
        if self._text_renderer and not self._text_renderer.is_finished():
            self._text_renderer.force_finish()
            return

        # Si el texto ya está completo, avanzar al siguiente panel
        self._tiempo_panel = 0.0
        self._panel_idx += 1

        if self._panel_idx >= len(self._cinem_actual.paneles):
            self._finalizar()
        else:
            self._setup_panel()

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

        # Actualizar text_renderer (typewriter effect)
        if self._text_renderer:
            self._text_renderer.update(dt)

        if self._tiempo_panel >= duracion_panel:
            self._tiempo_panel -= duracion_panel
            self._panel_idx += 1
            if self._panel_idx >= len(paneles):
                self._finalizar()
            else:
                self._setup_panel()  # Preparar siguiente panel

    def draw(self, surface: "pygame.Surface", screen_scale: int = 1) -> None:
        """
        Dibuja el panel actual con typewriter effect y banda visual.

        Orden de renderizado:
        1. Imagen de fondo (con alpha)
        2. Banda negra con bordes irregulares
        3. Texto visible (typewriter effect)
        4. Hint "[Esc] Saltar"
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

        # ---- calcular alpha para fade-in/fade-out ----
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

        w = surface.get_width()
        h = surface.get_height()

        # ---- 1. Renderizar imagen de fondo ----
        image_surf = None
        if panel.image_path:
            if panel._cached_image is None:
                # Primera vez: intentar cargar
                image_surf = self._load_image(panel.image_path)
                if image_surf:
                    panel._cached_image = image_surf
                else:
                    log_cinematics.warning(f"No se pudo cargar imagen para panel: {panel.image_path}")
            else:
                # Ya cacheada
                image_surf = panel._cached_image

        if image_surf:
            try:
                scaled_image = pygame.transform.scale(image_surf, (w, h))
                scaled_image.set_alpha(alpha)
                surface.blit(scaled_image, (0, 0))
            except Exception as e:
                log_cinematics.error(f"Error renderizando imagen: {e}")
                # Fallback a color sólido si hay error en renderizado
                surface.fill(panel.color_fondo)
        else:
            # Fallback a color sólido si no hay imagen
            fondo = pygame.Surface((w, h))
            fondo.fill(panel.color_fondo)
            fondo.set_alpha(alpha)
            surface.fill((0, 0, 0))
            surface.blit(fondo, (0, 0))

        # ---- 2. Banda negra con bordes irregulares (escalar posición) ----
        if self._text_box:
            band_surface = self._text_box.get_band_surface()
            band_surface.set_alpha(alpha)
            band_rect = self._text_box.get_band_rect()
            # Escalar la posición del rect a la superficie actual
            scaled_band_rect = pygame.Rect(
                band_rect.x * screen_scale,
                band_rect.y * screen_scale,
                band_rect.width * screen_scale,
                band_rect.height * screen_scale
            )
            # Escalar la banda a las nuevas dimensiones
            scaled_band_surface = pygame.transform.scale(
                band_surface,
                (scaled_band_rect.width, scaled_band_rect.height)
            )
            scaled_band_surface.set_alpha(alpha)
            surface.blit(scaled_band_surface, scaled_band_rect.topleft)

        # ---- 3. Texto con typewriter effect ----
        if self._text_renderer:
            visible_text = self._text_renderer.current_text()
            self._draw_wrapped_text(surface, visible_text, panel.color_texto, alpha, screen_scale)

        # ---- 4. Pista "Skip" ----
        if alpha > 60:
            hint_font = pygame.font.SysFont(None, max(12, self._font_size - 8))
            hint = hint_font.render("[Esc] Saltar", True, (120, 120, 120))
            hint.set_alpha(min(alpha, 180))
            surface.blit(hint, (int(8 * screen_scale), int(8 * screen_scale)))

    def _draw_wrapped_text(
        self,
        surface: "pygame.Surface",
        text: str,
        color: Tuple[int, int, int],
        alpha: int,
        screen_scale: int = 1
    ) -> None:
        """Dibuja texto con wrapping dentro de la banda.

        Args:
            surface: Superficie donde dibujar
            text: Texto a renderizar
            color: Color RGB del texto
            alpha: Opacidad (0-255)
            screen_scale: Factor de escala de pantalla
        """
        if not self._text_box or not self._font:
            return

        text_style_config = self._config.get("text_style", {})
        text_box_config = self._config.get("text_box", {})

        # Obtener recto del área de texto (coordenadas lógicas)
        padding = text_box_config.get("padding_left", 30)
        text_area = self._text_box.get_text_area_rect(padding=padding)

        # Escalar área de texto a superficie actual
        text_area_scaled = pygame.Rect(
            text_area.x * screen_scale,
            text_area.y * screen_scale,
            text_area.width * screen_scale,
            text_area.height * screen_scale
        )

        # Dividir en líneas (respetar \n del texto original)
        lines = text.split("\n")
        line_h = int(self._font.get_linesize() * screen_scale)

        # Renderizar cada línea
        y_offset = text_area_scaled.y
        for line in lines:
            surf = self._font.render(line, True, color)
            # Escalar texto a escala de pantalla
            scaled_surf = pygame.transform.scale(
                surf,
                (int(surf.get_width() * screen_scale), int(surf.get_height() * screen_scale))
            )
            scaled_surf.set_alpha(alpha)
            # Centrar horizontalmente dentro del área de texto escalada
            rect = scaled_surf.get_rect(centerx=surface.get_width() // 2, y=y_offset)
            surface.blit(scaled_surf, rect)
            y_offset += line_h

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _load_config_from_json(self, config_path: str) -> Dict[str, Any]:
        """Carga configuración de typewriter y banda desde JSON.

        Retorna dict con defaults si el archivo no existe.
        """
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Defaults si no existe config
        return {
            "text_style": {
                "font_path": "assets/fonts/SpecialElite-Regular.ttf",
                "font_size": 24,
                "color": [220, 220, 220],
                "typewriter_fps": 30,
                "max_width_ratio": 0.75,
                "bottom_margin_ratio": 0.15,
                "line_height_multiplier": 1.3
            },
            "text_box": {
                "color": [0, 0, 0],
                "alpha": 220,
                "min_height_px": 120,
                "edge_irregularity": 8,
                "padding_top": 15,
                "padding_bottom": 15,
                "padding_left": 30,
                "padding_right": 30
            },
            "typewriter_sound": {
                "path": "assets/sounds/typewriter_click.ogg",
                "volume": 0.4
            }
        }

    def _setup_panel(self) -> None:
        """Inicializa TextRenderer y TextBox para el panel actual."""
        if not self._cinem_actual or self._panel_idx >= len(self._cinem_actual.paneles):
            return

        panel = self._cinem_actual.paneles[self._panel_idx]

        # Crear nuevo TextRenderer
        sound_path = self._config.get("typewriter_sound", {}).get("path", "")
        sound_volume = self._config.get("typewriter_sound", {}).get("volume", 0.4)
        typewriter_fps = self._config.get("text_style", {}).get("typewriter_fps", 30)

        self._text_renderer = TextRenderer(
            text=panel.texto,
            typewriter_fps=typewriter_fps,
            typewriter_sound_path=sound_path,
            sound_volume=sound_volume
        )

        # Crear nuevo TextBox
        text_box_config = self._config.get("text_box", {})
        band_height = text_box_config.get("min_height_px", 120)
        box_color = tuple(text_box_config.get("color", [0, 0, 0]))
        alpha = text_box_config.get("alpha", 220)
        irregularity = text_box_config.get("edge_irregularity", 8)

        self._text_box = TextBox(
            screen_width=self.screen_w,
            screen_height=self.screen_h,
            band_height=band_height,
            color=box_color,
            alpha=alpha,
            irregularity=irregularity
        )

    def _inicializar_fuentes(self) -> None:
        if self._fuentes_listas:
            return

        # Intentar cargar font personalizado desde config
        text_style_config = self._config.get("text_style", {})
        font_path_config = text_style_config.get("font_path", "")
        font_size = text_style_config.get("font_size", self._font_size)

        # Intentar cargar desde archivo
        if font_path_config:
            # Resolver ruta: si es relativa, buscar en assets
            font_file = None

            # Intento 1: Ruta absoluta o relativa del config
            if Path(font_path_config).exists():
                font_file = Path(font_path_config)

            # Intento 2: Buscar en assets_dir() si es un nombre simple
            if font_file is None:
                asset_font_file = assets_dir(font_path_config)
                if asset_font_file.exists():
                    font_file = asset_font_file

            # Intento 3: Buscar como "fonts/<filename>"
            if font_file is None:
                if "/" not in font_path_config:
                    asset_font_file = assets_dir("fonts", font_path_config)
                    if asset_font_file.exists():
                        font_file = asset_font_file

            if font_file:
                try:
                    font_path_str = str(font_file)
                    self._font = pygame.font.Font(font_path_str, font_size)
                    self._font_sub = pygame.font.Font(font_path_str, max(12, font_size - 6))
                    self._fuentes_listas = True
                    log_cinematics.info(f"[OK] Font cargada: {font_file}")
                    return
                except Exception as e:
                    log_cinematics.warning(f"Error cargando font {font_file}: {e}")

        # Fallback a SysFont si falla la carga personalizada
        log_cinematics.debug(f"Usando SysFont como fallback")
        self._font     = pygame.font.SysFont(None, self._font_size)
        self._font_sub = pygame.font.SysFont(None, max(12, self._font_size - 6))
        self._fuentes_listas = True

    def _load_image(self, image_path: str) -> Optional["pygame.Surface"]:
        """Carga una imagen desde la carpeta de cinematics."""
        if not image_path:
            return None

        # Intentar cargar desde la carpeta de cinematics
        cinematics_dir = Path(assets_dir("cinematics"))
        image_file = cinematics_dir / image_path

        log_cinematics.debug(f"Intentando cargar imagen: {image_file}")

        if image_file.exists():
            try:
                log_cinematics.debug(f"[DONE] Imagen encontrada: {image_file}")
                return pygame.image.load(image_file.as_posix()).convert()
            except Exception as e:
                log_cinematics.warning(f"Error cargando imagen {image_file}: {e}")
                pass
        else:
            log_cinematics.warning(f"[FAIL] Archivo no encontrado: {image_file}")

        return None

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
