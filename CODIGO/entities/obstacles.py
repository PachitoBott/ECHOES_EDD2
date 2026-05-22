"""
Sistema de obstáculos animados basado en código.
Reemplaza spritesheets de animación con animación procedural en Python.
"""

import pygame
from typing import List, Optional
from entities.enemy_sprites import cargar_spritesheet_cuadricula


class ObstaculoPantalla:
    """
    Obstáculo animado tipo pantalla (2x1 tiles).
    Proporciones: 2 tiles de ancho × 1 tile de alto.
    Animación: 13 frames en bucle (de un spritesheet 4x4).
    Bloquea el paso del jugador y enemigos.
    """

    # Configuración de animación
    FPS_ANIMACION = 8      # Frames por segundo
    LOOP = True            # La animación se repite indefinidamente

    # Clase interna: información de frames pre-cargados (lazy loading)
    _frames_cache: Optional[List[pygame.Surface]] = None

    def __init__(self, x: float, y: float, tile_size: int):
        """
        Inicializa un obstáculo pantalla.

        Args:
            x, y:       Posición en el mundo (esquina superior izquierda)
            tile_size:  Tamaño de un tile en píxeles lógicos
        """
        # Proporciones: 2 tiles ancho × 1 tile alto
        self.ancho = tile_size * 2
        self.alto = tile_size * 1

        # Posición y hitbox
        self.x = x
        self.y = y
        self.hitbox = pygame.Rect(x, y, self.ancho, self.alto)

        # Estado de animación
        self.frame_actual = 0
        self.timer_frame = 0.0
        self.intervalo = 1.0 / self.FPS_ANIMACION

    @classmethod
    def _cargar_frames(cls) -> List[pygame.Surface]:
        """
        Carga los 13 frames de pantalla-1.png de forma lazy (primera vez que se usan).

        El spritesheet es 512x256 (4 columnas × 4 filas = 16 frames).
        Cada frame es 128×64 px.
        Usamos solo los primeros 13 frames.
        """
        if cls._frames_cache is not None:
            return cls._frames_cache

        frames = cargar_spritesheet_cuadricula(
            ruta="assets/pantalla-1.png",
            frame_w=128,
            frame_h=64,
            cols=4,
            frames_a_usar=13,  # Ignorar frames 13, 14, 15
            flip_horizontal=False,
            tamaño_logico=128  # No escalar, usar tamaño original
        )

        if not frames:
            # Fallback: generar placeholder si no carga
            placeholder = pygame.Surface((128, 64))
            placeholder.fill((100, 100, 100))
            frames = [placeholder] * 13

        cls._frames_cache = frames
        return frames

    def update(self, dt: float) -> None:
        """
        Avanza la animación en bucle.

        Args:
            dt: Delta time en segundos
        """
        self.timer_frame += dt
        if self.timer_frame >= self.intervalo:
            self.timer_frame -= self.intervalo
            self.frame_actual = (self.frame_actual + 1) % len(self._cargar_frames())

    def render(self, surface: pygame.Surface, camera_offset: tuple = (0, 0)) -> None:
        """
        Renderiza el frame actual en la superficie.

        Args:
            surface:        Superficie pygame donde dibujar
            camera_offset:  Tupla (offset_x, offset_y) para cámara
        """
        frames = self._cargar_frames()
        if not frames:
            return

        frame = frames[self.frame_actual]

        # Escalar al tamaño 2x1 tiles si es necesario
        if frame.get_size() != (self.ancho, self.alto):
            frame = pygame.transform.scale(frame, (self.ancho, self.alto))

        # Aplicar offset de cámara
        pos_x = self.x - camera_offset[0]
        pos_y = self.y - camera_offset[1]

        surface.blit(frame, (int(pos_x), int(pos_y)))

    def get_hitbox(self) -> pygame.Rect:
        """Retorna el hitbox actualizado para colisiones."""
        self.hitbox.topleft = (self.x, self.y)
        return self.hitbox

    @classmethod
    def limpiar_cache(cls) -> None:
        """Limpia el caché de frames (útil para hot-reload)."""
        cls._frames_cache = None
