# CODIGO/Enemy.py
import math
import random
import pygame
import logging
from pathlib import Path

from core.Entity import Entity
from Config import CFG
from core.Projectile import Projectile

log_enemy = logging.getLogger("ENEMY_FIRE")
from entities.enemy_sprites import (
    EnemyAnimator,
    load_enemy_animation_set,
    resolve_enemy_variant,
)

ENEMY_PROJECTILE_SPEED_SCALE = 4.0 / 5.0

IDLE, WANDER, CHASE = 0, 1, 2

# Contador global para generar IDs únicos de enemigos
_ENEMY_COUNTER = 0

def _generar_enemy_id() -> str:
    """Genera un ID único para cada enemigo instanciado."""
    global _ENEMY_COUNTER
    _ENEMY_COUNTER += 1
    return f"enemy_{_ENEMY_COUNTER:06d}"

class Enemy(Entity):
    """Base con FSM + LoS. Subclases cambian stats/comportamientos."""

    SPRITE_VARIANT = "default"
    DEATH_PARTICLE_COLOR = (255, 40, 40)  # Rojo brillante — paleta unificada para todas las muertes
    _death_effect_manager_global = None  # Asignado por Game al inicializar
    _debug_draw_hitboxes = False  # Flag para visualizar hitboxes en debug

    def __init__(self, x: float, y: float, hp: int = 3, gold_reward: int = 5) -> None:
        super().__init__(x, y, w=12, h=12, speed=40.0)
        self.hp = hp
        self.gold_reward = gold_reward

        # ID único para sincronización en multijugador
        self.enemy_id = _generar_enemy_id()

        # Estados y radios
        self.state = IDLE
        self.detect_radius = 110.0
        self.lose_radius = 130.0
        self._los_grace = 0.35  # “gracia” sin LoS antes de soltar persecución

        # Velocidades
        self.chase_speed = 70.0
        self.wander_speed = 50.0

        # Wander
        self.wander_time = 0.0
        self.wander_dir = (0.0, 0.0)

        # timers internos
        self._los_timer = 0.0
        self.reaction_delay = 0.35
        self.alert_timer = 0.0

        # Control de aturdimiento/knockback
        self.stun_timer = 0.0
        self._knockback_dir = (0.0, 0.0)
        self._knockback_speed = 0.0
        self.knockback_decay = 420.0

        # Daño por contacto (override en subclases que lo requieran)
        self.contact_damage = 0

        # Control de ralentizaciones
        self._slow_timer = 0.0
        self._slow_multiplier = 1.0

        # Animación
        if isinstance(self.SPRITE_VARIANT, (list, tuple)):
            preferred_variants = [str(v) for v in self.SPRITE_VARIANT if v]
        else:
            preferred_variants = [str(self.SPRITE_VARIANT)]
        self.sprite_variant = resolve_enemy_variant(preferred_variants)
        self.animations = load_enemy_animation_set(self.sprite_variant)
        self.animator = EnemyAnimator(
            self.animations,
            default_state="idle",
            fps_overrides={
                "idle": 5.0,
                "run": 10.0,
                "shoot": 8.0,
                "attack": 12.0,
                "death": 12.0,
            },
        )
        self._facing_right = True
        self._is_dying = False
        self._ready_to_remove = False
        self._movement_lock_timer = 0.0
        self._movement_locked = False
        self.hit_flash_timer = 0.0
        self._hit_flash_duration = 0.1
        
        # Sonidos
        self._damage_sound = None
        self._load_damage_sound()
        self._elimination_sound = None
        self._load_elimination_sound()
        self._attack_sound = None  # Será cargado por subclases que ataquen

    def _center(self):
        return (self.x + self.w/2, self.y + self.h/2)

    def move(self, dx: float, dy: float, dt: float, room) -> None:
        """Movimiento inteligente: intenta deslizarse en obstáculos."""
        step_x = dx * self.speed * dt
        step_y = dy * self.speed * dt

        # Intentar movimiento en X
        if step_x != 0:
            self.x += step_x
            if self._collides(room):
                self.x -= step_x
                # Si colisiona, no se mueve en X pero intenta Y
            else:
                # Chequear proximidad a obstáculos - si está muy cerca, detener movimiento en X
                dist, axis = self._get_proximity_distance_to_obstacles(room)
                if dist < self._proximity_threshold and axis == 'x':
                    self.x -= step_x

        # Intentar movimiento en Y
        if step_y != 0:
            self.y += step_y
            if self._collides(room):
                self.y -= step_y
                # Si colisiona, no se mueve en Y pero intenta X
            else:
                # Chequear proximidad a obstáculos - si está muy cerca, detener movimiento en Y
                dist, axis = self._get_proximity_distance_to_obstacles(room)
                if dist < self._proximity_threshold and axis == 'y':
                    self.y -= step_y

    # ---------- loop ----------
    def update(self, dt: float, player, room) -> None:
        if self._is_dying:
            # El efecto de muerte se spawnea inmediatamente en _begin_death()
            # El enemigo ya está marcado como _ready_to_remove
            return
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)
        self.alert_timer = max(0.0, self.alert_timer - dt)
        if self._slow_timer > 0.0:
            self._slow_timer = max(0.0, self._slow_timer - dt)
            if self._slow_timer <= 0.0:
                self._slow_multiplier = 1.0
        ex, ey = self._center()
        px, py = (player.x + player.w/2, player.y + player.h/2)

        dx, dy = (px - ex), (py - ey)
        dist   = math.hypot(dx, dy)
        has_los = room.has_line_of_sight(ex, ey, px, py)

        stunned = self.stun_timer > 0.0
        movement_locked = self._movement_lock_timer > 0.0
        if movement_locked:
            self._movement_lock_timer = max(0.0, self._movement_lock_timer - dt)

        prev_state = self.state

        # Cambios de estado (LoS + histéresis)
        if self.state != CHASE:
            if dist <= self.detect_radius and has_los:
                self.state = CHASE
                self._los_timer = self._los_grace
        else:
            if has_los:
                self._los_timer = self._los_grace
            else:
                self._los_timer = max(0.0, self._los_timer - dt)
            if dist >= self.lose_radius or self._los_timer <= 0.0:
                self._pick_wander()
                self.state = WANDER

        if prev_state != CHASE and self.state == CHASE:
            self.alert_timer = max(self.alert_timer, self.reaction_delay)

        if stunned:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            self._apply_knockback(dt, room)
            self._movement_locked = movement_locked
            self._update_animation(dt)
            return

        self.stun_timer = max(0.0, self.stun_timer - dt)
        self._apply_knockback(dt, room)

        if not movement_locked:
            # Ejecutar estado
            if self.state == IDLE:
                self._update_idle(dt)
            elif self.state == WANDER:
                self._update_wander(dt, room)
            elif self.state == CHASE:
                self._update_chase(dt, room, dx, dy)

        self._movement_locked = movement_locked
        self._update_animation(dt)

    def maybe_shoot(self, dt: float, player, room, out_bullets: list) -> bool:
        """Por defecto, los enemigos base NO disparan."""
        return False

    def is_stunned(self) -> bool:
        return self.stun_timer > 0.0

    def take_damage(
        self,
        amount: int,
        knockback_dir: tuple[float, float] | None = None,
        stun_duration: float = 0.22,
        knockback_strength: float = 150.0,
    ) -> bool:
        if self._is_dying:
            return False
        if amount > 0:
            hp_antes = self.hp
            self.hp -= amount
            # [DIAG] Log de daño recibido
            log_enemy.warning(f"[DAMAGE] {self.enemy_id} recibió {amount} daño en ({self.x:.0f},{self.y:.0f}). HP: {hp_antes} -> {self.hp}")
            self.hit_flash_timer = max(self.hit_flash_timer, self._hit_flash_duration)
            # Reproducir sonido de daño
            if self._damage_sound:
                self._damage_sound.play()
        alive = self.hp > 0
        if alive:
            if stun_duration > 0.0:
                self.stun_timer = max(self.stun_timer, stun_duration)
            if knockback_dir is not None and knockback_strength > 0.0:
                nx, ny = knockback_dir
                mag = math.hypot(nx, ny)
                if mag > 0.0:
                    self._knockback_dir = (nx / mag, ny / mag)
                    self._knockback_speed = max(self._knockback_speed, knockback_strength)
        else:
            # [DIAG] Mostrar el lugar donde take_damage() fue llamado
            import traceback
            stack = traceback.format_stack()
            caller_line = stack[-2].strip() if len(stack) > 1 else "UNKNOWN"
            log_enemy.warning(f"[DEATH_TRIGGER] {self.enemy_id} take_damage({amount}) hp={self.hp} desde: {caller_line}")
            log_enemy.warning(f"[DEATH] {self.enemy_id} muere en ({self.x:.0f},{self.y:.0f}). HP final: {self.hp}")
            self._begin_death()
        return self._is_dying

    def _apply_knockback(self, dt: float, room) -> None:
        if self._knockback_speed <= 0.0:
            return
        scale = self._knockback_speed / max(1e-6, self.speed)
        self.move(self._knockback_dir[0], self._knockback_dir[1], dt * scale, room)
        self._knockback_speed = max(0.0, self._knockback_speed - self.knockback_decay * dt)
        if self._knockback_speed <= 0.0:
            self._knockback_dir = (0.0, 0.0)

    def _begin_death(self) -> None:
        if self._is_dying:
            return
        self._is_dying = True
        self.hp = 0

        # [DIAG] Mostrar stack trace para ver por qué el enemigo muere
        import traceback
        stack = traceback.format_stack()
        caller = stack[-2] if len(stack) > 1 else "UNKNOWN"
        log_enemy.warning(f"[DEATH_TRACE] {self.enemy_id} _begin_death() llamado desde: {caller.strip()}")

        # Reproducir sonido de eliminación
        if self._elimination_sound:
            self._elimination_sound.play()

        # Spawnear efecto de muerte (reemplaza animación de muerte)
        if self._death_effect_manager_global:
            self._death_effect_manager_global.spawn(
                x=self.x,
                y=self.y,
                sprite_width=self.w,
                sprite_height=self.h,
                lifetime=0.5,
                num_particles=25,
                particle_color=self.DEATH_PARTICLE_COLOR
            )

        # Marcar como listo para remover (sin esperar animación de muerte)
        self._ready_to_remove = True

    def _movement_speed_factor(self) -> float:
        return self._slow_multiplier if self._slow_timer > 0.0 else 1.0

    def apply_slow(self, slow_fraction: float, duration: float) -> None:
        slow_fraction = max(0.0, min(0.95, slow_fraction))
        target_multiplier = max(0.05, 1.0 - slow_fraction)
        self._slow_multiplier = min(self._slow_multiplier, target_multiplier)
        self._slow_timer = max(self._slow_timer, max(0.0, duration))

    # ---------- estados ----------
    def _update_idle(self, dt: float) -> None:
        if random.random() < 0.005:
            self._pick_wander()
            self.state = WANDER

    def _pick_wander(self) -> None:
        ang = random.uniform(0, math.tau)
        self.wander_dir = (math.cos(ang), math.sin(ang))
        self.wander_time = random.uniform(0.6, 1.2)

    def _update_wander(self, dt: float, room) -> None:
        vx, vy = self.wander_dir
        speed_factor = self._movement_speed_factor()
        self._update_facing(vx)
        self.move(vx, vy, dt * (self.wander_speed / max(1e-6, self.speed)) * speed_factor, room)
        self.wander_time -= dt
        if self.wander_time <= 0.0 or random.random() < 0.01:
            if random.random() < 0.5:
                self.state = IDLE
            else:
                self._pick_wander()

    def _update_chase(self, dt: float, room, dx: float, dy: float) -> None:
        mag = math.hypot(dx, dy)
        if mag > 0:
            dx, dy = dx/mag, dy/mag
        speed_factor = self._movement_speed_factor()
        self._update_facing(dx)
        self.move(dx, dy, dt * (self.chase_speed / max(1e-6, self.speed)) * speed_factor, room)

    def draw(self, surf: pygame.Surface) -> None:
        frame = self.animator.current_surface()

        # [DIAGNOSTICO] Log para detectar frames None o inválidos
        from dev.logger import log_game
        anim_state = getattr(self.animator, "state", "?")
        oneshot_state = getattr(self.animator, "oneshot_state", None)
        if frame is None:
            log_game.warning(f"[DIAGNOSTICO] {self.enemy_id} current_surface() devolvió None! "
                           f"animator.state={anim_state} oneshot_state={oneshot_state}")
        elif frame.get_size() == (0, 0):
            log_game.warning(f"[DIAGNOSTICO] {self.enemy_id} frame con size ZERO "
                           f"animator.state={anim_state} oneshot_state={oneshot_state}")

        if not frame:
            return  # No dibujar si no hay frame válido

        if not self._facing_right:
            frame = pygame.transform.flip(frame, True, False)
        if self.hit_flash_timer > 0.0:
            frame = frame.copy()
            flash_overlay = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            flash_overlay.fill((255, 255, 255, 220))
            frame.blit(flash_overlay, (0, 0), special_flags=pygame.BLEND_ADD)

        dest = frame.get_rect(center=self.rect().center)
        surf.blit(frame, dest)

        if self._debug_draw_hitboxes:
            rect = self.rect()
            pygame.draw.rect(surf, (255, 0, 0), rect, 2)

    def _update_animation(self, dt: float) -> None:
        base_state = "idle"
        if not self._movement_locked and self.state in (WANDER, CHASE):
            base_state = "run"
        self.animator.set_base_state(base_state)
        self.animator.update(dt)

    def _update_facing(self, dx: float) -> None:
        if dx > 0.05:
            self._facing_right = True
        elif dx < -0.05:
            self._facing_right = False

    def trigger_shoot_animation(self, dir_x: float) -> None:
        self._update_facing(dir_x)
        self.animator.trigger_shoot()

    def trigger_attack_animation(self, dir_x: float = 0.0) -> None:
        """Gancho para enemigos cuerpo a cuerpo."""
        return

    def lock_movement(self, duration: float) -> None:
        if duration > 0.0:
            self._movement_lock_timer = max(self._movement_lock_timer, duration)

    def is_movement_locked(self) -> bool:
        return self._movement_lock_timer > 0.0

    def is_ready_to_remove(self) -> bool:
        if not self._is_dying:
            return False
        return self._ready_to_remove

    def is_dying(self) -> bool:
        return self._is_dying
    
    def _load_damage_sound(self) -> None:
        """Carga el sonido de daño del enemigo."""
        try:
            audio_path = Path("assets/audio/dmgenemy_sfx.mp3")
            if not audio_path.exists():
                audio_path = Path(__file__).parent / "assets" / "audio" / "dmgenemy_sfx.mp3"
            if audio_path.exists():
                self._damage_sound = pygame.mixer.Sound(audio_path.as_posix())
                self._damage_sound.set_volume(0.02)  # 2% del volumen
            else:
                self._damage_sound = None
        except (pygame.error, FileNotFoundError):
            self._damage_sound = None
    
    def _load_elimination_sound(self) -> None:
        """Carga el sonido de eliminación del enemigo."""
        try:
            audio_path = Path("assets/audio/enemy_elimination_sfx.mp3")
            if not audio_path.exists():
                audio_path = Path(__file__).parent / "assets" / "audio" / "enemy_elimination_sfx.mp3"
            if audio_path.exists():
                self._elimination_sound = pygame.mixer.Sound(audio_path.as_posix())
                self._elimination_sound.set_volume(0.15)  # 15% del volumen
            else:
                self._elimination_sound = None
        except (pygame.error, FileNotFoundError):
            self._elimination_sound = None
    
    def _load_attack_sound(self, filename: str) -> None:
        """Carga el sonido de ataque específico del enemigo."""
        try:
            audio_path = Path(f"assets/audio/{filename}")
            if not audio_path.exists():
                audio_path = Path(__file__).parent / "assets" / "audio" / filename
            if audio_path.exists():
                self._attack_sound = pygame.mixer.Sound(audio_path.as_posix())
                self._attack_sound.set_volume(0.25)  # 25% del volumen
            else:
                self._attack_sound = None
        except (pygame.error, FileNotFoundError):
            self._attack_sound = None


