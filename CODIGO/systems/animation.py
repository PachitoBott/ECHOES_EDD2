"""
systems/animation.py
====================
Sistema genérico de animaciones basado en spritesheets horizontales.

Responsabilidades:
  - Cargar una spritesheet horizontal (frames en una sola fila)
  - Dividir la imagen en frames individuales
  - Reproducir frames específicos en un orden configurable
  - Manejar timing (FPS) y loop/no-loop
  - Proporcionar el frame actual para renderizar

Uso:
  anim_manager = AnimationManager.load_from_json("assets/sprites/player/animations.json", "assets/sprites/player")
  animations = anim_manager  # dict[str, Animation]

  # En cada frame del juego:
  animations["idle"].update(dt)
  current_sprite = animations["idle"].current_frame()
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import pygame


class SpriteSheet:
    """Carga una spritesheet horizontal y la divide en frames."""

    def __init__(
        self,
        image_path: str,
        total_frames: int,
        frame_width: int,
        frame_height: int
    ):
        """Carga y divide una spritesheet en frames individuales.

        Args:
            image_path: ruta al PNG de la spritesheet
            total_frames: cantidad total de frames en la spritesheet (horizontales)
            frame_width: ancho de cada frame en píxeles
            frame_height: alto de cada frame en píxeles

        Raises:
            FileNotFoundError: si el PNG no existe
            ValueError: si el tamaño no coincide con total_frames
        """
        self.image_path = image_path
        self.total_frames = total_frames
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._frames: List[pygame.Surface] = []

        self._load_and_divide()

    def _load_and_divide(self) -> None:
        """Carga el PNG y lo divide en frames (soporta cuadrículas 2D)."""
        path = Path(self.image_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontró spritesheet: {self.image_path}")

        # Cargar imagen
        try:
            image = pygame.image.load(path.as_posix()).convert_alpha()
        except pygame.error as e:
            raise ValueError(f"No se pudo cargar {self.image_path}: {e}")

        actual_width, actual_height = image.get_size()

        # Calcular disposición (fila o cuadrícula)
        cols = actual_width // self.frame_width
        rows = actual_height // self.frame_height
        total_in_grid = cols * rows

        # Validar que total_frames no exceda los espacios disponibles
        if self.total_frames > total_in_grid:
            raise ValueError(
                f"Spritesheet '{path.name}' tiene {actual_width}x{actual_height}, "
                f"que cabe {cols}x{rows}={total_in_grid} frames de {self.frame_width}x{self.frame_height}, "
                f"pero se pedían {self.total_frames} frames"
            )

        # Dividir en frames (izquierda a derecha, arriba a abajo)
        for frame_idx in range(self.total_frames):
            col = frame_idx % cols
            row = frame_idx // cols
            x = col * self.frame_width
            y = row * self.frame_height
            rect = pygame.Rect(x, y, self.frame_width, self.frame_height)
            frame = image.subsurface(rect).copy().convert_alpha()
            self._frames.append(frame)

    def get_frames(self) -> List[pygame.Surface]:
        """Retorna la lista de todos los frames."""
        return self._frames


class Animation:
    """Maneja la reproducción de una animación con frames específicos."""

    def __init__(
        self,
        frames: List[pygame.Surface],
        frame_indices: List[int],
        fps: int,
        loop: bool = True
    ):
        """Crea una animación que reproduce frames específicos.

        Args:
            frames: lista de todos los frames disponibles (pool)
            frame_indices: índices de qué frames reproducir y en qué orden
            fps: frames por segundo
            loop: si True, repite desde el principio; si False, se queda en el último
        """
        self._frames_pool = frames  # Todos los frames disponibles
        self._frame_indices = frame_indices  # Qué frames reproducir
        self._fps = max(1, fps)  # Mínimo 1 FPS para evitar división por cero
        self._loop = loop

        # Estado
        self._current_index = 0  # Índice en frame_indices (0-based)
        self._timer = 0.0
        self._finished = False

    def reset(self) -> None:
        """Reinicia la animación al primer frame."""
        self._current_index = 0
        self._timer = 0.0
        self._finished = False

    def update(self, dt: float) -> None:
        """Avanza la animación según el tiempo transcurrido.

        Args:
            dt: delta time en segundos desde el último update
        """
        # Si ya terminó (no-loop), no avanzar
        if self._finished and not self._loop:
            return

        frame_duration = 1.0 / self._fps
        self._timer += dt

        # Avanzar frames según el tiempo acumulado
        while self._timer >= frame_duration:
            self._timer -= frame_duration
            self._current_index += 1

            # Si llegamos al final
            if self._current_index >= len(self._frame_indices):
                if self._loop:
                    # Reiniciar desde el principio
                    self._current_index = 0
                else:
                    # Quedarse en el último frame
                    self._current_index = len(self._frame_indices) - 1
                    self._finished = True
                    break

    def current_frame(self) -> pygame.Surface:
        """Retorna el frame actual a renderizar."""
        if not self._frame_indices or not self._frames_pool:
            # Fallback: retornar una superficie vacía
            return pygame.Surface((1, 1))

        frame_num = self._frame_indices[self._current_index]
        if frame_num < 0 or frame_num >= len(self._frames_pool):
            # Índice inválido
            return pygame.Surface((1, 1))

        return self._frames_pool[frame_num]

    def is_finished(self) -> bool:
        """True si la animación (no-loop) ha terminado."""
        return self._finished

    def set_fps(self, fps: int) -> None:
        """Cambia la velocidad de reproducción (FPS)."""
        self._fps = max(1, fps)


class AnimationManager:
    """Carga animaciones desde archivo JSON + spritesheets."""

    @staticmethod
    def load_from_json(
        json_path: str,
        sprite_base_dir: str
    ) -> Dict[str, Animation]:
        """Carga todas las animaciones desde JSON + spritesheets.

        Args:
            json_path: ruta al archivo animations.json
            sprite_base_dir: directorio base donde están los PNGs

        Returns:
            dict[nombre_animación] -> Animation

        Raises:
            FileNotFoundError: si el JSON no existe
            ValueError: si la estructura del JSON es inválida
        """
        json_file = Path(json_path)
        if not json_file.exists():
            raise FileNotFoundError(f"No se encontró {json_path}")

        # Cargar configuración
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido en {json_path}: {e}")

        # Validar estructura
        if 'frame_width' not in config or 'frame_height' not in config:
            raise ValueError("JSON debe contener 'frame_width' y 'frame_height'")
        if 'animations' not in config:
            raise ValueError("JSON debe contener 'animations'")

        frame_width = config['frame_width']
        frame_height = config['frame_height']

        # Cargar cada animación
        animations: Dict[str, Animation] = {}
        base_path = Path(sprite_base_dir)

        for anim_name, anim_config in config['animations'].items():
            try:
                # Validar campos requeridos
                required = ['file', 'total_frames', 'frame_indices', 'fps', 'loop']
                for field in required:
                    if field not in anim_config:
                        raise ValueError(f"Animación '{anim_name}' falta el campo '{field}'")

                # Cargar spritesheet
                image_path = str(base_path / anim_config['file'])
                spritesheet = SpriteSheet(
                    image_path,
                    anim_config['total_frames'],
                    frame_width,
                    frame_height
                )

                # Crear Animation
                animation = Animation(
                    frames=spritesheet.get_frames(),
                    frame_indices=anim_config['frame_indices'],
                    fps=anim_config['fps'],
                    loop=anim_config['loop']
                )

                animations[anim_name] = animation

            except (FileNotFoundError, ValueError) as e:
                # Log error pero continuar cargando otras animaciones
                print(f"[WARNING] No se pudo cargar animación '{anim_name}': {e}")

        if not animations:
            raise ValueError("No se cargó ninguna animación exitosamente")

        return animations
