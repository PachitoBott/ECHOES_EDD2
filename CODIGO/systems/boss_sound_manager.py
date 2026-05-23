"""
Sistema de sonidos para el Boss.

Maneja:
- Sonido idle (reposo) en loop continuo
- Sonidos de ataque específicos (Fanout, Zigzag, Laser, EMP)
- Transiciones suave entre idle y ataques
- Detención segura al morir

Independiente de MusicManager (canales separados).
"""

from pathlib import Path
import pygame
from typing import Optional


class BossSoundManager:
    """Gestor de sonidos para el boss."""

    # Rutas de archivos de sonido
    SONIDOS = {
        "idle": "assets/audio/sonido_idle.mp3",
        "fanout": "assets/audio/sonido_Fan.mp3",
        "zigzag": "assets/audio/sonido_zigzag.mp3",
        "laser": "assets/audio/sonido_laser.mp3",
        "emp": "assets/audio/sonido_emp.mp3",
        "proyectil": "assets/audio/boss_projectile_sfx.mp3",
    }

    def __init__(self, volumen_idle: float = 0.15):
        """
        Inicializa el gestor de sonidos del boss.

        Args:
            volumen_idle: Volumen del sonido idle (0.0-1.0)
        """
        # Asegurar que mixer está inicializado
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except pygame.error:
                pass

        # Configurar canales (independientes de música)
        try:
            pygame.mixer.set_num_channels(8)
        except pygame.error:
            pass  # Si falla, usar default

        # Almacenar sonidos cargados
        self.sonidos: dict[str, Optional[pygame.mixer.Sound]] = {}
        self._cargar_sonidos()

        # Estado del idle
        self.canal_idle: Optional[pygame.mixer.Channel] = None
        self.idle_activo = False
        self.volumen_idle = volumen_idle

        # Temporizadores para transiciones
        self._detener_idle_timer = 0.0
        self._reanudar_idle_timer = 0.0
        self._detener_en_progreso = False
        self._reanudar_pendiente = False

    def _cargar_sonidos(self) -> None:
        """Carga todos los archivos de sonido del boss."""
        # Volúmenes específicos para cada sonido
        volumenes = {
            "idle": 1.0,      # Volumen normal para idle (se ajusta con self.volumen_idle)
            "fanout": 1.0,    # Volumen normal para Fanout
            "zigzag": 1.0,    # Volumen normal para Zigzag
            "laser": 0.5,     # Laser al 50% (bajado por ser muy fuerte)
            "emp": 1.0,       # Volumen normal para EMP
            "proyectil": 0.6, # Proyectil dividido al 60% (bajado para no ser tan fuerte)
        }

        for nombre, ruta in self.SONIDOS.items():
            try:
                path = Path(ruta)
                if not path.exists():
                    # Intentar ruta relativa desde CODIGO
                    path = Path(__file__).parent.parent / ruta

                if path.exists():
                    self.sonidos[nombre] = pygame.mixer.Sound(str(path))
                    # Establecer volumen específico para este sonido
                    if self.sonidos[nombre] and nombre in volumenes:
                        self.sonidos[nombre].set_volume(volumenes[nombre])
                else:
                    print(f"[BOSS SOUND] Advertencia: No se encontró {ruta}")
                    self.sonidos[nombre] = None
            except (pygame.error, FileNotFoundError) as e:
                print(f"[BOSS SOUND] Error al cargar {nombre}: {e}")
                self.sonidos[nombre] = None

    def iniciar_idle(self) -> None:
        """Inicia el sonido idle en loop continuo."""
        if self.idle_activo:
            return

        sonido = self.sonidos.get("idle")
        if not sonido:
            return

        try:
            # Obtener canal disponible
            self.canal_idle = pygame.mixer.find_channel()
            if self.canal_idle:
                self.canal_idle.play(sonido, loops=-1)
                self.canal_idle.set_volume(self.volumen_idle)
                self.idle_activo = True
        except pygame.error:
            pass

    def detener_idle(self, fade_ms: int = 100) -> None:
        """
        Detiene el sonido idle con fade out suave.

        Args:
            fade_ms: Duración del fade en milisegundos
        """
        if not self.idle_activo or not self.canal_idle:
            return

        try:
            self.canal_idle.fadeout(fade_ms)
            self.idle_activo = False
            self._detener_en_progreso = True
            self._detener_idle_timer = fade_ms / 1000.0
        except pygame.error:
            pass

    def reanudar_idle(self, delay_ms: int = 400) -> None:
        """
        Reanuda el sonido idle después de un ataque.

        Args:
            delay_ms: Milisegundos de espera antes de reanudar
        """
        if self.idle_activo:
            return

        # Programar reanudación con delay
        self._reanudar_pendiente = True
        self._reanudar_idle_timer = delay_ms / 1000.0

    def reproducir_ataque(self, tipo_ataque: str) -> None:
        """
        Reproduce el sonido de un ataque específico.

        Args:
            tipo_ataque: Tipo de ataque ("fanout", "zigzag", "laser", "emp")
        """
        # Detener idle cuando comienza el ataque
        if self.idle_activo:
            self.detener_idle(fade_ms=100)

        sonido = self.sonidos.get(tipo_ataque)
        if not sonido:
            return

        try:
            # Buscar canal disponible (diferente al del idle)
            canal = pygame.mixer.find_channel()
            if canal:
                canal.play(sonido)
        except pygame.error:
            pass

    def reproducir_sonido_proyectil(self) -> None:
        """Reproduce el sonido cuando los proyectiles del Fanout se dividen."""
        sonido = self.sonidos.get("proyectil")
        if not sonido:
            return

        try:
            # Buscar canal disponible para el sonido de proyectil
            canal = pygame.mixer.find_channel()
            if canal:
                canal.play(sonido)
        except pygame.error:
            pass

    def detener_todo(self) -> None:
        """Detiene todos los sonidos del boss (muerte, etc)."""
        # Detener canal idle
        if self.canal_idle:
            try:
                self.canal_idle.stop()
            except pygame.error:
                pass
            self.canal_idle = None

        # Detener todos los sonidos
        self.idle_activo = False
        self._reanudar_pendiente = False
        self._detener_en_progreso = False

    def update(self, dt: float) -> None:
        """
        Actualiza los temporizadores de transición.

        Args:
            dt: Delta time en segundos
        """
        # Procesar detención con fade
        if self._detener_en_progreso:
            self._detener_idle_timer -= dt
            if self._detener_idle_timer <= 0:
                self._detener_en_progreso = False

        # Procesar reanudación con delay
        if self._reanudar_pendiente:
            self._reanudar_idle_timer -= dt
            if self._reanudar_idle_timer <= 0:
                self._reanudar_pendiente = False
                self.iniciar_idle()

    def set_volumen_idle(self, volumen: float) -> None:
        """
        Ajusta el volumen del sonido idle.

        Args:
            volumen: Volumen (0.0-1.0)
        """
        self.volumen_idle = max(0.0, min(1.0, volumen))
        if self.canal_idle and self.idle_activo:
            try:
                self.canal_idle.set_volume(self.volumen_idle)
            except pygame.error:
                pass
