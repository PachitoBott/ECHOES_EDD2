"""
Sistema de efectos de muerte basado en código (particles + flash rojo).
Reemplaza las animaciones de muerte por efectos visuales procedurales.
Paleta de colores: Rojo en distintas intensidades (brillante → oscuro).
"""

import random
import math
import pygame
from typing import List, Optional, Tuple


class DeathParticle:
    """Una pequeña partícula que se dispersa y desvanece."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        lifetime: float = 0.5,
        size: int = 3,
        color: Tuple[int, int, int] = (255, 100, 100)
    ):
        self.x = x
        self.y = y
        self.vx = vx  # pixels/second
        self.vy = vy  # pixels/second
        self.lifetime = lifetime
        self.age = 0.0
        self.size = size
        self.color = color

    def update(self, dt: float) -> None:
        """Actualiza posición y edad de la partícula."""
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def is_alive(self) -> bool:
        """Retorna True si la partícula aún está en su lifetime."""
        return self.age < self.lifetime

    def alpha(self) -> int:
        """Retorna el valor de alpha (0-255) basado en progress de vida."""
        # Fade out lineal
        progress = self.age / self.lifetime
        return max(0, int(255 * (1.0 - progress)))

    def render(self, surf: pygame.Surface) -> None:
        """Renderiza la partícula en la superficie."""
        alpha_val = self.alpha()
        if alpha_val <= 0:
            return

        # Crear superficie pequeña con la partícula
        size_surf = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            size_surf,
            (*self.color, alpha_val),
            (self.size, self.size),
            self.size
        )
        surf.blit(size_surf, (int(self.x - self.size), int(self.y - self.size)))


class DeathEffect:
    """Maneja un evento de muerte: flash rojo + partículas dispersas en paleta roja."""

    # Paleta de rojos — colores consistentes para todo el juego
    COLOR_HEAD    = (255, 40,  40)   # rojo brillante (partículas recientes)
    COLOR_MID     = (200, 25,  25)   # rojo medio
    COLOR_TAIL    = (120, 10,  10)   # rojo oscuro (partículas viejas)
    COLOR_DEEP    = (60,  5,   5)    # rojo casi negro (desvaneciendo)

    def __init__(
        self,
        x: float,
        y: float,
        sprite_width: int,
        sprite_height: int,
        lifetime: float = 0.5,
        num_particles: int = 20,
        particle_speed_min: float = 80.0,
        particle_speed_max: float = 200.0,
        particle_color: Tuple[int, int, int] = (255, 40, 40)
    ):
        self.x = x
        self.y = y
        self.sprite_width = sprite_width
        self.sprite_height = sprite_height
        self.lifetime = lifetime
        self.age = 0.0

        # Flash rojo (primeros frames) — paleta consistente con enemigos
        self.flash_duration = 0.15  # 150ms de flash rojo

        # Partículas dispersas
        self.particles: List[DeathParticle] = []
        self._spawn_particles(
            num_particles,
            particle_speed_min,
            particle_speed_max,
            particle_color
        )

    def _spawn_particles(
        self,
        count: int,
        speed_min: float,
        speed_max: float,
        color: Tuple[int, int, int]
    ) -> None:
        """
        Genera partículas en direcciones aleatorias con paleta roja.
        Los tonos de rojo varían de brillante (reciente) a oscuro (desvaneciendo).
        """
        center_x = self.x + self.sprite_width / 2
        center_y = self.y + self.sprite_height / 2

        # Paleta de rojos disponibles
        red_palette = [self.COLOR_HEAD, self.COLOR_MID, self.COLOR_TAIL, self.COLOR_DEEP]

        for _ in range(count):
            # Dirección aleatoria (radiante)
            angle = random.uniform(0, math.tau)
            speed = random.uniform(speed_min, speed_max)

            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed

            # Offset ligeramente aleatorio desde el centro
            offset_x = random.uniform(-self.sprite_width / 4, self.sprite_width / 4)
            offset_y = random.uniform(-self.sprite_height / 4, self.sprite_height / 4)

            # Color rojo aleatorio de la paleta (para variación visual)
            particle_color = random.choice(red_palette)

            particle = DeathParticle(
                center_x + offset_x,
                center_y + offset_y,
                vx,
                vy,
                lifetime=self.lifetime,
                size=random.randint(2, 4),
                color=particle_color
            )
            self.particles.append(particle)

    def update(self, dt: float) -> None:
        """Actualiza edad y partículas."""
        self.age += dt
        for particle in self.particles:
            if particle.is_alive():
                particle.update(dt)

    def is_alive(self) -> bool:
        """Retorna True si el efecto aún está activo."""
        return self.age < self.lifetime

    def should_flash(self) -> bool:
        """Retorna True si el flash rojo debe mostrarse."""
        return self.age < self.flash_duration

    def render(self, surf: pygame.Surface) -> None:
        """Renderiza partículas vivas."""
        for particle in self.particles:
            if particle.is_alive():
                particle.render(surf)


class DeathEffectManager:
    """Gestor global de todos los efectos de muerte activos."""

    def __init__(self):
        self.effects: List[DeathEffect] = []

    def spawn(
        self,
        x: float,
        y: float,
        sprite_width: int = 96,
        sprite_height: int = 96,
        lifetime: float = 0.5,
        num_particles: int = 25,
        particle_color: Tuple[int, int, int] = (255, 40, 40)
    ) -> None:
        """Crea un nuevo efecto de muerte con partículas rojo brillante."""
        effect = DeathEffect(
            x,
            y,
            sprite_width,
            sprite_height,
            lifetime=lifetime,
            num_particles=num_particles,
            particle_color=particle_color
        )
        self.effects.append(effect)

    def update(self, dt: float) -> None:
        """Actualiza todos los efectos activos y limpia los muertos."""
        # Actualizar efectos vivos
        for effect in self.effects[:]:
            effect.update(dt)
            if not effect.is_alive():
                self.effects.remove(effect)

    def render(self, surf: pygame.Surface) -> None:
        """Renderiza todos los efectos activos."""
        for effect in self.effects:
            effect.render(surf)

    def clear(self) -> None:
        """Limpia todos los efectos (útil para cambios de sala)."""
        self.effects.clear()

    def has_active_effects(self) -> bool:
        """Retorna True si hay efectos activos."""
        return len(self.effects) > 0