# ===== Tipos de enemigo =====

class FastChaserEnemy(Enemy):
    """Rápido, poca vida."""
    SPRITE_VARIANT = "green_chaser"
    DEATH_PARTICLE_COLOR = (255, 40, 40)  # Rojo brillante — unificado con otros enemigos
    def __init__(self, x, y):
        super().__init__(x, y, hp=2, gold_reward=7)
        self.chase_speed  = 100.0
        self.wander_speed = 80.0
        self.detect_radius = 100.0
        self.lose_radius   = 150.0
        self.reaction_delay = 0.0
        self.contact_damage = 1
        self.attack_range = 26.0
        self.attack_cooldown = 0.8
        self._attack_timer = 0.0

    def update(self, dt, player, room):
        self._attack_timer = max(0.0, self._attack_timer - dt)
        super().update(dt, player, room)
        if self.is_dying():
            return
        if self._attack_timer > 0.0:
            return
        ex = self.x + self.w/2
        ey = self.y + self.h/2
        px = player.x + player.w/2
        py = player.y + player.h/2
        dist = math.hypot(px - ex, py - ey)
        if dist <= self.attack_range:
            dir_x = px - ex
            self.trigger_attack_animation(dir_x)

    def trigger_attack_animation(self, dir_x: float = 0.0) -> None:
        if self.is_dying():
            return
        self._attack_timer = self.attack_cooldown
        self._update_facing(dir_x)
        self.animator.trigger_attack()

    def _update_animation(self, dt: float) -> None:
        """
        Actualiza la animación basada en el estado del enemigo.
        Prioridad: attack > run > idle
        """
        # Si está en cooldown de ataque, se está reproduciendo la animación de ataque
        if self._attack_timer > 0.0:
            base_state = "attack"
        # Si está en movimiento, usar animación "run" (walk)
        elif not self._movement_locked and self.state in (WANDER, CHASE):
            base_state = "run"
        # Por defecto, idle
        else:
            base_state = "idle"

        self.animator.set_base_state(base_state)
        self.animator.update(dt)


