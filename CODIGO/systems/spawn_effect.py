"""
Sistema de efectos de spawn para el jugador (inverso del efecto de muerte).
Partículas blancas convergentes + silueta del sprite con fade in.
"""

import random
import math
import pygame
from typing import List, Optional, Tuple


class SpawnParticle:
    """Una partícula blanca que converge hacia el centro y desvanece."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        lifetime: float = 0.5,
        size: int = 3,
        color: Tuple[int, int, int] = (255, 255, 255)
    ):
        self.x = x
        self.y = y
        self.vx = vx  # pixels/second (negativo, hacia adentro)
        self.vy = vy  # pixels/second (negativo, hacia adentro)
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
        """Retorna alpha: comienza opaco, desvanece hacia final."""
        progress = self.age / self.lifetime
        return max(0, int(255 * (1.0 - progress)))

    def render(self, surf: pygame.Surface) -> None:
        """Renderiza la partícula en la superficie."""
        alpha_val = self.alpha()
        if alpha_val <= 0:
            return

        size_surf = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            size_surf,
            (*self.color, alpha_val),
            (self.size, self.size),
            self.size
        )
        surf.blit(size_surf, (int(self.x - self.size), int(self.y - self.size)))


class SpawnEffect:
    """Maneja efecto de spawn: partículas blancas convergentes + sprite fade in."""

    # Color blanco para el efecto
    COLOR_WHITE = (255, 255, 255)

    def __init__(
        self,
        x: float,
        y: float,
        sprite: pygame.Surface,
        lifetime: float = 0.5,
        num_particles: int = 25,
        particle_speed_min: float = 80.0,
        particle_speed_max: float = 200.0,
    ):
        self.x = x
        self.y = y
        self.sprite = sprite
        self.sprite_width = sprite.get_width()
        self.sprite_height = sprite.get_height()
        self.lifetime = lifetime
        self.age = 0.0

        # Duración del fade in de la silueta blanca
        self.fade_in_duration = lifetime

        # Partículas convergentes (inverso de muerte)
        self.particles: List[SpawnParticle] = []
        self._spawn_particles(num_particles, particle_speed_min, particle_speed_max)

    def _spawn_particles(
        self,
        count: int,
        speed_min: float,
        speed_max: float,
    ) -> None:
        """
        Genera partículas blancas que convergen hacia el centro.
        Opuesto al efecto de muerte (que dispersa partículas).
        """
        center_x = self.x + self.sprite_width / 2
        center_y = self.y + self.sprite_height / 2

        for _ in range(count):
            # Dirección aleatoria (radiante) desde donde salen
            angle = random.uniform(0, math.tau)
            speed = random.uniform(speed_min, speed_max)

            # Velocidad hacia adentro (negativa, hacia el centro)
            vx = -math.cos(angle) * speed
            vy = -math.sin(angle) * speed

            # Posición inicial: fuera del sprite
            distance = random.uniform(self.sprite_width / 2, self.sprite_width * 0.75)
            start_x = center_x + math.cos(angle) * distance
            start_y = center_y + math.sin(angle) * distance

            particle = SpawnParticle(
                start_x,
                start_y,
                vx,
                vy,
                lifetime=self.lifetime,
                size=random.randint(2, 4),
                color=self.COLOR_WHITE
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

    def get_sprite_alpha(self) -> int:
        """
        Retorna el alpha de la silueta del sprite.
        Comienza en blanco (255), fade in al normal (0).
        """
        progress = self.age / self.fade_in_duration
        # Comienza opaco (255), desvanece a 0
        return max(0, int(255 * (1.0 - progress)))

    def render(self, surf: pygame.Surface) -> None:
        """Renderiza partículas y silueta del sprite."""
        # Renderizar partículas convergentes
        for particle in self.particles:
            if particle.is_alive():
                particle.render(surf)

        # Renderizar silueta blanca del sprite (fade in)
        sprite_alpha = self.get_sprite_alpha()
        if sprite_alpha > 0:
            # Crear una versión blanca del sprite
            white_sprite = self.sprite.copy()
            white_surface = pygame.Surface(white_sprite.get_size(), pygame.SRCALPHA)
            white_surface.fill((255, 255, 255, sprite_alpha))
            white_sprite.blit(white_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            # Renderizar en la posición del jugador
            surf.blit(white_sprite, (int(self.x), int(self.y)))


class SpawnEffectManager:
    """Gestor global para efectos de spawn del jugador."""

    def __init__(self):
        self.effects: List[SpawnEffect] = []

    def spawn(
        self,
        x: float,
        y: float,
        sprite: pygame.Surface,
        lifetime: float = 0.5,
        num_particles: int = 25,
    ) -> None:
        """Crea un nuevo efecto de spawn con partículas blancas convergentes."""
        effect = SpawnEffect(
            x,
            y,
            sprite,
            lifetime=lifetime,
            num_particles=num_particles,
        )
        self.effects.append(effect)

    def update(self, dt: float) -> None:
        """Actualiza todos los efectos activos y limpia los completados."""
        for effect in self.effects[:]:
            effect.update(dt)
            if not effect.is_alive():
                self.effects.remove(effect)

    def render(self, surf: pygame.Surface) -> None:
        """Renderiza todos los efectos activos."""
        for effect in self.effects:
            effect.render(surf)

    def clear(self) -> None:
        """Limpia todos los efectos."""
        self.effects.clear()

    def has_active_effects(self) -> bool:
        """Retorna True si hay efectos activos."""
        return len(self.effects) > 0
