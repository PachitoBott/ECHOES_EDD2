import json
import random
import math
from pathlib import Path
from typing import Optional
import pygame


class FloatingElement:
    """Elemento flotante en el fondo borroso."""

    def __init__(self, x: float, y: float, size: int, color: tuple[int, int, int],
                 drift_speed: float, rotation_speed: float):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.drift_speed = drift_speed
        self.rotation_speed = rotation_speed
        self.rotation = random.uniform(0, 360)
        self.vx = random.uniform(-drift_speed, drift_speed)
        self.vy = random.uniform(-drift_speed, drift_speed)


class BlurredBackground:
    """Sistema de fondo borroso con elementos flotantes animados."""

    def __init__(self, screen_width: int, screen_height: int, config_path: Optional[str] = None):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Cargar configuración
        self.config = self._load_config(config_path)

        # Surface para el fondo borroso
        self._bg_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)

        # Generar elementos flotantes
        self.elements = []
        self._generate_elements()

        # Estado
        self._time_elapsed = 0.0

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Carga la configuración desde JSON."""
        if config_path is None:
            config_path = Path(__file__).parent / "blur_config.json"

        try:
            with open(config_path, 'r') as f:
                full_config = json.load(f)
                return full_config.get("blur_background", {})
        except (FileNotFoundError, json.JSONDecodeError):
            # Configuración por defecto si no encuentra archivo
            return {
                "enabled": True,
                "blur_intensity": 8,
                "num_elements": 12,
                "opacity": 0.3,
                "animation_speed": 1.0,
                "element_colors": [
                    [100, 150, 255],
                    [150, 100, 255],
                    [255, 100, 150]
                ],
                "element_size_range": [20, 80],
                "drift_speed_range": [0.3, 1.5],
                "rotation_speed_range": [10, 60]
            }

    def _generate_elements(self) -> None:
        """Genera los elementos flotantes iniciales."""
        self.elements = []
        num_elements = self.config.get("num_elements", 12)
        colors = self.config.get("element_colors", [[100, 150, 255]])
        size_range = self.config.get("element_size_range", [20, 80])
        drift_range = self.config.get("drift_speed_range", [0.3, 1.5])
        rotation_range = self.config.get("rotation_speed_range", [10, 60])

        for _ in range(num_elements):
            x = random.uniform(-50, self.screen_width + 50)
            y = random.uniform(-50, self.screen_height + 50)
            size = random.randint(size_range[0], size_range[1])
            color = tuple(random.choice(colors))
            drift_speed = random.uniform(drift_range[0], drift_range[1])
            rotation_speed = random.uniform(rotation_range[0], rotation_range[1])

            element = FloatingElement(x, y, size, color, drift_speed, rotation_speed)
            self.elements.append(element)

    def update(self, dt: float) -> None:
        """Actualiza el estado de los elementos flotantes."""
        if not self.config.get("enabled", True):
            return

        animation_speed = self.config.get("animation_speed", 1.0)
        self._time_elapsed += dt * animation_speed

        for element in self.elements:
            # Actualizar posición
            element.x += element.vx * dt * 30  # 30 es un factor de escala
            element.y += element.vy * dt * 30

            # Actualizar rotación
            element.rotation += element.rotation_speed * dt * animation_speed
            element.rotation %= 360

            # Rebote en los bordes (envolver alrededor)
            margin = element.size
            if element.x < -margin:
                element.x = self.screen_width + margin
            elif element.x > self.screen_width + margin:
                element.x = -margin

            if element.y < -margin:
                element.y = self.screen_height + margin
            elif element.y > self.screen_height + margin:
                element.y = -margin

    def draw(self, target_surface: pygame.Surface) -> None:
        """Renderiza el fondo borroso en la superficie objetivo."""
        if not self.config.get("enabled", True):
            return

        # Limpiar surface
        self._bg_surface.fill((0, 0, 0, 0))

        # Dibujar elementos flotantes como círculos rotados
        for element in self.elements:
            self._draw_floating_element(element)

        # Aplicar blur (simulado con drawing múltiple con alpha)
        blur_intensity = self.config.get("blur_intensity", 8)
        self._apply_blur_effect(blur_intensity)

        # Establecer opacidad
        opacity = self.config.get("opacity", 0.3)
        self._bg_surface.set_alpha(int(255 * opacity))

        # Blitear al surface objetivo
        target_surface.blit(self._bg_surface, (0, 0))

    def _draw_floating_element(self, element: FloatingElement) -> None:
        """Dibuja un elemento flotante como una forma geométrica."""
        # Crear superficie temporal para el elemento con rotación
        element_surf = pygame.Surface((element.size * 2, element.size * 2), pygame.SRCALPHA)

        # Dibujar círculo con gradiente simulado
        color = element.color
        center = (element.size, element.size)

        # Círculo principal
        pygame.draw.circle(element_surf, (*color, 180), center, element.size)

        # Círculo de borde
        pygame.draw.circle(element_surf, (*color, 100), center, element.size // 2)

        # Rotar según rotación del elemento
        rotated_surf = pygame.transform.rotate(element_surf, element.rotation)
        rotated_rect = rotated_surf.get_rect(center=(int(element.x), int(element.y)))

        # Blitear al surface de fondo
        self._bg_surface.blit(rotated_surf, rotated_rect.topleft)

    def _apply_blur_effect(self, blur_intensity: int) -> None:
        """Aplica un efecto de blur simulado."""
        # Crear una versión borrosa usando smoothscale
        temp_surface = self._bg_surface.copy()

        # Reducir tamaño y ampliar nuevamente (efecto blur)
        if blur_intensity > 0:
            reduced_size = (
                max(1, self.screen_width // blur_intensity),
                max(1, self.screen_height // blur_intensity)
            )
            small = pygame.transform.smoothscale(temp_surface, reduced_size)
            blurred = pygame.transform.smoothscale(small, (self.screen_width, self.screen_height))

            # Mezclar con original usando alpha blending
            self._bg_surface.blit(blurred, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)

    def set_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita el fondo borroso."""
        self.config["enabled"] = enabled

    def set_opacity(self, opacity: float) -> None:
        """Establece la opacidad del fondo borroso (0.0 - 1.0)."""
        self.config["opacity"] = max(0.0, min(1.0, opacity))

    def set_blur_intensity(self, intensity: int) -> None:
        """Establece la intensidad del blur."""
        self.config["blur_intensity"] = max(1, intensity)

    def regenerate_elements(self) -> None:
        """Regenera los elementos flotantes."""
        self._generate_elements()