class ShooterEnemy(Enemy):
    """Dispara si te ve (LoS) y estás en rango."""
    SPRITE_VARIANT = ("blue_shooter", "yellow_shooter")
    def __init__(self, x, y):
        super().__init__(x, y, hp=3, gold_reward=9)
        self.chase_speed  = 5
        self.wander_speed = 5
        self.detect_radius = 220.0
        self.lose_radius   = 260.0

        self.fire_cooldown = 2.75
        self._fire_timer   = 0.0
        self.fire_range    = 260.0
        self.bullet_speed  = 160.0 * ENEMY_PROJECTILE_SPEED_SCALE
        self.reaction_delay = 0.55
        self._load_attack_sound("shooter_enemy_sfx.mp3")

        # Configurar FPS para yellow_shooter si es la variante actual
        if self.sprite_variant == "yellow_shooter":
            self.animator.fps_overrides.update({
                "idle": 10.0,
                "run": 10.0,
                "shoot": 12.0,
            })

    def update(self, dt, player, room):
        super().update(dt, player, room)
        self._fire_timer = max(0.0, self._fire_timer - dt)

    def maybe_shoot(self, dt, player, room, out_bullets: list) -> bool:
        if self.alert_timer > 0.0 or self.is_stunned() or self.is_dying():
            return False
        if self._fire_timer > 0.0:
            return False
        # Solo dispara si está en CHASE, hay LoS y dentro de rango
        ex, ey = self._center()
        px, py = (player.x + player.w/2, player.y + player.h/2)
        dx, dy = (px - ex), (py - ey)
        dist = math.hypot(dx, dy)
        if self.state != CHASE or dist > self.fire_range:
            return False
        if not room.has_line_of_sight(ex, ey, px, py):
            return False

        # [DIAG] El enemigo está disparando
        log_enemy.warning(f"[SHOOT] {self.enemy_id} disparando desde ({ex:.0f},{ey:.0f}) hacia jugador en ({px:.0f},{py:.0f}), dist={dist:.1f}, owner_id={self.enemy_id}")

        # Normaliza y dispara ráfagas en abanico
        if dist > 0:
            dx, dy = dx/dist, dy/dist
            self._update_facing(dx)

        base_angle = math.atan2(dy, dx)
        spread = math.radians(35)
        burst = 5
        center = (burst - 1) / 2.0
        for i in range(burst):
            offset = (i - center)
            angle = base_angle + (spread * offset / max(center, 1))
            dir_x = math.cos(angle)
            dir_y = math.sin(angle)
            spawn_x = ex + dir_x * 8
            spawn_y = ey + dir_y * 8
            bullet = Projectile(
                    spawn_x, spawn_y, dir_x, dir_y,
                    speed=self.bullet_speed,
                    radius=3,
                    color=(255, 90, 90),
                    damage=getattr(self, "projectile_damage", 1),
                    owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
                )
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)

        # Anillo radial lento para saturar la sala
        radial = 8
        radial_speed = self.bullet_speed * 0.55
        for j in range(radial):
            angle = base_angle + j * (math.tau / radial)
            dir_x = math.cos(angle)
            dir_y = math.sin(angle)
            spawn_x = ex + dir_x * 10
            spawn_y = ey + dir_y * 10
            bullet = Projectile(
                spawn_x, spawn_y, dir_x, dir_y,
                speed=radial_speed,
                radius=4,
                color=(200, 70, 180),
                damage=getattr(self, "projectile_damage", 1),
                owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
            )
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)
        self._fire_timer = self.fire_cooldown
        # Reproducir sonido de ataque
        if hasattr(self, '_attack_sound') and self._attack_sound:
            self._attack_sound.play()
        self.trigger_shoot_animation(dx)
        return True


