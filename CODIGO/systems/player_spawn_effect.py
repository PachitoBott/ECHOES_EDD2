"""
Sistema de efectos visuales para el respawn del jugador.

Incluye:
- Flash blanco inicial
- Partículas convergentes
- Transición suave a visibilidad normal
"""

import math
import random
from dataclasses import dataclass
from typing import List

import pygame


@dataclass
class SpawnParticle:
    """Partícula individual del efecto de spawn."""
    x: float
    y: float
    vx: float
    vy: float
    life: float  # Tiempo de vida restante en segundos
    max_life: float  # Duración total


class PlayerSpawnEffect:
    """
    Efecto visual para el respawn del jugador.

    Fases:
    - Phase 1 (0-18 frames): Flash blanco intenso, partículas aparecen y convergen
    - Phase 2 (18-38 frames): Transición suave a normal
    """

    # Duración de cada fase (en frames a ~60 FPS)
    DURATION_FLASH = 18  # frames
    DURATION_NORMAL = 20  # frames
    TOTAL_DURATION = DURATION_FLASH + DURATION_NORMAL

    # Configuración de partículas
    NUM_PARTICLES = 30
    PARTICLE_RADIUS = 160  # Radio de spawn inicial
    PARTICLE_SIZE = 3  # Radio visual de cada partícula
    PARTICLE_LIFETIME = 0.4  # segundos

    def __init__(self):
        self.frame_counter = 0
        self.particles: List[SpawnParticle] = []
        self.is_active = False
        self.player_center_x = 0.0
        self.player_center_y = 0.0

    def spawn(self, player_center_x: float, player_center_y: float) -> None:
        """
        Inicia el efecto de spawn en la posición del jugador.

        Args:
            player_center_x: Coordenada X del centro del jugador
            player_center_y: Coordenada Y del centro del jugador
        """
        self.is_active = True
        self.frame_counter = 0
        self.player_center_x = player_center_x
        self.player_center_y = player_center_y
        self.particles.clear()
        self._spawn_particles()

    def _spawn_particles(self) -> None:
        """Genera las partículas iniciales alrededor del jugador."""
        for _ in range(self.NUM_PARTICLES):
            # Ángulo aleatorio alrededor del jugador
            angle = random.uniform(0, 2 * math.pi)

            # Posición inicial fuera del jugador (en radio PARTICLE_RADIUS)
            spawn_x = self.player_center_x + math.cos(angle) * self.PARTICLE_RADIUS
            spawn_y = self.player_center_y + math.sin(angle) * self.PARTICLE_RADIUS

            # Velocidad dirigida hacia el centro del jugador
            # Duración aproximada: PARTICLE_LIFETIME segundos
            dist = self.PARTICLE_RADIUS
            duration_sec = self.PARTICLE_LIFETIME
            speed = dist / duration_sec

            vx = -math.cos(angle) * speed
            vy = -math.sin(angle) * speed

            particle = SpawnParticle(
                x=spawn_x,
                y=spawn_y,
                vx=vx,
                vy=vy,
                life=self.PARTICLE_LIFETIME,
                max_life=self.PARTICLE_LIFETIME
            )
            self.particles.append(particle)

    def update(self, dt: float) -> None:
        """
        Actualiza el efecto de spawn.

        Args:
            dt: Delta time en segundos
        """
        if not self.is_active:
            return

        # Incrementar contador de frames (aproximado basado en dt)
        self.frame_counter += dt * 60  # Normalizar a ~60 FPS

        # Actualizar partículas
        for particle in self.particles[:]:
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.life -= dt

            if particle.life <= 0:
                self.particles.remove(particle)

        # Marcar como inactivo cuando termine
        if self.frame_counter >= self.TOTAL_DURATION:
            self.is_active = False
            self.particles.clear()

    def get_flash_alpha(self) -> int:
        """
        Retorna el valor de alpha para el flash blanco (0-255).

        Returns:
            Valor de alpha: 255 durante el flash, 0 después
        """
        if self.frame_counter < self.DURATION_FLASH:
            # Durante el flash: mantener máximo
            return 255
        elif self.frame_counter < self.TOTAL_DURATION:
            # Transición suave a 0
            progress = (self.frame_counter - self.DURATION_FLASH) / self.DURATION_NORMAL
            return int(255 * (1.0 - progress))
        else:
            return 0

    def draw_particles(self, surface: pygame.Surface, screen_scale: int = 1) -> None:
        """
        Dibuja las partículas en la pantalla.

        Args:
            surface: Superficie pygame donde dibujar
            screen_scale: Factor de escala de pantalla
        """
        if not self.is_active or not self.particles:
            return

        for particle in self.particles:
            # Alpha basado en vida restante
            alpha = int(255 * (particle.life / particle.max_life))

            # Color blanco con alpha
            color = (255, 255, 255, alpha)

            # Posición escalada
            x = int(particle.x * screen_scale)
            y = int(particle.y * screen_scale)
            radius = self.PARTICLE_SIZE * screen_scale

            # Crear superficie para la partícula con alpha
            particle_surf = pygame.Surface(
                (radius * 2, radius * 2),
                pygame.SRCALPHA
            )
            pygame.draw.circle(
                particle_surf,
                color,
                (radius, radius),
                radius
            )

            # Blitear en la posición correcta
            surface.blit(particle_surf, (x - radius, y - radius))

    def is_finished(self) -> bool:
        """Retorna True si el efecto ha terminado."""
        return not self.is_active


class SpawnEffectManager:
    """Gestor centralizado de efectos de spawn para todos los jugadores."""

    def __init__(self):
        self.player1_effect = PlayerSpawnEffect()
        self.player2_effect = PlayerSpawnEffect()

    def spawn_player1(self, x: float, y: float) -> None:
        """Inicia efecto de spawn para jugador 1."""
        self.player1_effect.spawn(x, y)

    def spawn_player2(self, x: float, y: float) -> None:
        """Inicia efecto de spawn para jugador 2."""
        self.player2_effect.spawn(x, y)

    def update(self, dt: float) -> None:
        """Actualiza ambos efectos."""
        self.player1_effect.update(dt)
        self.player2_effect.update(dt)

    def draw_particles(self, surface: pygame.Surface, screen_scale: int = 1) -> None:
        """Dibuja partículas de ambos efectos."""
        self.player1_effect.draw_particles(surface, screen_scale)
        self.player2_effect.draw_particles(surface, screen_scale)

    def get_player1_flash_alpha(self) -> int:
        """Retorna alpha del flash para jugador 1."""
        return self.player1_effect.get_flash_alpha()

    def get_player2_flash_alpha(self) -> int:
        """Retorna alpha del flash para jugador 2."""
        return self.player2_effect.get_flash_alpha()

    def is_active(self) -> bool:
        """True si algún efecto está activo."""
        return self.player1_effect.is_active or self.player2_effect.is_active
