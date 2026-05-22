"""Definiciones y factoría de armas del jugador."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

from core.Projectile import Projectile


@dataclass(frozen=True)
class WeaponSpec:
    weapon_id: str
    cooldown: float
    spread_deg: float
    bullet_speed: float
    projectile_radius: int = 3
    offsets: Sequence[float] = field(default_factory=lambda: (0.0,))
    forward_spawn: float = 8.0
    projectile_color: tuple[int, int, int] | None = None
    on_hit_effects: Sequence[dict[str, Any]] = field(default_factory=tuple)
    special: dict[str, Any] = field(default_factory=dict)


class Weapon:
    """Instancia runtime de un arma concreta."""

    # Factor de cuánto momentum hereda la bala (0.0 = sin momentum, 0.55 = pronunciado)
    BALA_MOMENTUM_FACTOR = 0.55

    def __init__(self, spec: WeaponSpec, cooldown_scale: float = 1.0) -> None:
        self.spec = spec
        self._cooldown = 0.0
        self._cooldown_scale = max(0.05, cooldown_scale)
        self._time_since_last_shot = 999.0
        self._continuous_fire_time = 0.0

    # ------------------------- Temporización -------------------------
    def tick(self, dt: float) -> None:
        """Avanza el tiempo del arma: decremente cooldown (cadencia de disparo)."""
        self._cooldown = max(0.0, self._cooldown - dt)
        self._time_since_last_shot = min(10.0, self._time_since_last_shot + dt)
        self._update_heat(dt)

    def can_fire(self) -> bool:
        """Verifica si el arma puede disparar (cadencia lista)."""
        return self._cooldown <= 0.0

    # ----------------------------- Estado (Munición eliminada) ---------

    # ------------------------ Generación balas -----------------------
    def fire(self, origin: tuple[float, float], direction: tuple[int, int],
             player_vel_x: float = 0.0, player_vel_y: float = 0.0) -> List[Projectile]:
        """Dispara proyectiles en una dirección cardinal.

        Args:
            origin: (ox, oy) - posición de origen del disparo
            direction: (dir_x, dir_y) - dirección cardinal (0,-1) arriba, (0,1) abajo,
                                       (-1,0) izquierda, (1,0) derecha
            player_vel_x: velocidad X actual del jugador para momentum heredado
            player_vel_y: velocidad Y actual del jugador para momentum heredado
        """
        if not self.can_fire():
            return []

        ox, oy = origin
        dir_x, dir_y = direction  # Ya está normalizado como cardinal

        bullets: List[Projectile] = []
        for offset in self.spec.offsets:
            # Desplazamiento perpendicular para soportar múltiples cañones
            # Si dispara arriba/abajo (dir_y != 0), offsets van a los lados (±dir_x, 0)
            # Si dispara izquierda/derecha (dir_x != 0), offsets van arriba/abajo (0, ±dir_y)
            perp_x, perp_y = -dir_y, dir_x
            spawn_x = ox + dir_x * self.spec.forward_spawn + perp_x * offset
            spawn_y = oy + dir_y * self.spec.forward_spawn + perp_y * offset

            # Velocidad base de la bala en la dirección de disparo
            vel_x_base = float(dir_x) * self.spec.bullet_speed
            vel_y_base = float(dir_y) * self.spec.bullet_speed

            # Aplicar momentum heredado del movimiento del jugador
            # La bala recibe una fracción de la velocidad del jugador
            vel_x_final = vel_x_base + player_vel_x * self.BALA_MOMENTUM_FACTOR
            vel_y_final = vel_y_base + player_vel_y * self.BALA_MOMENTUM_FACTOR

            # Recalcular dx, dy normalizados con la velocidad final
            vel_mag = math.hypot(vel_x_final, vel_y_final)
            if vel_mag > 0:
                dx_final = vel_x_final / vel_mag
                dy_final = vel_y_final / vel_mag
                speed_final = vel_mag
            else:
                dx_final = float(dir_x)
                dy_final = float(dir_y)
                speed_final = self.spec.bullet_speed

            # En sistema cardinal, sin spread angular
            bullets.append(
                Projectile(
                    spawn_x,
                    spawn_y,
                    dx_final,  # Dirección con momentum incluido
                    dy_final,
                    speed=speed_final,
                    radius=self.spec.projectile_radius,
                    color=self.spec.projectile_color,
                    effects=[dict(effect) for effect in self.spec.on_hit_effects],
                )
            )

        self._apply_special_on_fire()
        heat_multiplier = self._heat_penalty_multiplier()
        self._cooldown = self.spec.cooldown * self._cooldown_scale * heat_multiplier
        self._time_since_last_shot = 0.0
        return bullets

    # ----------------------- Ajustes dinámicos -----------------------
    def set_cooldown_scale(self, cooldown_scale: float) -> None:
        """Permite modificar el multiplicador de recarga en runtime."""
        self._cooldown_scale = max(0.05, cooldown_scale)

    # -------------------------- Especiales --------------------------
    def _effective_spread_deg(self) -> float:
        """Calcula el spread efectivo del arma con especiales como recoil_ramp."""
        base = self.spec.spread_deg
        recoil_cfg = self.spec.special.get("recoil_ramp")
        if recoil_cfg:
            # El spread aumenta durante disparo continuo
            # Se resetea si pasa tiempo sin disparar (basado en gracia del sistema)
            grace = float(recoil_cfg.get("grace", 0.5))  # Tiempo para resetear recoil
            if self._time_since_last_shot <= grace:
                # En disparo continuo: aplicar recoil progresivo
                extra = float(recoil_cfg.get("extra", 0.0))
                base += extra
        return base

    def _update_heat(self, dt: float) -> None:
        heat_cfg = self.spec.special.get("heat")
        if not heat_cfg:
            return
        grace = float(heat_cfg.get("grace", 0.28))
        if self._time_since_last_shot > grace:
            decay = float(heat_cfg.get("decay", 3.5))
            self._continuous_fire_time = max(0.0, self._continuous_fire_time - decay * dt)

    def _apply_special_on_fire(self) -> None:
        heat_cfg = self.spec.special.get("heat")
        if heat_cfg:
            threshold = max(0.05, float(heat_cfg.get("threshold", 2.0)))
            if self._time_since_last_shot <= float(heat_cfg.get("grace", 0.28)):
                self._continuous_fire_time = min(
                    threshold + 2.0,
                    self._continuous_fire_time + self._time_since_last_shot,
                )
            else:
                self._continuous_fire_time = max(
                    0.0, self._continuous_fire_time - float(heat_cfg.get("decay", 3.5))
                )

    def _heat_penalty_multiplier(self) -> float:
        heat_cfg = self.spec.special.get("heat")
        if not heat_cfg:
            return 1.0
        threshold = max(0.05, float(heat_cfg.get("threshold", 2.0)))
        penalty = max(0.0, float(heat_cfg.get("penalty", 0.1)))
        if self._continuous_fire_time >= threshold:
            return 1.0 + penalty
        return 1.0


class WeaponFactory:
    """Gestiona los distintos tipos de armas disponibles."""

    def __init__(self) -> None:
        self._registry: Dict[str, WeaponSpec] = {
            "bloqueo": WeaponSpec(
                weapon_id="bloqueo",
                cooldown=0.25,  # Reducida de 0.125 (8 disparos/seg a 4 disparos/seg)
                spread_deg=10.0,
                bullet_speed=340.0,
            ),
            "reportar": WeaponSpec(
                weapon_id="reportar",
                cooldown=0.30,  # Reducida de 0.15
                spread_deg=16.0,
                bullet_speed=320.0,
                offsets=(-6.0, 6.0),
            ),
            "apoyo_amigo": WeaponSpec(
                weapon_id="apoyo_amigo",
                cooldown=0.28,  # Reducida de 0.14
                spread_deg=4.0,
                bullet_speed=360.0,
            ),
            "pausa_digital": WeaponSpec(
                weapon_id="pausa_digital",
                cooldown=0.70,  # Reducida de 0.35
                spread_deg=32.0,
                bullet_speed=280.0,
                offsets=(-12.0, -6.0, 0.0, 6.0, 12.0),
                projectile_radius=4,
            ),
            "autoestima": WeaponSpec(
                weapon_id="autoestima",
                cooldown=0.24,  # Reducida de 0.12
                spread_deg=2.5,
                bullet_speed=390.0,
                special={
                    "heat": {
                        "threshold": 2.0,
                        "penalty": 0.1,
                        "grace": 0.25,
                        "decay": 3.5,
                    }
                },
            ),
            "evidencia": WeaponSpec(
                weapon_id="evidencia",
                cooldown=0.36,  # Reducida de 0.18
                spread_deg=28.0,
                bullet_speed=240.0,
                projectile_radius=5,
                offsets=(-4.0, 4.0),
                forward_spawn=4.0,
                projectile_color=(140, 220, 255),
                on_hit_effects=(
                    {
                        "type": "shock",
                        "slow": 0.2,
                        "duration": 0.6,
                    },
                ),
            ),
            "modo_incognito": WeaponSpec(
                weapon_id="modo_incognito",
                cooldown=0.22,  # Reducida de 0.11
                spread_deg=8.0,
                bullet_speed=325.0,
                offsets=(0.0,),
                forward_spawn=9.0,
                special={
                    "recoil_ramp": {
                        "shots": 6,
                        "extra": 2.0,
                    }
                },
            ),
        }

    def __contains__(self, weapon_id: str) -> bool:
        return weapon_id in self._registry

    def create(self, weapon_id: str, *, cooldown_scale: float = 1.0) -> Weapon:
        spec = self._registry[weapon_id]
        return Weapon(spec, cooldown_scale=cooldown_scale)

    def ids(self) -> Iterable[str]:
        return self._registry.keys()