class BasicEnemy(Enemy):
    """Enemigo común que dispara lentamente mientras avanza."""

    SPRITE_VARIANT = "yellow_shooter"
    DEATH_PARTICLE_COLOR = (255, 40, 40)  # Rojo brillante — unificado con otros enemigos

    def __init__(self, x, y):
        super().__init__(x, y, hp=3, gold_reward=5)

        # Ajustar hitbox para que coincida con el sprite de 64×64 (75% = 48×48)
        cx, cy = self.x + self.w / 2.0, self.y + self.h / 2.0
        self.w = 48
        self.h = 48
        self.x = cx - self.w / 2.0
        self.y = cy - self.h / 2.0

        self.fire_cooldown = 1.1
        self._fire_timer = 0.0
        self.fire_range = 210.0
        self.bullet_speed = 192.0 * ENEMY_PROJECTILE_SPEED_SCALE
        self.reaction_delay = 0.45
        self._load_attack_sound("basic_enemy_sfx.mp3")
        # Reducir volumen del BasicEnemy en 75%
        if self._attack_sound:
            self._attack_sound.set_volume(0.025)  # 25% del volumen base (0.10)

        # Configurar FPS para yellow_shooter
        self.animator.fps_overrides.update({
            "idle": 10.0,
            "run": 10.0,
            "shoot": 12.0,
        })

    def update(self, dt, player, room):
        super().update(dt, player, room)
        self._fire_timer = max(0.0, getattr(self, "_fire_timer", 0.0) - dt)

    def maybe_shoot(self, dt, player, room, out_bullets) -> bool:
        if self.alert_timer > 0.0 or self.is_stunned() or self.is_dying():
            return False
        if getattr(self, "_fire_timer", 0.0) > 0.0:
            return False

        ex, ey = self._center()
        px, py = (player.x + player.w/2, player.y + player.h/2)
        dx, dy = (px - ex), (py - ey)
        dist = math.hypot(dx, dy)
        if self.state != CHASE or dist > self.fire_range:
            return False
        if not room.has_line_of_sight(ex, ey, px, py):
            return False

        if dist > 0:
            dx, dy = dx/dist, dy/dist
            self._update_facing(dx)

        base_angle = math.atan2(dy, dx)
        offsets = (-0.18, 0.0, 0.18)
        for offset in offsets:
            angle = base_angle + offset
            dir_x = math.cos(angle)
            dir_y = math.sin(angle)
            spawn_x = ex + dir_x * 6
            spawn_y = ey + dir_y * 6
            bullet = Projectile(
                spawn_x, spawn_y, dir_x, dir_y,
                speed=self.bullet_speed,
                radius=3,
                color=(120, 230, 140),
                damage=getattr(self, "projectile_damage", 1),
                owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
            )
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)
        self._fire_timer = self.fire_cooldown
        # Reproducir sonido de ataque
        if hasattr(self, '_attack_sound') and self._attack_sound:
            self._attack_sound.play()
        self.trigger_shoot_animation(dx)
        return True


