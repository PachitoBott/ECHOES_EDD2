"""
narrative/text_renderer.py
==========================
Sistema de typewriter effect para cinematics.

Responsabilidades:
  - Gestionar state del typewriter (índice de carácter, tiempo acumulado)
  - Revelar texto letra por letra basado en tiempo
  - Triggear sonido click solo para caracteres alfanuméricos
  - Proporcionar texto visible y estado (finished)

Uso:
  renderer = TextRenderer("Hello world", typewriter_fps=30,
                         typewriter_sound_path="assets/sounds/click.ogg")

  # En cada frame:
  renderer.update(dt)
  visible_text = renderer.current_text()

  # Para llenar de inmediato (usuario presiona tecla):
  renderer.force_finish()
"""

import pygame
from typing import Optional


class TextRenderer:
    """Maneja el efecto typewriter: revelación gradual de caracteres."""

    def __init__(
        self,
        text: str,
        typewriter_fps: int = 30,
        typewriter_sound_path: Optional[str] = None,
        sound_volume: float = 0.4
    ):
        """Inicializa el renderer de typewriter.

        Args:
            text: Texto completo a revelar
            typewriter_fps: Caracteres revelados por segundo (ej: 30 = 30 chars/sec)
            typewriter_sound_path: Ruta al archivo de sonido del click (opcional)
            sound_volume: Volumen del sonido (0.0-1.0)
        """
        self.text = text
        self.typewriter_fps = max(1, typewriter_fps)
        self.sound_volume = sound_volume

        # State del typewriter
        self._current_char_index = 0
        self._timer = 0.0
        self._finished = False

        # Sound
        self._typewriter_sound: Optional[pygame.mixer.Sound] = None
        if typewriter_sound_path:
            try:
                self._typewriter_sound = pygame.mixer.Sound(typewriter_sound_path)
                self._typewriter_sound.set_volume(max(0.0, min(1.0, sound_volume)))
            except (pygame.error, FileNotFoundError):
                # Fallback silencioso si el archivo no existe
                pass

        # Tracking para evitar múltiples sonidos por carácter
        self._last_char_index_played = -1

    def update(self, dt: float) -> None:
        """Avanza el typewriter según tiempo transcurrido.

        Args:
            dt: Delta time en segundos
        """
        if self._finished:
            return

        # Tiempo por carácter (en segundos)
        time_per_char = 1.0 / self.typewriter_fps
        self._timer += dt

        # Avanzar carácter si acumuló suficiente tiempo
        while (self._timer >= time_per_char and
               self._current_char_index < len(self.text)):
            self._timer -= time_per_char

            # Trigger sonido (solo para caracteres alfanuméricos)
            char = self.text[self._current_char_index]
            if (char.isalnum() and
                self._last_char_index_played != self._current_char_index):
                if self._typewriter_sound:
                    self._typewriter_sound.play()
                self._last_char_index_played = self._current_char_index

            self._current_char_index += 1

        # Marcar como terminado
        if self._current_char_index >= len(self.text):
            self._finished = True

    def current_text(self) -> str:
        """Retorna el texto visible hasta el índice actual.

        Returns:
            String con caracteres revelados hasta el momento
        """
        return self.text[:self._current_char_index]

    def is_finished(self) -> bool:
        """Retorna True si se mostró todo el texto.

        Returns:
            bool indicando si la animación de typewriter terminó
        """
        return self._finished

    def force_finish(self) -> None:
        """Llena todo el texto de inmediato (usuario presionó tecla)."""
        self._current_char_index = len(self.text)
        self._finished = True

    def reset(self) -> None:
        """Reinicia el typewriter al principio para nuevo panel."""
        self._current_char_index = 0
        self._timer = 0.0
        self._finished = False
        self._last_char_index_played = -1
