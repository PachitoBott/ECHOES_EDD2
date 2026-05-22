"""
Sistema de obstáculos animados basado en código.
Reemplaza spritesheets de animación con animación procedural en Python.

Estructura escalable: clase base ObstaculoAnimado compartida entre todos
los obstáculos con animación (pantalla-1, pantalla-2, tubo-3, etc.)
"""

import pygame
import random
from typing import List, Optional
from entities.enemy_sprites import cargar_spritesheet_cuadricula


class ObstaculoAnimado:
    """
    Clase base para obstáculos con animación en spritesheet.
    Reutilizable para cualquier obstáculo animado futuro.
    Subclases solo necesitan definir frames y proporciones.
    """

    FPS_ANIMACION = 8      # Frames por segundo (configurable por subclase)
    LOOP = True            # La animación se repite indefinidamente

    def __init__(self, x: float, y: float,
                 ancho: int, alto: int,
                 frames: Optional[List[pygame.Surface]] = None):
        """
        Inicializa un obstáculo animado base.

        Args:
            x, y:       Posición en el mundo (esquina superior izquierda)
            ancho:      Ancho en píxeles lógicos
            alto:       Alto en píxeles lógicos
            frames:     Lista de superficies de frames (puede ser None)
        """
        self.x = x
        self.y = y
        self.ancho = ancho
        self.alto = alto
        self.hitbox = pygame.Rect(x, y, ancho, alto)

        # Estado de animación
        self.frames = frames or []
        self.frame_actual = 0
        self.timer_frame = 0.0
        self.intervalo = 1.0 / self.FPS_ANIMACION

        # Desincronizar animación: offset aleatorio en el frame
        if self.frames:
            self.frame_actual = random.randint(0, len(self.frames) - 1)
            self.timer_frame = random.uniform(0.0, self.intervalo)

    def update(self, dt: float) -> None:
        """
        Avanza la animación. Subclases pueden sobreescribir.

        Args:
            dt: Delta time en segundos
        """
        if not self.frames:
            return

        self.timer_frame += dt
        if self.timer_frame >= self.intervalo:
            self.timer_frame -= self.intervalo
            if self.LOOP:
                # Bucle infinito
                self.frame_actual = (self.frame_actual + 1) % len(self.frames)
            else:
                # Una sola vez, congelado en el último frame
                self.frame_actual = min(
                    self.frame_actual + 1,
                    len(self.frames) - 1
                )

    def render(self, surface: pygame.Surface,
               camera_offset: tuple = (0, 0)) -> None:
        """
        Renderiza el frame actual escalado al tamaño del obstáculo.

        Args:
            surface:        Superficie pygame donde dibujar
            camera_offset:  Tupla (offset_x, offset_y) para cámara
        """
        if not self.frames:
            return

        frame = self.frames[self.frame_actual]

        # Escalar al tamaño del obstáculo si es necesario
        if frame.get_size() != (self.ancho, self.alto):
            frame = pygame.transform.scale(frame, (self.ancho, self.alto))

        # Aplicar offset de cámara y renderizar
        pos_x = self.x - camera_offset[0]
        pos_y = self.y - camera_offset[1]
        surface.blit(frame, (int(pos_x), int(pos_y)))

    def get_hitbox(self) -> pygame.Rect:
        """Retorna el hitbox actualizado para colisiones."""
        self.hitbox.topleft = (self.x, self.y)
        return self.hitbox