class TankEnemy(Enemy):
    """Lento, mucha vida y dispara ráfagas estilo escopeta."""

    SPRITE_VARIANT = ("tank", "blue_shooter")
    DEATH_PARTICLE_COLOR = (255, 40, 40)  # Rojo brillante — unificado con otros enemigos

    def __init__(self, x, y):
        super().__init__(x, y, hp=9, gold_reward=12)
        self.chase_speed  = 30.0
        self.wander_speed = 18.0
        self.detect_radius = 240.0
        self.lose_radius   = 260.0

        # Hitbox más grande y vertical para ajustar al nuevo sprite.
        cx, cy = self.x + self.w / 2.0, self.y + self.h / 2.0
        self.w = 18
        self.h = 30
        self.x = cx - self.w / 2.0
        self.y = cy - self.h / 2.0

        self.fire_cooldown = 3.1
        self._fire_timer = 0.0
        self.fire_range = 260.0
        self.bullet_speed = 152.0 * ENEMY_PROJECTILE_SPEED_SCALE
        self.pellets = 7
        self.spread_radians = math.radians(28)
        self.reaction_delay = 0.65
        self.shoot_windup = 0.6
        self.post_shoot_pause = 0.35
        self._windup_timer = 0.0
        self._pending_shot_dir: tuple[float, float] | None = None

        # El tanque alterna frames con más calma y deja ver mejor el disparo.
        self.animator.fps_overrides.update({
            "idle": 3.5,
            "run": 6.0,
            "shoot": 31.0,  # Animación de ataque: ~0.7 segundos
        })
        self._load_attack_sound("tank_enemy_sfx.mp3")
        # Aumentar volumen para TankEnemy
        if self._attack_sound:
            self._attack_sound.set_volume(0.20)  # 20% del volumen

    def take_damage(
        self,
        amount: int,
        knockback_dir: tuple[float, float] | None = None,
        stun_duration: float = 0.22,
        knockback_strength: float = 150.0,
    ) -> bool:
        if knockback_strength > 0.0:
            knockback_strength *= 0.45
        return super().take_damage(
            amount,
            knockback_dir,
            stun_duration=stun_duration,
            knockback_strength=knockback_strength,
        )

    def update(self, dt, player, room):
        super().update(dt, player, room)
        self._fire_timer = max(0.0, getattr(self, "_fire_timer", 0.0) - dt)

    def maybe_shoot(self, dt, player, room, out_bullets) -> bool:
        if self.is_dying():
            self._cancel_windup()
            return False

        if self.is_stunned():
            self._cancel_windup()
            return False

        ex, ey = self._center()
        px, py = (player.x + player.w / 2, player.y + player.h / 2)
        dx, dy = (px - ex), (py - ey)
        dist = math.hypot(dx, dy)

        if self._windup_timer > 0.0:
            self._windup_timer = max(0.0, self._windup_timer - dt)
            if (
                self.state != CHASE
                or dist > self.fire_range
                or not room.has_line_of_sight(ex, ey, px, py)
            ):
                self._cancel_windup()
                return False
            if self._windup_timer > 0.0:
                return False
            return self._complete_windup(out_bullets)

        if self.alert_timer > 0.0:
            return False
        if getattr(self, "_fire_timer", 0.0) > 0.0:
            return False
        if self.state != CHASE or dist > self.fire_range:
            return False
        if not room.has_line_of_sight(ex, ey, px, py):
            return False
        if dist <= 0.0:
            return False

        dir_x, dir_y = dx / dist, dy / dist
        self._update_facing(dir_x)
        self._pending_shot_dir = (dir_x, dir_y)
        self._windup_timer = self.shoot_windup
        self.lock_movement(self.shoot_windup)
        return False

    def _cancel_windup(self) -> None:
        self._windup_timer = 0.0
        self._pending_shot_dir = None
        if self._movement_lock_timer > 0.0:
            self._movement_lock_timer = 0.0

    def _complete_windup(self, out_bullets) -> bool:
        if not self._pending_shot_dir:
            return False
        dir_x, dir_y = self._pending_shot_dir
        self._pending_shot_dir = None
        ex, ey = self._center()
        self._update_facing(dir_x)
        fired_any = self._emit_barrage(ex, ey, dir_x, dir_y, out_bullets)
        self._fire_timer = self.fire_cooldown
        # Reproducir sonido de ataque
        if hasattr(self, '_attack_sound') and self._attack_sound:
            self._attack_sound.play()
        self.trigger_shoot_animation(dir_x)
        self.lock_movement(self.post_shoot_pause)
        return fired_any

    def _emit_barrage(
        self,
        ex: float,
        ey: float,
        dir_x: float,
        dir_y: float,
        out_bullets,
    ) -> bool:
        base_angle = math.atan2(dir_y, dir_x)
        half = (self.pellets - 1) / 2.0
        spread_step = self.spread_radians / half if half > 0 else 0.0
        fired_any = False

        for i in range(self.pellets):
            offset = (i - half)
            angle = base_angle + offset * spread_step
            vx = math.cos(angle)
            vy = math.sin(angle)
            spawn_x = ex + vx * 8
            spawn_y = ey + vy * 8
            bullet = Projectile(
                spawn_x,
                spawn_y,
                vx,
                vy,
                speed=self.bullet_speed,
                radius=4,
                color=(255, 120, 90),
                damage=getattr(self, "projectile_damage", 1),
                owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
            )
            fired_any = True
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)

        if fired_any:
            ortho_angle = base_angle + math.pi / 2.0
            ortho_dirs = (
                (math.cos(ortho_angle), math.sin(ortho_angle)),
                (math.cos(ortho_angle + math.pi), math.sin(ortho_angle + math.pi)),
            )
            for vx, vy in ortho_dirs:
                spawn_x = ex + vx * 8
                spawn_y = ey + vy * 8
                bullet = Projectile(
                    spawn_x,
                    spawn_y,
                    vx,
                    vy,
                    speed=self.bullet_speed * 0.9,
                    radius=4,
                    color=(255, 160, 120),
                    damage=getattr(self, "projectile_damage", 1),
                    owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
                )
                if hasattr(out_bullets, "add"):
                    out_bullets.add(bullet)
                else:
                    out_bullets.append(bullet)

        return fired_any

    def draw(self, surf: pygame.Surface) -> None:
        """
        Renderiza el tank con sus frames de 96x96 píxeles sin escalado.
        """
        frame = self.animator.current_surface()

        # Aplicar flip según dirección
        if not self._facing_right:
            frame = pygame.transform.flip(frame, True, False)

        # Flash de daño
        if self.hit_flash_timer > 0.0:
            frame = frame.copy()
            flash_overlay = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            flash_overlay.fill((255, 255, 255, 220))
            frame.blit(flash_overlay, (0, 0), special_flags=pygame.BLEND_ADD)

        # Renderizar en posición correcta (sin escalado)
        dest = frame.get_rect(center=self.rect().center)
        surf.blit(frame, dest)


