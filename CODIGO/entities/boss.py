"""
Boss fight principal — Echoes.

Wall boss anclado en la pared superior de la sala.
Se desplaza lateralmente con animación idle.
"""

import os
import math
import random
import pygame
from typing import Optional


def cargar_boss_idle(ruta: str) -> list[pygame.Surface]:
    """
    Carga boss_idle.png y divide en frames (4 cols x 3 filas).

    Args:
        ruta: ruta al archivo PNG

    Returns:
        Lista de 12 superficies pygame (frames)
    """
    try:
        img = pygame.image.load(ruta).convert_alpha()
    except pygame.error as e:
        print(f"[BOSS] Error cargando {ruta}: {e}")
        return []

    w, h = img.get_size()

    # Validar dimensiones esperadas (2944x1200 para 4x3 frames de 736x400)
    if w != 2944 or h != 1200:
        print(f"[BOSS] Advertencia: dimensiones inesperadas {w}x{h}")
        print(f"       Esperadas: 2944x1200 (4x3 frames de 736x400 cada uno)")

    frame_w, frame_h = 736, 400
    frames = []

    # Extraer exactamente 11 frames (primeros 11 del spritesheet 4x3)
    frame_count = 0
    for row in range(3):
        for col in range(4):
            if frame_count >= 11:  # Límite duro: máximo 11 frames
                break
            x = col * frame_w
            y = row * frame_h
            frame = img.subsurface(pygame.Rect(x, y, frame_w, frame_h))
            frames.append(frame.copy())
            frame_count += 1
        if frame_count >= 11:
            break

    print(f"[BOSS] Cargados {len(frames)} frames de {ruta}")
    return frames


