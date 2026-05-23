"""
systems/music_manager.py

Gestor centralizado de música del juego.
Usa pygame.mixer.music para una pista a la vez.
Controla los tres momentos musicales del juego:
- Cinemática intro
- Boss fight
- Minijuego
"""

import pygame
import os
from pathlib import Path


class MusicManager:
    """
    Gestor centralizado de música del juego.
    Usa pygame.mixer.music para una pista a la vez.
    """

    # Rutas de los archivos - usar ruta absoluta basada en la ubicación del archivo
    RUTA_BASE = str(Path(__file__).parent.parent / "assets" / "audio")

    TRACKS = {
        "cinematica_intro": "cinematica_intro.mp3",
        "boss_fight":       "Boss_fight.mp3",  # Con mayúscula
        "minigame":         "minigame.mp3",
    }

    def __init__(self):
        self.track_actual = None
        self.volumen = 0.7  # 0.0 a 1.0
        self.inicializado = False
        self._inicializar_mixer()

    def _inicializar_mixer(self):
        """
        Inicializa pygame.mixer si no está inicializado.
        No reinicializa si ya está activo.
        """
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=44100,
                    size=-16,
                    channels=2,
                    buffer=512
                )
            self.inicializado = True
            print("[MUSIC] Mixer inicializado correctamente")
        except Exception as e:
            print(f"[MUSIC] Error al inicializar mixer: {e}")
            self.inicializado = False

    def _get_ruta(self, nombre_track: str) -> str:
        """Devuelve la ruta completa de un track."""
        archivo = self.TRACKS.get(nombre_track, "")
        # RUTA_BASE es ya una ruta absoluta, así que simplemente concatenar
        return os.path.join(self.RUTA_BASE, archivo)

    def reproducir(self, nombre_track: str,
                   loop: bool = True,
                   fade_in_ms: int = 500):
        """
        Reproduce un track de música.

        Args:
            nombre_track: clave del track ("cinematica_intro",
                          "boss_fight" o "minigame")
            loop: True = loop infinito, False = una vez
            fade_in_ms: milisegundos de fade in al iniciar
        """
        if not self.inicializado:
            print("[MUSIC] Mixer no inicializado, "
                  "omitiendo reproducción")
            return

        # No reiniciar si ya está sonando el mismo track
        if self.track_actual == nombre_track:
            if pygame.mixer.music.get_busy():
                return

        ruta = self._get_ruta(nombre_track)

        if not os.path.exists(ruta):
            print(f"[MUSIC] Archivo no encontrado: {ruta}")
            return

        try:
            pygame.mixer.music.load(ruta)
            pygame.mixer.music.set_volume(self.volumen)

            loops = -1 if loop else 0
            # -1 = loop infinito, 0 = reproducir una vez

            pygame.mixer.music.play(loops=loops,
                                    fade_ms=fade_in_ms)
            self.track_actual = nombre_track

            print(f"[MUSIC] Reproduciendo: {nombre_track} "
                  f"({'loop' if loop else 'una vez'})")

        except Exception as e:
            print(f"[MUSIC] Error al reproducir "
                  f"{nombre_track}: {e}")

    def detener(self, fade_out_ms: int = 800):
        """
        Detiene la música con fade out gradual.

        Args:
            fade_out_ms: milisegundos de fade out
        """
        if not self.inicializado:
            return

        if not pygame.mixer.music.get_busy():
            self.track_actual = None
            return

        try:
            if fade_out_ms > 0:
                pygame.mixer.music.fadeout(fade_out_ms)
            else:
                pygame.mixer.music.stop()

            self.track_actual = None
            print("[MUSIC] Música detenida")

        except Exception as e:
            print(f"[MUSIC] Error al detener: {e}")

    def set_volumen(self, volumen: float):
        """
        Ajusta el volumen de la música.

        Args:
            volumen: float entre 0.0 y 1.0
        """
        self.volumen = max(0.0, min(1.0, volumen))
        if self.inicializado:
            pygame.mixer.music.set_volume(self.volumen)

    def pausar(self):
        """Pausa la música sin detenerla."""
        if self.inicializado:
            pygame.mixer.music.pause()

    def reanudar(self):
        """Reanuda la música pausada."""
        if self.inicializado:
            pygame.mixer.music.unpause()

    def esta_sonando(self) -> bool:
        """Devuelve True si hay música reproduciéndose."""
        if not self.inicializado:
            return False
        return pygame.mixer.music.get_busy()


# Instancia global — importar desde cualquier módulo
music_manager = MusicManager()