class FakerEnemy(Enemy):
    """Faker - Melee rápido y letal. Mayor velocidad, menos vida, ataques más rápidos."""
    SPRITE_VARIANT = "faker"
    DEATH_PARTICLE_COLOR = (255, 40, 40)
    def __init__(self, x, y):
        super().__init__(x, y, hp=4, gold_reward=7)

        cx, cy = self.x + self.w / 2.0, self.y + self.h / 2.0
        self.w = 64
        self.h = 64
        self.x = cx - self.w / 2.0
        self.y = cy - self.h / 2.0

        self.chase_speed  = 130.0
        self.wander_speed = 105.0
        self.detect_radius = 100.0
        self.lose_radius   = 150.0
        self.reaction_delay = 0.0
        self.contact_damage = 1
        self.attack_range = 26.0
        self.attack_cooldown = 2.0
        self._attack_timer = 0.0
        self.attack_duration = 0.5
        self._attack_fired = False

        # Ralentizar animación de ataque
        self.animator.fps_overrides["attack"] = 8.0

    def update(self, dt, player, room):
        self._attack_timer = max(0.0, self._attack_timer - dt)
        super().update(dt, player, room)
        if self.is_dying():
            return

        ex = self.x + self.w/2
        ey = self.y + self.h/2
        px = player.x + player.w/2
        py = player.y + player.h/2
        dist = math.hypot(px - ex, py - ey)

        # Si está en rango de ataque, se queda quieto
        if dist <= self.attack_range:
            self.lock_movement(0.1)  # Lock continuo cada frame
            if self._attack_timer <= 0.0 and not self._attack_fired:
                dir_x = px - ex
                self.trigger_attack_animation(dir_x)
                self._attack_fired = True
        else:
            self._attack_fired = False

    def trigger_attack_animation(self, dir_x: float = 0.0) -> None:
        if self.is_dying():
            return
        self._attack_timer = self.attack_cooldown
        self._update_facing(dir_x)
        self.animator.trigger_attack()
        self.lock_movement(self.attack_duration)

    def _update_animation(self, dt: float) -> None:
        if self._attack_timer > 0.0:
            base_state = "attack"
        elif not self._movement_locked and self.state in (WANDER, CHASE):
            base_state = "run"
        else:
            base_state = "idle"

        self.animator.set_base_state(base_state)
        self.animator.update(dt)