class Boss:
    """
    Wall boss anclado en la pared superior de la sala.
    Se desplaza lateralmente. Solo animación idle por ahora.
    """

    # Configuración de animación
    FPS_IDLE = 8  # frames por segundo

    # Configuración de movimiento
    SPEED = 60  # px/segundo lateral
    MARGIN = 50  # margen desde bordes de sala

    # Escala de render — el sprite es muy grande (736x400)
    # Escalar para que se vea proporcional a la sala
    RENDER_SCALE = 0.25  # 25% → 184x100px en pantalla

    # Configuración de vida
    MAX_HP = 100  # Vida máxima del boss
    HIT_FLASH_DURATION = 0.15  # Duración del titilar blanco al recibir daño

    def __init__(
        self,
        sala_rect: pygame.Rect,
        pared_superior_y: int
    ):
        """
        Args:
            sala_rect: rect del área jugable de la sala (en píxeles)
            pared_superior_y: Y donde termina la pared superior (en píxeles)
        """
        self.sala_rect = sala_rect
        self.pared_y = pared_superior_y
        self.vivo = True
        self.activo = False  # se activa al entrar a la sala

        # Sistema de vida
        self.hp = self.MAX_HP
        self.max_hp = self.MAX_HP
        self.hit_flash_timer = 0.0  # Timer para titilar blanco

        # Cargar sprites
        self.frames: list[pygame.Surface] = []
        self.frame_actual = 0
        self.timer_frame = 0.0
        self.intervalo_frame = 1.0 / self.FPS_IDLE

        # Tamaño de render
        self.render_w = 0
        self.render_h = 0

        # Posición — se calcula después de cargar sprites
        self.x = float(sala_rect.centerx)
        self.y = 0.0

        # Movimiento lateral
        self.velocidad_x = self.SPEED  # positivo = derecha
        self._debug_frame_counter = 0

        self._cargar_sprites()
        self._calcular_posicion_inicial()

    def _cargar_sprites(self) -> None:
        """Carga boss_idle.png desde assets."""
        # Buscar en ubicaciones comunes
        rutas_candidatas = [
            "assets/boss_idle.png",
            "assets/sprites/boss_idle.png",
            "assets/enemies/boss_idle.png",
            "assets/sprites/enemies/boss_idle.png",
        ]

        ruta_encontrada: Optional[str] = None
        for ruta in rutas_candidatas:
            if os.path.exists(ruta):
                ruta_encontrada = ruta
                break

        if not ruta_encontrada:
            print("[BOSS] boss_idle.png no encontrado.")
            print("       Ubicaciones intentadas:")
            for ruta in rutas_candidatas:
                print(f"         - {ruta}")
            self._usar_placeholder()
            return

        frames_raw = cargar_boss_idle(ruta_encontrada)
        if not frames_raw:
            self._usar_placeholder()
            return

        # Escalar frames al tamaño de render
        FRAME_W_RAW = 736
        FRAME_H_RAW = 400
        self.render_w = int(FRAME_W_RAW * self.RENDER_SCALE)
        self.render_h = int(FRAME_H_RAW * self.RENDER_SCALE)

        self.frames = [
            pygame.transform.scale(f, (self.render_w, self.render_h))
            for f in frames_raw
        ]
        print(f"[BOSS] Tamaño de render: {self.render_w}x{self.render_h}px "
              f"(escala {self.RENDER_SCALE*100:.0f}%)")

    def _usar_placeholder(self) -> None:
        """Placeholder visible si falta el PNG."""
        self.render_w = 200
        self.render_h = 80

        # Crear múltiples frames idénticos para que la animación funcione
        # aunque el PNG no esté disponible
        placeholder_frames = []

        for frame_idx in range(11):  # 11 frames como en el spritesheet real
            surf = pygame.Surface((self.render_w, self.render_h), pygame.SRCALPHA)
            surf.fill((120, 0, 0, 200))
            pygame.draw.rect(surf, (200, 0, 0), (0, 0, self.render_w, self.render_h), 2)

            # Texto "BOSS" centrado
            try:
                font = pygame.font.SysFont("monospace", 20, bold=True)
                txt = font.render(f"BOSS [{frame_idx+1}]", False, (255, 100, 100))
                surf.blit(txt, (
                    self.render_w // 2 - txt.get_width() // 2,
                    self.render_h // 2 - txt.get_height() // 2
                ))
            except Exception:
                pass

            placeholder_frames.append(surf)

        self.frames = placeholder_frames
        print(f"[BOSS] Usando placeholder con {len(self.frames)} frames (PNG no encontrado)")

    def _calcular_posicion_inicial(self) -> None:
        """
        Posiciona el boss centrado en la pared superior.
        El sprite comienza un poco abajo de la pared superior.
        Se sube 64 píxeles para el posicionamiento correcto.
        """
        # X: centrado en la sala al inicio
        self.x = float(self.sala_rect.centerx - self.render_w // 2)

        # Y: posicionado un poco más abajo de la pared superior
        # en lugar de colgar encima. Se sube 64 píxeles.
        self.y = float(self.pared_y - 64)

        print(f"[BOSS] Posición inicial: ({self.x:.0f}, {self.y:.0f})")

    def activar(self) -> None:
        """Llamar cuando el jugador entra a la sala."""
        self.activo = True
        limite_izq = self.sala_rect.left + self.MARGIN
        limite_der = self.sala_rect.right - self.render_w - self.MARGIN
        rango_movimiento = limite_der - limite_izq

        print(f"\n[BOSS] [OK] BOSS ACTIVADO - LISTO PARA ACTUALIZAR Y RENDERIZAR")
        print(f"      Posición inicial: ({self.x:.0f}, {self.y:.0f})")
        print(f"      Frames cargados: {len(self.frames)}")
        print(f"      Sala rect: left={self.sala_rect.left}, right={self.sala_rect.right}, "
              f"width={self.sala_rect.width}")
        print(f"      Límites de movimiento: izq={limite_izq:.0f}, der={limite_der:.0f}, "
              f"rango={rango_movimiento:.0f}px")
        print(f"      Sprite: render_w={self.render_w}, render_h={self.render_h}")
        print(f"      Parámetros: SPEED={self.SPEED} px/sec, MARGIN={self.MARGIN}px\n")

    def take_damage(self, amount: int) -> None:
        """Inflige daño al boss y activa el efecto de titilar blanco."""
        if not self.vivo:
            return

        self.hp = max(0, self.hp - amount)
        self.hit_flash_timer = self.HIT_FLASH_DURATION

        if self.hp <= 0:
            self.vivo = False
            print(f"[BOSS] BOSS DERROTADO")
        else:
            print(f"[BOSS] Daño recibido: {amount} | HP: {self.hp}/{self.max_hp}")

    def update(self, dt: float) -> None:
        """Actualiza animación y movimiento lateral."""
        self._debug_frame_counter += 1

        # Actualizar timer de parpadeo
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

        if not self.activo or not self.vivo:
            if self._debug_frame_counter % 60 == 0 and self._debug_frame_counter < 120:
                print(f"[BOSS] UPDATE BLOQUEADO: activo={self.activo}, vivo={self.vivo}")
            return

        # Debug: mostrar estado cada 30 frames
        if self._debug_frame_counter % 30 == 0:
            print(f"[BOSS] UPDATE ACTIVO: x={self.x:.1f}, vel={self.velocidad_x}, dt={dt:.4f}, "
                  f"frame={self.frame_actual}/{len(self.frames)}, sala_rect=({self.sala_rect.left}, {self.sala_rect.right})")

        # Actualizar animación idle
        self.timer_frame += dt
        if self.timer_frame >= self.intervalo_frame:
            self.timer_frame -= self.intervalo_frame
            self.frame_actual = (self.frame_actual + 1) % len(self.frames)

        # Movimiento lateral
        x_anterior = self.x
        self.x += self.velocidad_x * dt

        # Límites laterales de la sala
        limite_izq = self.sala_rect.left + self.MARGIN
        limite_der = self.sala_rect.right - self.render_w - self.MARGIN

        if self.x <= limite_izq:
            self.x = float(limite_izq)
            self.velocidad_x = abs(self.velocidad_x)  # ir derecha
            print(f"[BOSS] [LEFT] Rebotó en límite izquierdo: x={x_anterior:.1f}→{self.x:.0f}, "
                  f"vel→{self.velocidad_x}")

        elif self.x >= limite_der:
            self.x = float(limite_der)
            self.velocidad_x = -abs(self.velocidad_x)  # ir izquierda
            print(f"[BOSS] [RIGHT] Rebotó en límite derecho: x={x_anterior:.1f}→{self.x:.0f}, "
                  f"vel→{self.velocidad_x}")

    def render(self, surface: pygame.Surface) -> None:
        """Renderiza el boss en la pantalla con titilar blanco."""
        if not self.frames:
            return

        frame = self.frames[self.frame_actual]
        pos_x = int(self.x)
        pos_y = int(self.y)

        # Aplicar efecto de titilar blanco cuando recibe daño
        if self.hit_flash_timer > 0.0:
            # Crear una versión blanca del frame
            frame_white = frame.copy()
            white_surf = pygame.Surface(frame_white.get_size(), pygame.SRCALPHA)
            white_surf.fill((255, 255, 255, 200))  # Blanco semi-opaco
            frame_white.blit(white_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(frame_white, (pos_x, pos_y))
        else:
            surface.blit(frame, (pos_x, pos_y))

    @property
    def rect(self) -> pygame.Rect:
        """Rect actual del boss para colisiones."""
        return pygame.Rect(
            int(self.x),
            int(self.y),
            self.render_w,
            self.render_h
        )


# ============================================================================
# SISTEMA DE ATAQUES DEL BOSS
# ============================================================================

class AtaqueBoss:
    """
    Clase base para todos los ataques del boss.
    Cada ataque hereda de esta clase y define su comportamiento único.
    """
    def __init__(self):
        self.activo = True
        self.terminado = False

    def update(self, dt: float, jugadores: list):
        """
        Actualiza el estado del ataque.

        Args:
            dt: Delta time en segundos
            jugadores: Lista de objetos jugador (pueden ser None)
        """
        raise NotImplementedError

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        """
        Renderiza los efectos visuales del ataque.

        Args:
            surface: Superficie donde renderizar
            camera_offset: Offset de cámara (x, y)
        """
        raise NotImplementedError


class ProyectilBoss:
    """
    Proyectil específico del boss.
    Soporta movimiento normal y comportamientos especiales
    (pausa antes de explotar, etc.).
    """

    def __init__(
        self,
        x: float,
        y: float,
        dx: float,
        dy: float,
        daño: int = 1,
        radio: int = 8,
        color=(255, 80, 80),
        color_borde=(255, 200, 200),
        puede_explotar: bool = False,
        tiempo_explosion: float = 0.0,
        velocidad: float = 180.0
    ):
        """
        Args:
            x, y: Posición inicial
            dx, dy: Dirección normalizada (rangos -1 a 1)
            daño: Daño que inflige al jugador
            radio: Radio visual del proyectil
            color: Color RGB del cuerpo
            color_borde: Color RGB del borde
            puede_explotar: Si puede entrar en fase de explosión
            tiempo_explosion: Segundos antes de pausarse y explotar
            velocidad: Velocidad en píxeles/segundo
        """
        self.x = x
        self.y = y
        self.dx = dx  # dirección normalizada X
        self.dy = dy  # dirección normalizada Y
        self.velocidad = velocidad  # se multiplica por dx/dy
        self.daño = daño
        self.radio = radio
        self.color = color
        self.color_borde = color_borde
        self.activo = True

        # Sistema de explosión (para ataque fanout)
        self.puede_explotar = puede_explotar
        self.tiempo_explosion = tiempo_explosion
        self.timer_vida = 0.0
        self.pausado = False
        self.timer_pausa = 0.0
        self.DURACION_PAUSA = 0.4  # segundos quieto antes de explotar
        self.explotar_flag = False

        # Pulso visual
        self.timer_pulso = 0.0

    @property
    def rect(self) -> pygame.Rect:
        """Rect del proyectil para colisiones."""
        return pygame.Rect(
            int(self.x) - self.radio,
            int(self.y) - self.radio,
            self.radio * 2,
            self.radio * 2
        )

    def update(self, dt: float):
        """Actualiza posición y estado del proyectil."""
        if not self.activo:
            return

        self.timer_vida += dt
        self.timer_pulso += dt

        # Lógica de pausa y explosión
        if self.puede_explotar:
            # Si no está pausado, verificar si debe empezar a pausarse
            if (not self.pausado and
                    self.timer_vida >= self.tiempo_explosion):
                self.pausado = True
                self.timer_pausa = 0.0
                return  # No se mueve mientras está pausado

            # Si está pausado, contar el tiempo
            if self.pausado:
                self.timer_pausa += dt
                if self.timer_pausa >= self.DURACION_PAUSA:
                    self.explotar_flag = True
                    self.activo = False
                return

        # Movimiento normal (cuando no está pausado)
        self.x += self.dx * self.velocidad * dt
        self.y += self.dy * self.velocidad * dt

        # Eliminar si sale de la pantalla (con margen)
        MARGEN = 100
        if (self.x < -MARGEN or self.x > 960 + MARGEN or
                self.y < -MARGEN or self.y > 640 + MARGEN):
            self.activo = False

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        """Renderiza el proyectil con efectos visuales."""
        if not self.activo:
            return

        px = int(self.x - camera_offset[0])
        py = int(self.y - camera_offset[1])

        # Pulso de tamaño sutil
        pulso = math.sin(self.timer_pulso * 8) * 2
        r = self.radio + int(pulso)

        # Halo exterior semitransparente
        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(
            halo,
            (*self.color, 40),
            (r * 2, r * 2),
            r * 2
        )
        surface.blit(halo, (px - r * 2, py - r * 2))

        # Cuerpo del proyectil
        pygame.draw.circle(surface, self.color, (px, py), r)

        # Borde brillante
        pygame.draw.circle(surface, self.color_borde, (px, py), r, 2)

        # Indicador de explosión pendiente (anillo de alerta)
        if self.pausado:
            progreso = self.timer_pausa / self.DURACION_PAUSA
            alpha = int(200 * progreso)
            warn = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
            pygame.draw.circle(
                warn,
                (255, 255, 0, alpha),
                (r * 3, r * 3),
                int(r * (1 + progreso * 2)),
                2
            )
            surface.blit(warn, (px - r * 3, py - r * 3))