class ObstaculoPantalla(ObstaculoAnimado):
    """
    Pantalla animada 2×1 tiles.
    Spritesheet: 512×256 px (4 columnas × 4 filas)
    Frames: 13 de 16 (ignora frames 13, 14, 15)
    """

    # Cache de clase para lazy loading (primer acceso carga, resto usan caché)
    _frames_cache: Optional[List[pygame.Surface]] = None

    def __init__(self, x: float, y: float, tile_size: int):
        """
        Inicializa pantalla 2×1.

        Args:
            x, y:       Posición en el mundo
            tile_size:  Tamaño de un tile en píxeles lógicos
        """
        # Cargar frames una sola vez (lazy)
        frames = self._cargar_frames()

        # Proporciones: 2 tiles ancho × 1 tile alto
        ancho = tile_size * 2
        alto = tile_size * 1

        super().__init__(x, y, ancho, alto, frames)

    @classmethod
    def _cargar_frames(cls) -> List[pygame.Surface]:
        """Carga los 13 frames de pantalla-1.png (lazy loading)."""
        if cls._frames_cache is not None:
            return cls._frames_cache

        frames = cargar_spritesheet_cuadricula(
            ruta="assets/pantalla-1.png",
            frame_w=128,
            frame_h=64,
            cols=4,
            frames_a_usar=13,
            flip_horizontal=False,
            tamaño_logico=128
        )

        if not frames:
            # Fallback: placeholder si no carga
            placeholder = pygame.Surface((128, 64))
            placeholder.fill((100, 100, 100))
            frames = [placeholder] * 13

        cls._frames_cache = frames
        return frames

    @classmethod
    def limpiar_cache(cls) -> None:
        """Limpia el caché de frames (útil para hot-reload)."""
        cls._frames_cache = None


class ObstaculoPantalla2(ObstaculoAnimado):
    """
    Pantalla animada grande 2×2 tiles.
    Spritesheet: 512×512 px (4 columnas × 4 filas)
    Frames: 16 de 16
    """

    _frames_cache: Optional[List[pygame.Surface]] = None

    def __init__(self, x: float, y: float, tile_size: int):
        """
        Inicializa pantalla 2×2.

        Args:
            x, y:       Posición en el mundo
            tile_size:  Tamaño de un tile en píxeles lógicos
        """
        frames = self._cargar_frames()

        # Proporciones: 2 tiles ancho × 2 tiles alto
        ancho = tile_size * 2
        alto = tile_size * 2

        super().__init__(x, y, ancho, alto, frames)

    @classmethod
    def _cargar_frames(cls) -> List[pygame.Surface]:
        """Carga los 16 frames de pantalla-2.png (lazy loading)."""
        if cls._frames_cache is not None:
            return cls._frames_cache

        frames = cargar_spritesheet_cuadricula(
            ruta="assets/pantalla-2.png",
            frame_w=128,
            frame_h=128,
            cols=4,
            frames_a_usar=16,
            flip_horizontal=False,
            tamaño_logico=128
        )

        if not frames:
            # Fallback
            placeholder = pygame.Surface((128, 128))
            placeholder.fill((100, 100, 100))
            frames = [placeholder] * 16

        cls._frames_cache = frames
        return frames

    @classmethod
    def limpiar_cache(cls) -> None:
        """Limpia el caché de frames."""
        cls._frames_cache = None


class ObstaculoTubo(ObstaculoAnimado):
    """
    Tubo animado 1×2 tiles.
    Spritesheet: 256×512 px (4 columnas × 3 filas)
    Frames: 11 de 12 (ignora frames 11, 12)
    """

    _frames_cache: Optional[List[pygame.Surface]] = None

    def __init__(self, x: float, y: float, tile_size: int):
        """
        Inicializa tubo 1×2.

        Args:
            x, y:       Posición en el mundo
            tile_size:  Tamaño de un tile en píxeles lógicos
        """
        frames = self._cargar_frames()

        # Proporciones: 1 tile ancho × 2 tiles alto
        ancho = tile_size * 1
        alto = tile_size * 2

        super().__init__(x, y, ancho, alto, frames)

    @classmethod
    def _cargar_frames(cls) -> List[pygame.Surface]:
        """Carga los 11 frames de tubo-3.png (lazy loading, 4×3 grid)."""
        if cls._frames_cache is not None:
            return cls._frames_cache

        frames = cargar_spritesheet_cuadricula(
            ruta="assets/tubo-3.png",
            frame_w=64,
            frame_h=170,
            cols=4,
            frames_a_usar=11,
            flip_horizontal=False,
            tamaño_logico=170
        )

        if not frames:
            # Fallback
            placeholder = pygame.Surface((64, 170))
            placeholder.fill((50, 150, 50))
            frames = [placeholder] * 11

        cls._frames_cache = frames
        return frames

    @classmethod
    def limpiar_cache(cls) -> None:
        """Limpia el caché de frames."""
        cls._frames_cache = None