class TelefonoEnemy(Enemy):
    """Teléfono - Dispara rápido y muy ágil. Velocidad aumentada y cadencia de fuego acelerada."""
    SPRITE_VARIANT = "telefono"
    def __init__(self, x, y):
        super().__init__(x, y, hp=3, gold_reward=9)

        cx, cy = self.x + self.w / 2.0, self.y + self.h / 2.0
        self.w = 64
        self.h = 64
        self.x = cx - self.w / 2.0
        self.y = cy - self.h / 2.0

        self.chase_speed  = 35.0
        self.wander_speed = 25.0
        self.detect_radius = 220.0
        self.lose_radius   = 260.0

        self.fire_cooldown = 1.8
        self._fire_timer   = 0.0
        self.fire_range    = 260.0
        self.bullet_speed  = 160.0 * ENEMY_PROJECTILE_SPEED_SCALE
        self.reaction_delay = 0.35
        self._load_attack_sound("shooter_enemy_sfx.mp3")
        if self._attack_sound:
            self._attack_sound.set_volume(0.1)

        self.animator.fps_overrides.update({
            "idle": 10.0,
            "run": 10.0,
            "shoot": 12.0,
        })

    def update(self, dt, player, room):
        super().update(dt, player, room)
        self._fire_timer = max(0.0, self._fire_timer - dt)

    def maybe_shoot(self, dt, player, room, out_bullets: list) -> bool:
        if self.alert_timer > 0.0 or self.is_stunned() or self.is_dying():
            return False
        if self._fire_timer > 0.0:
            return False
        ex, ey = self._center()
        px, py = (player.x + player.w/2, player.y + player.h/2)
        dx, dy = (px - ex), (py - ey)
        dist = math.hypot(dx, dy)
        if self.state != CHASE or dist > self.fire_range:
            return False
        if not room.has_line_of_sight(ex, ey, px, py):
            return False

        if dist > 0:
            dx, dy = dx/dist, dy/dist
            self._update_facing(dx)

        base_angle = math.atan2(dy, dx)
        spread = math.radians(35)
        burst = 5
        center = (burst - 1) / 2.0
        for i in range(burst):
            offset = (i - center)
            angle = base_angle + (spread * offset / max(center, 1))
            dir_x = math.cos(angle)
            dir_y = math.sin(angle)
            spawn_x = ex + dir_x * 8
            spawn_y = ey + dir_y * 8
            bullet = Projectile(
                    spawn_x, spawn_y, dir_x, dir_y,
                    speed=self.bullet_speed,
                    radius=3,
                    color=(255, 90, 90),
                    damage=getattr(self, "projectile_damage", 1),
                    owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
                )
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)

        radial = 8
        radial_speed = self.bullet_speed * 0.55
        for j in range(radial):
            angle = base_angle + j * (math.tau / radial)
            dir_x = math.cos(angle)
            dir_y = math.sin(angle)
            spawn_x = ex + dir_x * 10
            spawn_y = ey + dir_y * 10
            bullet = Projectile(
                spawn_x, spawn_y, dir_x, dir_y,
                speed=radial_speed,
                radius=4,
                color=(200, 70, 180),
                damage=getattr(self, "projectile_damage", 1),
                owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
            )
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)
        self._fire_timer = self.fire_cooldown
        if hasattr(self, '_attack_sound') and self._attack_sound:
            self._attack_sound.play()
        self.trigger_shoot_animation(dx)
        return True


