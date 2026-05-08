"""
narrative/text_box.py
=====================
Sistema de banda negra procedural con bordes irregulares para cinematics.

Responsabilidades:
  - Generar banda negra de ancho completo con bordes irregulares
  - Cachear la banda generada (evita flickering y overhead de renderizado)
  - Proporcionar rects para posicionamiento de texto
  - Algoritmo determinístico para bordes jagged (usa hash, no random)

Uso:
  text_box = TextBox(screen_width=960, screen_height=640)
  band_surface = text_box.get_band_surface()
  band_rect = text_box.get_band_rect()
  text_area = text_box.get_text_area_rect(padding=30)
"""

import pygame
from typing import Tuple


class TextBox:
    """Genera y gestiona banda visual procedural para cinematics."""

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        band_height: int = 120,
        color: Tuple[int, int, int] = (0, 0, 0),
        alpha: int = 220,
        irregularity: int = 8
    ):
        """Inicializa la caja de texto con banda irregular.

        Args:
            screen_width: Ancho de la pantalla en píxeles
            screen_height: Alto de la pantalla en píxeles
            band_height: Alto de la banda en píxeles
            color: Color RGB de la banda (default: negro)
            alpha: Opacidad de la banda (0-255)
            irregularity: Intensidad de la irregularidad del borde superior (3-12 píx)
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.band_height = band_height
        self.color = color
        self.alpha = alpha
        self.irregularity = max(1, irregularity)

        self._band_surface: pygame.Surface | None = None
        self._generated_config = None

        # Generar banda al inicializar
        self.generate_band()

    def generate_band(self) -> None:
        """Crea superficie de banda con bordes superiores irregulares.

        La irregularidad se genera de forma determinística usando hash,
        para evitar flickering (mismo seed = mismo resultado cada frame).
        """
        # Crear superficie con canal alpha
        self._band_surface = pygame.Surface(
            (self.screen_width, self.band_height),
            pygame.SRCALPHA
        )

        # Llenar con color semitransparente
        self._band_surface.fill((*self.color, self.alpha))

        # Generar borde superior irregular (procedural, determinístico)
        top_edge = []
        for x in range(self.screen_width):
            # Offset aleatorio usando hash determinístico (seed fijo: 12345)
            # Esto asegura mismo patrón cada frame (no flickering)
            offset = (hash((x, 12345)) % self.irregularity) - (self.irregularity // 2)
            y = max(0, offset)  # Asegurar que y no sea negativo
            top_edge.append([x, y])  # Usar lista, no tupla

        # Dibujar línea jagged en borde superior (usar solo RGB, no alpha)
        if len(top_edge) > 1:
            try:
                pygame.draw.lines(
                    self._band_surface,
                    self.color,  # RGB only, no alpha needed for lines
                    top_edge,
                    2  # width
                )
            except TypeError:
                # Fallback si hay problemas con draw.lines
                pass

        # Guardar config para validar si necesita regeneración
        self._generated_config = {
            "width": self.screen_width,
            "height": self.band_height,
            "color": self.color,
            "alpha": self.alpha,
            "irregularity": self.irregularity
        }

    def get_band_surface(self) -> pygame.Surface:
        """Retorna la superficie de banda generada.

        Returns:
            pygame.Surface con la banda completa (caché)
        """
        if self._band_surface is None:
            self.generate_band()
        return self._band_surface

    def get_band_rect(self) -> pygame.Rect:
        """Retorna rect para posicionar banda en base de pantalla.

        La banda se posiciona en la parte inferior de la pantalla.

        Returns:
            pygame.Rect con posición y dimensiones de la banda
        """
        y = self.screen_height - self.band_height
        return pygame.Rect(0, y, self.screen_width, self.band_height)

    def get_text_area_rect(self, padding: int = 30) -> pygame.Rect:
        """Retorna rect para posicionar texto dentro de banda.

        Args:
            padding: Espacio entre borde de banda y texto (píxeles)

        Returns:
            pygame.Rect con área disponible para texto (con padding)
        """
        band_rect = self.get_band_rect()
        return pygame.Rect(
            band_rect.x + padding,
            band_rect.y + padding,
            band_rect.width - 2 * padding,
            band_rect.height - 2 * padding
        )
