import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pygame

from core.Entity import Entity
from Config import CFG
from core.Projectile import Projectile
from entities.Weapons import WeaponFactory
from systems.animation import Animation, AnimationManager
from systems.death_effect import DeathParticle


PLAYER_SPRITE_SIZE = (64, 64)
PLAYER_HITBOX_SIZE = (18, 24)
PLAYER_HITBOX_OFFSET = (23, 40)
PLAYER_SPRITE_CENTER_OFFSET_Y = (
    PLAYER_HITBOX_OFFSET[1] + PLAYER_HITBOX_SIZE[1] // 2 - PLAYER_SPRITE_SIZE[1] // 2
)


@dataclass
class DashTrailSegment:
    pos: tuple[float, float]
    life: float


class Player(Entity):
    HITBOX_SIZE = PLAYER_HITBOX_SIZE

    def __init__(self, x: float, y: float, *, sprite_dir: str | Path | None = None) -> None:
        super().__init__(x, y, w=PLAYER_HITBOX_SIZE[0], h=PLAYER_HITBOX_SIZE[1], speed=120.0)
        self.gold = 0
        self.empathy_fragments = 0  # Contador de fragmentos de empatía para final alternativo
        self.cooldown_scale = 1.0
        self._weapon_factory = WeaponFactory()
        self._owned_weapons: set[str] = set()
        self.weapon_id: str | None = None
        self.weapon = None
        self.cooldown_scale_base = 1.0
        self._cooldown_modifiers: dict[str, float] = {}
        self._upgrade_flags: set[str] = set()
        self.key_items: set[str] = set()
        self.sprint_control_bonus = 0.0
        self._sprint_control_timer = 0.0
        self._is_sprinting = False
        self.phase_during_dash = False
        self.dash_core_bonus_window = 0.0
        self.dash_core_bonus_iframe = 0.0
        self._recent_enemy_shot_timer = 0.0
        self._was_dashing = False
        self.on_shoot: Callable[[tuple[float, float], tuple[float, float]], None] | None = None

        # --- Atributos de supervivencia y movilidad ---
        self.base_speed = self.speed
        self.base_max_hp = 1  # 1 golpe = 1 vida perdida
        self.max_hp = self.base_max_hp
        self.hp = self.max_hp
        self.base_max_lives = CFG.PLAYER_START_LIVES
        self.max_lives = self.base_max_lives
        self.lives = self.max_lives
        self.life_charge_buffer = 0
        self.invulnerable_timer = 0.0
        self.post_hit_invulnerability = 0.45
        self.respawn_invulnerability = 2.0
        # Conteo de golpes por vida (cada golpe equivale a 1 punto de vida perdido)
        self._hits_taken_current_life = 0
        self._respawn_animating = False
        # Track previous lives to detect when a complete corazón is lost
        self._previous_lives = self.lives

        # --- Sistema de revival (animación de respawn) ---
        self.reviviendo = False
        self.revival_timer = 0.0
        self.revival_frame = 0
        self.revival_frame_timer = 0.0
        self.revival_fps = 10  # frames por segundo
        self.revival_duracion = 7 / 10  # 7 frames a 10fps = 0.7 segundos
        self.frames_revival = []  # Se carga al inicializar animaciones
        self.revival_particle_effect = None  # Efecto de partículas blancas durante revival

        # --- Sistema de flash blanco cuando recibe daño ---
        self.hit_flash_timer = 0.0
        self._hit_flash_duration = 0.1  # 100ms de flash blanco

        self.sprint_multiplier = 1.35
        self.base_sprint_multiplier = self.sprint_multiplier

        self.dash_speed_multiplier = 3.25
        self.dash_duration = 0.18
        self.base_dash_duration = self.dash_duration
        self.dash_cooldown = 0.75
        self.base_dash_cooldown = self.dash_cooldown
        self.dash_iframe_duration = self.dash_duration + 0.08

        # Threshold para diferenciar caminar vs correr en animaciones
        # input_mag > run_threshold = "run", 0 < input_mag <= run_threshold = "walk"
        self.run_threshold = 80.0

        self._dash_timer = 0.0
        self._dash_cooldown_timer = 0.0
        self._dash_key_down = False
        self._dash_dir = (0.0, -1.0)
        self._last_move_dir = (0.0, -1.0)

        # --- Velocidad heredada para balas (momentum) ---
        self.vel_x = 0.0  # Velocidad actual X
        self.vel_y = 0.0  # Velocidad actual Y

        # Rastro visual del dash
        self.dash_trail_lifetime = 0.22
        self.dash_trail_interval = 0.02
        self.dash_trail_size = max(8, int(self.w * 0.75))
        self.dash_trail_vertical_offset = 14
        self._dash_trail_timer = 0.0
        self._dash_trail: list[DashTrailSegment] = []

        self.controls_enabled = True

        self.sprite_dir: Path | None = self._resolve_sprite_dir(sprite_dir)
        self._animations: dict[str, Animation] = {}
        self._current_animation = "idle"
        self._animation_override: str | None = None
        self._facing = "right"  # "left" o "right" (preparado para futuros up/down)

        # Cargar animaciones
        try:
            self._animations = self._build_animations()
        except Exception as e:
            # Si falla, crear animaciones vacías para no crashear
            print(f"[WARNING] No se pudieron cargar animaciones: {e}")
            self._animations = self._create_empty_animations()

        # Cargar frames de revival desde la animación death_spawn
        self._cargar_frames_revival()

        # --- Sistema de disparo twin-stick (IJKL) ---
        self._shoot_keys = {
            pygame.K_i: (0, -1),    # arriba
            pygame.K_k: (0, 1),     # abajo
            pygame.K_j: (-1, 0),    # izquierda
            pygame.K_l: (1, 0),     # derecha
        }
        self._last_shoot_key: int | None = None
        self._shoot_dir_current: tuple[int, int] = (0, 0)

        # Sonido de caminata
        self.run_sound = None
        self._is_run_sound_playing = False
        self._load_run_sound()
        
        # Sonido de dash
        self.dash_sound = None
        self._load_dash_sound()
        
        # Sonido de respawn
        self.respawn_sound = None
        self._load_respawn_sound()
        
        # Sonido de daño
        self.damage_sound = None
        self._load_damage_sound()

        self.reset_loadout()

    def update(self, dt: float, room, out_projectiles=None) -> None:
        # Si está reviviendo, solo actualizar la animación de revival
        # NO procesar input de movimiento ni disparo
        if self.reviviendo:
            self.update_revival(dt)
            self.invulnerable_timer = max(0.0, self.invulnerable_timer - dt)
            return

        keys = pygame.key.get_pressed() if self.controls_enabled else None
        self.invulnerable_timer = max(0.0, self.invulnerable_timer - dt)
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)
        self._dash_timer = max(0.0, self._dash_timer - dt)
        self._dash_cooldown_timer = max(0.0, self._dash_cooldown_timer - dt)
        self._recent_enemy_shot_timer = max(0.0, self._recent_enemy_shot_timer - dt)
        self._sprint_control_timer = max(0.0, self._sprint_control_timer - dt)

        if self.controls_enabled and keys:
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        else:
            dx = dy = 0
        input_mag = math.hypot(dx, dy)
        if input_mag > 0:
            dx, dy = dx / input_mag, dy / input_mag
            self._last_move_dir = (dx, dy)

        dash_pressed = keys[pygame.K_SPACE] if self.controls_enabled and keys else False
        dash_just_pressed = dash_pressed and not self._dash_key_down
        self._dash_key_down = dash_pressed

        move_dx, move_dy = dx, dy
        speed_scale = 1.0

        dash_active = self.controls_enabled and self._dash_timer > 0.0
        sprinting_now = False
        if dash_active:
            move_dx, move_dy = self._dash_dir
            speed_scale = self.dash_speed_multiplier
        else:
            if dash_just_pressed and self._dash_cooldown_timer <= 0.0:
                dash_dir = (dx, dy) if input_mag > 0 else self._last_move_dir
                dash_mag = math.hypot(*dash_dir)
                if dash_mag > 0:
                    dash_dir = (dash_dir[0] / dash_mag, dash_dir[1] / dash_mag)
                    self._dash_dir = dash_dir
                    self._dash_timer = self.dash_duration
                    move_dx, move_dy = dash_dir
                    speed_scale = self.dash_speed_multiplier
                    self._dash_cooldown_timer = self.dash_cooldown
                    self.invulnerable_timer = max(self.invulnerable_timer, self.dash_iframe_duration)
                    dash_active = True
                    # Reproducir sonido de dash
                    if self.dash_sound:
                        self.dash_sound.play()
            if not dash_active and input_mag > 0:
                if self.controls_enabled and keys and (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]):
                    speed_scale = self.sprint_multiplier
                    sprinting_now = True

        if sprinting_now and not self._is_sprinting:
            self._sprint_control_timer = max(self._sprint_control_timer, 1.0)

        if sprinting_now and self.sprint_control_bonus > 0.0 and self._sprint_control_timer > 0.0:
            speed_scale *= 1.0 + self.sprint_control_bonus

        self._update_facing(move_dx, dash_active)

        if move_dx != 0 or move_dy != 0:
            mag = math.hypot(move_dx, move_dy)
            if mag > 0:
                move_dx /= mag
                move_dy /= mag

        # Calcular velocidad heredada para balas (antes de mover)
        # Esta es la velocidad que heredarán los proyectiles disparados
        self.vel_x = move_dx * speed_scale * self.base_speed
        self.vel_y = move_dy * speed_scale * self.base_speed

        self.move(move_dx * speed_scale, move_dy * speed_scale, dt, room)

        self._update_dash_trail(dt, dash_active)

        if self.weapon:
            self.weapon.tick(dt)

        moving = dash_active or input_mag > 0
        # Solo reproducir sonido de run cuando NO está haciendo dash
        moving_no_dash = input_mag > 0 and not dash_active
        self._update_run_sound(moving_no_dash)
        self._update_animation(dt, moving)
        if self._was_dashing and not dash_active and self.dash_core_bonus_iframe > 0.0:
            if self._recent_enemy_shot_timer > 0.0:
                self.invulnerable_timer = max(0.0, self.invulnerable_timer) + self.dash_core_bonus_iframe

        # --- Detectar y procesar disparo (teclas IJKL) ---
        if self.controls_enabled and keys:
            # Actualizar dirección de disparo actual basado en última tecla presionada
            for key, direction in self._shoot_keys.items():
                if keys[key]:
                    self._last_shoot_key = key
                    self._shoot_dir_current = direction
                    break  # Priorizar la primera encontrada (última presionada registrada)

            # Si ninguna tecla de disparo está presionada
            if all(not keys[k] for k in self._shoot_keys):
                self._last_shoot_key = None
                self._shoot_dir_current = (0, 0)
        else:
            self._last_shoot_key = None
            self._shoot_dir_current = (0, 0)

        # Disparar cada frame si hay dirección activa
        if out_projectiles is not None:
            self.try_shoot(out_projectiles)

        self._was_dashing = dash_active
        self._is_sprinting = sprinting_now

    def set_controls_enabled(self, enabled: bool) -> None:
        self.controls_enabled = bool(enabled)
        if not enabled:
            self._dash_key_down = False
            self._last_shoot_key = None
            self._shoot_dir_current = (0, 0)

    # ------------------------------------------------------------------
    # Estado defensivo
    # ------------------------------------------------------------------
    def is_invulnerable(self) -> bool:
        return self.invulnerable_timer > 0.0

    def is_phase_active(self) -> bool:
        return self.phase_during_dash and self._dash_timer > 0.0

    def take_damage(self, amount: int) -> bool:
        """Aplica daño al jugador si no está en iframes. Devuelve True si impactó."""
        # Invulnerable durante revival — ignorar todo daño
        if self.reviviendo:
            return False

        if amount <= 0 or self.is_invulnerable():
            return False
        prev_hp = self.hp
        self.hp = max(0, self.hp - amount)
        self.invulnerable_timer = max(self.invulnerable_timer, self.post_hit_invulnerability)
        # Activar flash blanco al recibir daño
        self.hit_flash_timer = max(self.hit_flash_timer, self._hit_flash_duration)
        if prev_hp != self.hp:
            self._hits_taken_current_life = self.max_hp - self.hp
            # Reproducir sonido de daño
            if self.damage_sound:
                self.damage_sound.play()
        return True

    def lose_life(self) -> bool:
        """Consume una vida. Devuelve True si aún quedan vidas disponibles."""
        if self.lives <= 0:
            return False
        self._previous_lives = self.lives  # Track before decrement
        self.lives -= 1
        return self.lives > 0

    def should_respawn(self) -> bool:
        """
        Determina si se debe hacer respawn (resurrección con animación).
        Solo devuelve True cuando se pierde un CORAZÓN COMPLETO (cada 2 vidas).

        Sistema:
        - 6→5: No respawn (vida perdida, corazón 3 a medio)
        - 5→4: SI respawn (corazón 3 a vacío - corazón 3 perdido)
        - 4→3: No respawn (vida perdida, corazón 2 a medio)
        - 3→2: SI respawn (corazón 2 a vacío - corazón 2 perdido)
        - 2→1: No respawn (vida perdida, corazón 1 a medio)
        - 1→0: SI respawn (corazón 1 a vacío - corazón 1 perdido)
        """
        # Respawn happens when we cross to an even number of lives
        # (transitioning from odd -> even means a complete heart was lost)
        return self._previous_lives % 2 == 1 and self.lives % 2 == 0

    def reset_lives(self) -> None:
        self.lives = self.max_lives
        self.life_charge_buffer = 0

    def hits_taken_this_life(self) -> int:
        """Golpes recibidos en la vida actual (se resetea al revivir)."""
        return self._hits_taken_current_life

    def hits_remaining_this_life(self) -> int:
        """Golpes que aún se pueden resistir antes de perder la vida actual."""
        return max(0, self.max_hp - self._hits_taken_current_life)

    def respawn(self) -> None:
        """Restaura la salud y otorga invulnerabilidad breve tras revivir."""
        self.hp = self.max_hp
        self._hits_taken_current_life = 0
        self.invulnerable_timer = max(self.invulnerable_timer, self.respawn_invulnerability)
        self._dash_timer = 0.0
        self._dash_cooldown_timer = 0.0
        self._dash_key_down = False
        self._dash_dir = (0.0, -1.0)
        self._last_move_dir = (0.0, -1.0)
        self._dash_trail.clear()
        self._dash_trail_timer = 0.0
        self._start_respawn_animation()

    def _start_respawn_animation(self) -> None:
        """Inicia la animación de muerte/respawn (ahora llamada 'death')."""
        # Evitar iniciar la animación múltiples veces
        if self._respawn_animating:
            return

        self._respawn_animating = True
        # Iniciar el nuevo sistema de revival
        self._iniciar_revival()
        # Reproducir sonido de respawn
        if self.respawn_sound:
            self.respawn_sound.play()

    def _iniciar_revival(self) -> None:
        """
        Inicia el estado de revivir.
        Activa la animación de revival, invulnerabilidad y partículas blancas.
        """
        self.reviviendo = True
        self.revival_timer = 0.0
        self.revival_frame = 0
        self.revival_frame_timer = 0.0
        self.invulnerable_timer = self.respawn_invulnerability

        # Crear efecto de partículas blancas
        self._create_revival_particles()

    def _create_revival_particles(self) -> None:
        """Crea el efecto de partículas blancas durante el revival."""
        center_x = self.x + self.w / 2
        center_y = self.y + self.h / 2

        # Lista de colores blancos con variaciones
        white_palette = [
            (255, 255, 255),  # Blanco puro
            (220, 220, 220),  # Blanco con gris claro
            (240, 240, 240),  # Blanco muy claro
        ]

        # Crear partículas blancas
        self.revival_particle_effect = []
        num_particles = 25

        for _ in range(num_particles):
            # Dirección aleatoria (radiante)
            angle = random.uniform(0, math.tau)
            speed = random.uniform(100.0, 250.0)  # velocidad de las partículas

            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed

            # Offset ligeramente aleatorio desde el centro
            offset_x = random.uniform(-self.w / 4, self.w / 4)
            offset_y = random.uniform(-self.h / 4, self.h / 4)

            # Color blanco aleatorio de la paleta
            particle_color = random.choice(white_palette)

            particle = DeathParticle(
                center_x + offset_x,
                center_y + offset_y,
                vx,
                vy,
                lifetime=0.7,  # duracion de las partículas
                size=random.randint(2, 4),
                color=particle_color
            )
            self.revival_particle_effect.append(particle)

    def update_revival(self, dt: float) -> None:
        """
        Actualiza el estado de revivir.
        Llamar desde el update principal SOLO cuando self.reviviendo == True.
        """
        if not self.reviviendo:
            return

        # Decrementar hit flash timer (también durante revival)
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

        # Actualizar partículas blancas
        if self.revival_particle_effect:
            for particle in self.revival_particle_effect:
                if particle.is_alive():
                    particle.update(dt)

        # Avanzar frame de animación
        self.revival_frame_timer += dt
        intervalo = 1.0 / self.revival_fps

        if self.revival_frame_timer >= intervalo:
            self.revival_frame_timer -= intervalo
            self.revival_frame += 1

            # Verificar si terminó la animación
            if self.revival_frame >= len(self.frames_revival):
                self._terminar_revival()

    def _terminar_revival(self) -> None:
        """
        Llama cuando termina la animación de revivir.
        Restaura el control al jugador.
        """
        self.reviviendo = False
        self.revival_frame = 0

        # Limpiar partículas
        self.revival_particle_effect = None

        # Restaurar animación a idle
        self._set_current_animation("idle")
        self._respawn_animating = False

    def try_shoot(self, out_projectiles) -> None:
        """Dispara proyectiles en la dirección cardinal actual (IJKL) si el cooldown lo permite."""
        if not self.weapon or not self.weapon.can_fire():
            return
        if self._shoot_dir_current == (0, 0):
            return

        # Origen: centro del jugador
        cx = self.x + self.w / 2
        cy = self.y + self.h / 2

        # Disparar con dirección cardinal, heredando momentum del movimiento actual
        created = self.weapon.fire((cx, cy), self._shoot_dir_current,
                                   player_vel_x=self.vel_x, player_vel_y=self.vel_y)
        if not created:
            return

        # Eco de Señal: dos balas desviadas ±2 grados cada una desde la línea recta
        if getattr(self, "_ibarra_double_shot", False):
            import math
            ref = created[0]

            # Calcular ángulo del disparo original
            angle_rad = math.atan2(ref.dy, ref.dx)

            # Primera bala: desviada -2 grados
            angle_left = angle_rad - math.radians(2)
            dx_left = math.cos(angle_left)
            dy_left = math.sin(angle_left)

            # Segunda bala: desviada +2 grados
            angle_right = angle_rad + math.radians(2)
            dx_right = math.cos(angle_right)
            dy_right = math.sin(angle_right)

            # Reemplazar la primera bala con la versión desviada
            ref.dx = dx_left
            ref.dy = dy_left

            # Agregar segunda bala desviada en la otra dirección
            extra = Projectile(
                ref.x,
                ref.y,
                dx_right, dy_right,
                speed=ref.speed,
                radius=ref.radius,
                color=ref.color,
                effects=list(ref.effects),
                damage=ref.damage,
                owner_id=ref.owner_id,
            )
            created.append(extra)

        self._start_shoot_animation()
        adder = getattr(out_projectiles, "add", None)
        for bullet in created:
            if callable(adder):
                adder(bullet)
            else:
                out_projectiles.append(bullet)
            if callable(self.on_shoot):
                direction = pygame.Vector2(bullet.dx, bullet.dy)
                if direction.length_squared() > 0.0:
                    direction = direction.normalize()
                self.on_shoot((bullet.x, bullet.y), (direction.x, direction.y))

    def draw(self, surf, flash_alpha: int = 255):
        """Dibuja al jugador en la pantalla."""
        # Renderizar trail del dash
        self._draw_dash_trail(surf)

        # Si está reviviendo, renderizar animación especial de revival
        if self.reviviendo:
            self._render_revival(surf)
            return

        # Renderizado normal
        if self._current_animation not in self._animations:
            return

        animation = self._animations[self._current_animation]
        sprite = self._prepare_sprite(animation.current_frame())

        sprite_rect = sprite.get_rect()
        sprite_rect.centerx = int(round(self.x + self.w / 2))
        sprite_rect.centery = int(round(self.y + self.h / 2 - PLAYER_SPRITE_CENTER_OFFSET_Y))

        # Aplicar flash blanco si acaba de recibir daño
        if self.hit_flash_timer > 0.0:
            # Hacer una copia para no modificar el sprite original en caché
            sprite = sprite.copy()
            flash_overlay = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            flash_overlay.fill((255, 255, 255, 220))
            sprite.blit(flash_overlay, (0, 0), special_flags=pygame.BLEND_ADD)

        surf.blit(sprite, sprite_rect)

    def _render_revival(self, surf: pygame.Surface) -> None:
        """
        Renderiza la animación especial de revival.
        Sprite normal + partículas blancas dispersas.
        """
        if not self.frames_revival or self.revival_frame >= len(self.frames_revival):
            return

        # Frame actual seguro
        frame_idx = min(self.revival_frame, len(self.frames_revival) - 1)
        frame = self.frames_revival[frame_idx]

        # Posición del sprite
        sprite_rect = frame.get_rect()
        sprite_rect.centerx = int(round(self.x + self.w / 2))
        sprite_rect.centery = int(round(self.y + self.h / 2 - PLAYER_SPRITE_CENTER_OFFSET_Y))

        # Aplicar flash blanco si acaba de recibir daño (durante revival también)
        if self.hit_flash_timer > 0.0:
            # Hacer una copia para no modificar el frame original en caché
            frame = frame.copy()
            flash_overlay = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            flash_overlay.fill((255, 255, 255, 220))
            frame.blit(flash_overlay, (0, 0), special_flags=pygame.BLEND_ADD)

        # Renderizar sprite normal (sin overlay)
        surf.blit(frame, sprite_rect)

        # Renderizar partículas blancas
        if self.revival_particle_effect:
            for particle in self.revival_particle_effect:
                if particle.is_alive():
                    particle.render(surf)

    def _prepare_sprite(self, base_sprite: pygame.Surface) -> pygame.Surface:
        """Aplica transformaciones al sprite (flip horizontal si mira izquierda)."""
        sprite = base_sprite
        if self._facing == "left":
            sprite = pygame.transform.flip(sprite, True, False)
        return sprite

    def _update_facing(self, move_dx: float, dash_active: bool) -> None:
        """Actualiza la dirección horizontal hacia la que mira el personaje.

        Prioridad: disparo (horizontal) > dash > movimiento > última dirección

        Nota: Solo se modifica la dirección horizontal (left/right).
        Las direcciones verticales (arriba/abajo) en disparo no cambian la orientación.
        """
        horizontal = 0.0

        # Prioridad 1: Si hay dirección de disparo activa, usar esa (pero solo si es horizontal)
        if self._shoot_dir_current != (0, 0):
            shoot_h = self._shoot_dir_current[0]
            if shoot_h != 0:  # Solo si es izquierda o derecha
                horizontal = shoot_h
        # Prioridad 2: Usar dirección del dash si activo
        if horizontal == 0 and dash_active:
            horizontal = self._dash_dir[0]
        # Prioridad 3: Usar dirección de movimiento actual
        if horizontal == 0 and abs(move_dx) > 1e-3:
            horizontal = move_dx
        # Prioridad 4: Usar última dirección de movimiento conocida
        if horizontal == 0 and abs(self._last_move_dir[0]) > 1e-3:
            horizontal = self._last_move_dir[0]

        # Actualizar facing solo si hay cambio horizontal
        if abs(horizontal) > 1e-3:
            self._facing = "left" if horizontal < 0 else "right"


    # ------------------------------------------------------------------
    # Animaciones
    # ------------------------------------------------------------------
    def _resolve_sprite_dir(self, sprite_dir: str | Path | None) -> Path | None:
        if sprite_dir:
            return Path(sprite_dir)
        if CFG.PLAYER_SPRITES_PATH:
            return Path(CFG.PLAYER_SPRITES_PATH)
        return None

    def _load_run_sound(self) -> None:
        """Carga el sonido de caminata."""
        try:
            audio_path = Path("assets/audio/run.mp3")
            if not audio_path.exists():
                # Intentar ruta relativa desde CODIGO
                audio_path = Path(__file__).parent / "assets" / "audio" / "run.mp3"
            if audio_path.exists():
                self.run_sound = pygame.mixer.Sound(audio_path.as_posix())
                self.run_sound.set_volume(0.01)  # 1% del volumen - muy bajo
            else:
                self.run_sound = None
        except (pygame.error, FileNotFoundError):
            self.run_sound = None

    def _update_run_sound(self, moving: bool) -> None:
        """Controla la reproducción del sonido de caminata."""
        if not self.run_sound:
            return
        
        if moving and not self._is_run_sound_playing:
            # Iniciar sonido en loop
            self.run_sound.play(loops=-1)
            self._is_run_sound_playing = True
        elif not moving and self._is_run_sound_playing:
            # Detener sonido
            self.run_sound.stop()
            self._is_run_sound_playing = False
    
    def _load_dash_sound(self) -> None:
        """Carga el sonido de dash."""
        try:
            audio_path = Path("assets/audio/dash_sfx.mp3")
            if not audio_path.exists():
                # Intentar ruta relativa desde CODIGO
                audio_path = Path(__file__).parent / "assets" / "audio" / "dash_sfx.mp3"
            if audio_path.exists():
                self.dash_sound = pygame.mixer.Sound(audio_path.as_posix())
                self.dash_sound.set_volume(0.125)  # 12.5% del volumen
            else:
                self.dash_sound = None
        except (pygame.error, FileNotFoundError):
            self.dash_sound = None
    
    def _load_respawn_sound(self) -> None:
        """Carga el sonido de respawn."""
        try:
            audio_path = Path("assets/audio/respawn_sfx.mp3")
            if not audio_path.exists():
                # Intentar ruta relativa desde CODIGO
                audio_path = Path(__file__).parent / "assets" / "audio" / "respawn_sfx.mp3"
            if audio_path.exists():
                self.respawn_sound = pygame.mixer.Sound(audio_path.as_posix())
                self.respawn_sound.set_volume(0.075)  # 7.5% del volumen
            else:
                self.respawn_sound = None
        except (pygame.error, FileNotFoundError):
            self.respawn_sound = None
    
    def _load_damage_sound(self) -> None:
        """Carga el sonido de daño."""
        try:
            audio_path = Path("assets/audio/dmgplayer_sfx.mp3")
            if not audio_path.exists():
                # Intentar ruta relativa desde CODIGO
                audio_path = Path(__file__).parent / "assets" / "audio" / "dmgplayer_sfx.mp3"
            if audio_path.exists():
                self.damage_sound = pygame.mixer.Sound(audio_path.as_posix())
                self.damage_sound.set_volume(0.05)  # 5% del volumen
            else:
                self.damage_sound = None
        except (pygame.error, FileNotFoundError):
            self.damage_sound = None

    def set_skin(self, sprite_dir: str | Path | None) -> None:
        """Actualiza los sprites y recarga las animaciones (actualmente solo Daniel)."""
        # Nota: Actualmente el sistema no soporta múltiples skins
        # Solo carga desde assets/sprites/player
        try:
            self._animations = self._build_animations()
        except Exception as e:
            print(f"[WARNING] No se pudieron recargar animaciones: {e}")
            self._animations = self._create_empty_animations()

        self._current_animation = "idle"
        self._animation_override = None

    def _cargar_frames_revival(self) -> None:
        """
        Extrae los frames de la animación death_spawn para el efecto de revival.
        Aplica los frame_indices [6,5,4,3,2,1,0] para reproducir en orden inverso.
        """
        if "death_spawn" not in self._animations:
            return

        # Obtener la animación de revival
        anim_revival = self._animations["death_spawn"]
        # Acceder a los frames del animation y aplicar los frame_indices
        if hasattr(anim_revival, '_frames_pool') and hasattr(anim_revival, '_frame_indices'):
            frames_pool = anim_revival._frames_pool
            frame_indices = anim_revival._frame_indices
            # Aplicar los indices para obtener frames en orden inverso
            self.frames_revival = [frames_pool[idx] for idx in frame_indices if idx < len(frames_pool)]
        else:
            # Fallback: crear lista vacía
            self.frames_revival = []

    def _build_animations(self) -> dict[str, Animation]:
        """Carga animaciones desde spritesheets + JSON."""
        json_path = "assets/sprites/player/animations.json"
        sprite_dir = "assets/sprites/player"

        try:
            animations = AnimationManager.load_from_json(json_path, sprite_dir)
            return animations
        except (FileNotFoundError, ValueError) as e:
            raise Exception(f"No se pudieron cargar animaciones: {e}")

    def _create_empty_animations(self) -> dict[str, Animation]:
        """Crea animaciones vacías para fallback (no crashea pero no renderiza nada)."""
        # Crear una superficie vacía de fallback
        empty_surface = pygame.Surface((64, 64))
        empty_surface.fill((0, 0, 0))
        empty_frames = [empty_surface]

        return {
            "idle": Animation(empty_frames, [0], fps=1, loop=False),
            "walk": Animation(empty_frames, [0], fps=1, loop=True),
            "attack": Animation(empty_frames, [0], fps=1, loop=False),
            "death": Animation(empty_frames, [0], fps=1, loop=False),
        }

    def _set_current_animation(self, name: str, *, force_reset: bool = False) -> None:
        """Cambia la animación actual."""
        if name not in self._animations:
            return  # Animación no existe, ignorar

        if self._current_animation != name:
            self._current_animation = name
            self._animations[name].reset()
        elif force_reset:
            self._animations[name].reset()

    def _start_shoot_animation(self) -> None:
        if self._respawn_animating:
            return

        # Determinar qué animación de disparo reproducir según la dirección
        if self._shoot_dir_current == (0, -1) and "shoot_up" in self._animations:
            # Dispara hacia arriba
            self._animation_override = "shoot_up"
            self._set_current_animation("shoot_up", force_reset=True)
        elif self._shoot_dir_current == (0, 1) and "shoot_down" in self._animations:
            # Dispara hacia abajo
            self._animation_override = "shoot_down"
            self._set_current_animation("shoot_down", force_reset=True)
        else:
            # Fallback a animación genérica de disparo (para disparos laterales)
            self._animation_override = "attack"
            self._set_current_animation("attack", force_reset=True)

    def _is_shift_pressed(self) -> bool:
        """Detecta si Shift está presionado (izquierdo o derecho)."""
        keys = pygame.key.get_pressed() if self.controls_enabled else None
        if not keys:
            return False
        return keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

    def _get_input_magnitude(self) -> float:
        """
        Calcula la magnitud del input (0 a ~1.41 en diagonal).
        Utilizado para determinar si el jugador está caminando o corriendo.
        """
        keys = pygame.key.get_pressed() if self.controls_enabled else None
        if not keys:
            return 0.0
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        return math.hypot(dx, dy)

    def _update_animation(self, dt: float, moving: bool) -> None:
        """Determina qué animación reproducir según estado del jugador.

        Prioridad: disparar > movimiento > idle

        Lógica:
        1. death (si está muriendo)
        2. Animaciones de disparo (si está disparando):
           - pistol_aim_run_up (corriendo hacia arriba)
           - pistol_aim_run_down (corriendo hacia abajo)
           - pistol_aim_run (corriendo lateralmente o caminando)
           - pistol_aim (quieto, congelado en frame 5)
        3. Animaciones de movimiento (si se está moviendo):
           - run (corriendo rápido)
           - walk (caminando)
        4. idle (quieto sin disparar)
        """
        # Calcular estado de movimiento actual
        input_mag = self._get_input_magnitude()  # 0 a ~1.41
        is_moving = input_mag > 0
        shift_pressed = self._is_shift_pressed()
        is_running = shift_pressed and is_moving  # Run solo si Shift + movimiento
        is_walking = is_moving and not is_running
        is_shooting = self._shoot_dir_current != (0, 0)

        # Seleccionar animación según prioridad
        if self._respawn_animating:
            active_name = "death"
        elif is_shooting:
            # Prioridad: disparar con diferentes animaciones según velocidad
            shoot_dir_x, shoot_dir_y = self._shoot_dir_current
            if is_running:
                # Corriendo + disparando en direcciones específicas
                if shoot_dir_y < 0:  # Disparando hacia arriba mientras corre
                    active_name = "pistol_aim_run_up"
                elif shoot_dir_y > 0:  # Disparando hacia abajo mientras corre
                    active_name = "pistol_aim_run_down"
                else:  # Disparando horizontalmente mientras corre
                    active_name = "pistol_aim_run"
            elif is_walking:
                # Caminando + disparando
                active_name = "pistol_aim_run"
            else:
                # Quieto + disparando (congelado en frame 5)
                active_name = "pistol_aim"
        elif is_running:
            active_name = "run"
        elif is_walking:
            active_name = "walk"
        else:
            active_name = "idle"

        self._set_current_animation(active_name)

        if active_name in self._animations:
            animation = self._animations[active_name]
            animation.update(dt)

            # Death termina sin repetir
            if self._respawn_animating and animation.is_finished():
                self._respawn_animating = False

    def _update_dash_trail(self, dt: float, dash_active: bool) -> None:
        # Reducir vida de los rastros existentes
        for segment in self._dash_trail:
            segment.life -= dt
        self._dash_trail = [seg for seg in self._dash_trail if seg.life > 0.0]

        # Controlar el spawn de nuevos rastros mientras dura el dash
        self._dash_trail_timer = max(0.0, self._dash_trail_timer - dt)
        if dash_active and self._dash_trail_timer <= 0.0:
            self._dash_trail_timer = self.dash_trail_interval
            cx = self.x + self.w / 2
            cy = (
                self.y
                + self.h / 2
                - PLAYER_SPRITE_CENTER_OFFSET_Y
                + self.dash_trail_vertical_offset
            )
            self._dash_trail.append(DashTrailSegment(pos=(cx, cy), life=self.dash_trail_lifetime))

    def _draw_dash_trail(self, surf) -> None:
        if not self._dash_trail:
            return

        max_life = self.dash_trail_lifetime if self.dash_trail_lifetime > 0 else 0.0001
        size = self.dash_trail_size
        for segment in self._dash_trail:
            life = segment.life
            alpha = max(0, min(255, int(255 * (life / max_life))))
            trail_surface = pygame.Surface((size, size), pygame.SRCALPHA)
            trail_surface.fill((255, 255, 255, alpha))
            pos_x, pos_y = segment.pos
            surf.blit(trail_surface, (pos_x - size / 2, pos_y - size / 2))

    # ------------------------------------------------------------------
    # Armas
    # ------------------------------------------------------------------
    def reset_loadout(self) -> None:
        """Restablece el arma inicial al comenzar una nueva partida."""
        self._owned_weapons.clear()
        self._upgrade_flags.clear()
        self._cooldown_modifiers.clear()
        self.cooldown_scale_base = 1.0
        self.cooldown_scale = 1.0
        self.speed = self.base_speed
        self.max_hp = self.base_max_hp
        self.hp = self.max_hp
        self.max_lives = self.base_max_lives
        self.reset_lives()
        self._previous_lives = self.lives
        self._hits_taken_current_life = 0
        self.invulnerable_timer = 0.0
        self._dash_timer = 0.0
        self._dash_cooldown_timer = 0.0
        self._dash_key_down = False
        self._dash_dir = (0.0, -1.0)
        self._last_move_dir = (0.0, -1.0)
        self._dash_trail.clear()
        self._dash_trail_timer = 0.0
        self._respawn_animating = False
        self._animation_override = None
        self.sprint_control_bonus = 0.0
        self._sprint_control_timer = 0.0
        self._is_sprinting = False
        self.phase_during_dash = False
        self.dash_core_bonus_window = 0.0
        self.dash_core_bonus_iframe = 0.0
        self._recent_enemy_shot_timer = 0.0
        self._was_dashing = False

        self.sprint_multiplier = self.base_sprint_multiplier
        self.dash_duration = self.base_dash_duration
        self.dash_cooldown = self.base_dash_cooldown
        self.dash_iframe_duration = self.dash_duration + 0.08
        self._grant_weapon("bloqueo")
        self.equip_weapon("bloqueo")

    def has_weapon(self, weapon_id: str) -> bool:
        return weapon_id in self._owned_weapons

    def unlock_weapon(self, weapon_id: str, auto_equip: bool = True) -> bool:
        """Añade el arma al inventario. Devuelve True si era nueva."""
        if weapon_id not in self._weapon_factory:
            return False
        is_new = weapon_id not in self._owned_weapons
        self._grant_weapon(weapon_id)
        if auto_equip:
            self.equip_weapon(weapon_id)
        return is_new

    def equip_weapon(self, weapon_id: str) -> None:
        if weapon_id not in self._owned_weapons:
            return
        self.weapon = self._weapon_factory.create(weapon_id, cooldown_scale=self.cooldown_scale)
        self.weapon_id = weapon_id

    def _grant_weapon(self, weapon_id: str) -> None:
        if weapon_id in self._weapon_factory:
            self._owned_weapons.add(weapon_id)

    # -------------------- Modificadores persistentes -------------------
    def refresh_weapon_modifiers(self) -> None:
        """Reaplica mejoras acumuladas al arma equipada."""
        if not self.weapon:
            return
        setter = getattr(self.weapon, "set_cooldown_scale", None)
        if callable(setter):
            setter(self.cooldown_scale)

    # ------------------------- Gestion de upgrades --------------------
    def register_upgrade(self, upgrade_id: str) -> None:
        self._upgrade_flags.add(upgrade_id)

    def has_upgrade(self, upgrade_id: str) -> bool:
        return upgrade_id in self._upgrade_flags

    def add_key_item(self, item_id: str) -> bool:
        if not item_id:
            return False
        is_new = item_id not in self.key_items
        self.key_items.add(item_id)
        return is_new

    def has_key_item(self, item_id: str) -> bool:
        return item_id in self.key_items

    def set_cooldown_modifier(self, upgrade_id: str, multiplier: float) -> None:
        self._cooldown_modifiers[upgrade_id] = float(multiplier)
        self._recompute_cooldown_scale()

    def _recompute_cooldown_scale(self) -> None:
        scale = self.cooldown_scale_base
        for mult in self._cooldown_modifiers.values():
            scale *= mult
        scale = max(0.35, scale)
        self.cooldown_scale = scale
        self.refresh_weapon_modifiers()

    def notify_enemy_shot(self, window: float | None = None) -> None:
        if window is None:
            window = self.dash_core_bonus_window if self.dash_core_bonus_window > 0.0 else 0.15
        if window <= 0.0:
            return
        self._recent_enemy_shot_timer = max(self._recent_enemy_shot_timer, window)