class EmojiEnemy(Enemy):
    """Emoji - Dispara en ráfaga de 4 proyectiles rápidos uno tras otro."""

    SPRITE_VARIANT = "emoji"
    DEATH_PARTICLE_COLOR = (255, 40, 40)

    def __init__(self, x, y):
        super().__init__(x, y, hp=3, gold_reward=5)

        cx, cy = self.x + self.w / 2.0, self.y + self.h / 2.0
        self.w = 64
        self.h = 64
        self.x = cx - self.w / 2.0
        self.y = cy - self.h / 2.0

        self.chase_speed = 25.0
        self.wander_speed = 20.0
        self.fire_cooldown = 2.0
        self._fire_timer = 0.0
        self.fire_range = 210.0
        self.bullet_speed = 192.0 * ENEMY_PROJECTILE_SPEED_SCALE
        self.reaction_delay = 0.45
        self._load_attack_sound("basic_enemy_sfx.mp3")
        if self._attack_sound:
            self._attack_sound.set_volume(0.025)

        self.animator.fps_overrides.update({
            "idle": 10.0,
            "run": 10.0,
            "shoot": 12.0,
        })

        # Sistema de ráfaga
        self._burst_count = 0
        self._burst_total = 4
        self._burst_interval = 0.15
        self._burst_timer = 0.0

    def update(self, dt, player, room):
        super().update(dt, player, room)
        self._fire_timer = max(0.0, getattr(self, "_fire_timer", 0.0) - dt)

        # Actualizar timer de ráfaga si está en progreso
        if self._burst_count > 0 and self._burst_count < self._burst_total:
            self._burst_timer = max(0.0, self._burst_timer - dt)

    def maybe_shoot(self, dt, player, room, out_bullets) -> bool:
        if self.alert_timer > 0.0 or self.is_stunned() or self.is_dying():
            return False
        if getattr(self, "_fire_timer", 0.0) > 0.0:
            return False

        ex, ey = self._center()
        px, py = (player.x + player.w/2, player.y + player.h/2)
        dx, dy = (px - ex), (py - ey)
        dist = math.hypot(dx, dy)
        if self.state != CHASE or dist > self.fire_range:
            return False
        if not room.has_line_of_sight(ex, ey, px, py):
            return False

        if dist > 0:
            dx, dy = dx/dist, dy/dist
            self._update_facing(dx)

        # Si no estamos en ráfaga, iniciarla
        if self._burst_count == 0:
            self._burst_count = 1
            self._burst_timer = self._burst_interval
        # Si estamos en ráfaga pero el timer no ha llegado, no disparar
        elif self._burst_count < self._burst_total and self._burst_timer > 0:
            return False
        # Si es hora del siguiente disparo en la ráfaga
        elif self._burst_count < self._burst_total:
            self._burst_count += 1
            self._burst_timer = self._burst_interval
        else:
            # Ráfaga terminada, reiniciar
            self._burst_count = 0
            self._fire_timer = self.fire_cooldown
            return False

        base_angle = math.atan2(dy, dx)
        offsets = (-0.18, 0.0, 0.18)
        for offset in offsets:
            angle = base_angle + offset
            dir_x = math.cos(angle)
            dir_y = math.sin(angle)
            spawn_x = ex + dir_x * 6
            spawn_y = ey + dir_y * 6
            bullet = Projectile(
                spawn_x, spawn_y, dir_x, dir_y,
                speed=self.bullet_speed,
                radius=3,
                color=(120, 230, 140),
                damage=getattr(self, "projectile_damage", 1),
                owner_id=self.enemy_id,  # [FIX] Prevenir que el enemigo se dañe a sí mismo
            )
            if hasattr(out_bullets, "add"):
                out_bullets.add(bullet)
            else:
                out_bullets.append(bullet)

        if hasattr(self, '_attack_sound') and self._attack_sound:
            self._attack_sound.play()
        self.trigger_shoot_animation(dx)
        return True
