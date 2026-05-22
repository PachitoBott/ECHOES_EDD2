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
    SPEED = 200  # px/segundo lateral (aumentado de 60)
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

        # Inicializar sistema de ataques
        self._init_sistema_ataques()

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

    def update(self, dt: float, jugadores=None) -> None:
        """
        Actualiza animación, movimiento lateral y sistema de ataques.

        Args:
            dt: Delta time en segundos
            jugadores: Lista de objetos jugador (opcional)
        """
        if jugadores is None:
            jugadores = []

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

        # Actualizar sistema de ataques
        self._update_ataques(dt, jugadores)

    def render(self, surface: pygame.Surface) -> None:
        """
        Renderiza el boss en la pantalla con titilar blanco.
        Primero renderiza ataques, luego el sprite del boss.
        """
        # Renderizar ataques ANTES del sprite para que queden debajo
        self._render_ataques(surface, camera_offset=(0, 0))

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

    # ========================================================================
    # MÉTODOS DEL SISTEMA DE ATAQUES
    # ========================================================================

    def _init_sistema_ataques(self) -> None:
        """Inicializa el sistema de ataques del boss."""
        # Ataques activos en curso
        self.ataques_activos: list = []

        # Proyectiles activos en pantalla
        self.proyectiles: list = []

        # Cooldowns individuales por ataque (en segundos)
        self.cooldowns = {
            "fanout": 0.0,
            "zigzag": 0.0,
            "laser": 0.0,
            "emp": 0.0,
        }

        # Duraciones de cooldown por ataque
        self.COOLDOWN_DURACION = {
            "fanout": 2.0,   # reducido de 4.0
            "zigzag": 2.5,   # reducido de 5.0
            "laser": 3.0,    # reducido de 6.0
            "emp": 4.0,      # reducido de 8.0
        }

        # Timer entre decisiones de ataque
        self.timer_decision = 0.0
        self.INTERVALO_DECISION = 1.2  # reducido de 2.5 segundos

        # Fase del boss (1-3 según vida)
        self.fase = 1

        # Último ataque usado (para no repetir)
        self.ultimo_ataque = None

        print(f"[BOSS] Sistema de ataques inicializado")

    def _update_ataques(self, dt: float, jugadores: list) -> None:
        """
        Actualiza todos los ataques activos.
        Maneja cooldowns, generación de ataques y proyectiles.
        """
        # Actualizar cooldowns
        for nombre in self.cooldowns:
            if self.cooldowns[nombre] > 0:
                self.cooldowns[nombre] -= dt

        # Actualizar ataques activos
        for ataque in self.ataques_activos:
            ataque.update(dt, jugadores)

        # Limpiar ataques terminados
        self.ataques_activos = [
            a for a in self.ataques_activos
            if not a.terminado
        ]

        # Actualizar proyectiles activos
        for proj in self.proyectiles[:]:  # Copiar para iteración segura
            proj.update(dt)

        # Eliminar proyectiles inactivos (limpiar in-place, no reasignar)
        # para mantener la referencia que los ataques tienen
        self.proyectiles[:] = [p for p in self.proyectiles if p.activo]

        # Decidir próximo ataque
        self.timer_decision -= dt
        if self.timer_decision <= 0:
            self._decidir_ataque(jugadores)
            self.timer_decision = self.INTERVALO_DECISION

        # Actualizar fase según vida
        self._actualizar_fase()

    def _actualizar_fase(self) -> None:
        """
        Actualiza la fase del boss según su vida actual.
        Fase 1: 100-67% vida
        Fase 2: 66-34% vida
        Fase 3: 33-1% vida
        """
        if self.max_hp <= 0:
            return

        porcentaje = self.hp / self.max_hp

        if porcentaje > 0.66:
            self.fase = 1
        elif porcentaje > 0.33:
            self.fase = 2
        else:
            self.fase = 3

    def _decidir_ataque(self, jugadores: list) -> None:
        """
        Selecciona qué ataque usar según fase, cooldowns y disponibilidad.
        Solo elige si no hay ataques activos (excepto en fase 3).
        """
        if not jugadores or not self.activo:
            return

        # Ataques disponibles por fase
        disponibles_por_fase = {
            1: ["fanout", "zigzag"],
            2: ["fanout", "zigzag", "laser"],
            3: ["fanout", "zigzag", "laser", "emp"],
        }

        candidatos = disponibles_por_fase.get(self.fase, ["fanout"])

        # Filtrar por cooldown disponible
        candidatos = [
            nombre for nombre in candidatos
            if self.cooldowns.get(nombre, 0) <= 0
        ]

        # No repetir el último ataque si hay más opciones
        if len(candidatos) > 1 and self.ultimo_ataque in candidatos:
            candidatos.remove(self.ultimo_ataque)

        if not candidatos:
            return

        # Verificar si hay algún ataque ya activo
        if len(self.ataques_activos) > 0:
            # En fase 3, puede encadenar 2 ataques simultáneamente
            if self.fase < 3:
                return

        # Seleccionar ataque al azar
        nombre_elegido = random.choice(candidatos)
        self._ejecutar_ataque(nombre_elegido, jugadores)
        self.ultimo_ataque = nombre_elegido

    def _ejecutar_ataque(self, nombre: str, jugadores: list) -> None:
        """
        Instancia y activa un ataque específico.
        Crea la instancia del ataque y la añade a la lista de ataques activos.
        """
        # Centro inferior del boss (desde donde salen proyectiles)
        boca_x = self.x + self.render_w // 2
        boca_y = self.y + self.render_h

        # Obtener jugador más cercano para ataques dirigidos
        jugador_objetivo = self._get_jugador_mas_cercano(jugadores)
        if not jugador_objetivo:
            return

        ataque = None

        # Crear instancia del ataque elegido
        if nombre == "fanout":
            ataque = AtaqueFanout(
                boca_x, boca_y,
                jugador_objetivo,
                self.proyectiles
            )
        elif nombre == "zigzag":
            ataque = AtaqueZigzag(
                boca_x, boca_y,
                self.proyectiles
            )
        elif nombre == "laser":
            # Verificar si el láser puede usarse (jugador debe estar debajo)
            if not self._puede_usar_laser(jugadores):
                print(f"[BOSS] Láser no puede activarse: jugador no está en rango")
                return

            ataque = AtaqueLaser(
                boca_x, boca_y,
                self.render_w,
                self.x
            )
        elif nombre == "emp":
            # Centro del boss como punto de origen de las ondas
            centro_boss_x = self.x + self.render_w // 2
            centro_boss_y = self.y + self.render_h // 2

            ataque = AtaqueEMP(
                centro_boss_x, centro_boss_y,
                self.proyectiles
            )
        else:
            print(f"[BOSS] Ataque '{nombre}' aún no implementado")
            return

        # Añadir ataque a la lista de activos
        if ataque:
            self.ataques_activos.append(ataque)
            print(f"[BOSS] Ejecutando ataque: {nombre} (fase {self.fase})")

        # Establecer cooldown
        self.cooldowns[nombre] = self.COOLDOWN_DURACION[nombre]

    def _get_jugador_mas_cercano(self, jugadores: list):
        """
        Devuelve el jugador más cercano al boss.
        Se usa como objetivo para ataques dirigidos.
        """
        if not jugadores:
            return None

        boss_cx = self.x + self.render_w // 2
        return min(
            jugadores,
            key=lambda j: abs(
                (j.x + getattr(j, 'w', 32) // 2) - boss_cx
            ) if hasattr(j, 'x') else float('inf')
        )

    def _render_ataques(self, surface: pygame.Surface,
                        camera_offset=(0, 0)) -> None:
        """
        Renderiza todos los ataques y proyectiles activos.
        Llamada desde render() para que aparezcan debajo del sprite del boss.
        """
        # Renderizar proyectiles
        for proj in self.proyectiles:
            proj.render(surface, camera_offset)

        # Renderizar ataques
        for ataque in self.ataques_activos:
            ataque.render(surface, camera_offset)

    def _puede_usar_laser(self, jugadores: list) -> bool:
        """
        Verifica si el láser puede activarse.
        El láser solo se activa si un jugador está dentro del rango
        horizontal del boss (ancho del boss ± margen).
        """
        boss_izq = self.x - 60  # 60px de margen a la izquierda
        boss_der = self.x + self.render_w + 60  # 60px de margen a la derecha

        for jugador in jugadores:
            if not hasattr(jugador, 'x'):
                continue

            # Centro X del jugador
            jx = jugador.x + getattr(jugador, 'w', 32) // 2

            # Verificar si está dentro del rango horizontal
            if boss_izq <= jx <= boss_der:
                return True

        return False

    def verificar_colisiones_jugador(self, jugador) -> None:
        """
        Verifica si algún proyectil del boss golpea al jugador.
        Debe ser llamado desde el game loop para cada jugador.
        """
        if not hasattr(jugador, 'x') or not hasattr(jugador, 'y'):
            return

        # Obtener rect del jugador
        jugador_w = getattr(jugador, 'w', 32)
        jugador_h = getattr(jugador, 'h', 48)
        jugador_rect = pygame.Rect(
            jugador.x,
            jugador.y,
            jugador_w,
            jugador_h
        )

        # Verificar colisión con proyectiles
        for proj in self.proyectiles[:]:  # Copiar lista para iteración segura
            if not proj.activo:
                continue

            if proj.rect.colliderect(jugador_rect):
                # Aplicar daño al jugador
                jugador.take_damage(proj.daño)
                proj.activo = False
                print(f"[BOSS] Proyectil golpeó al jugador: daño={proj.daño}")

        # Verificar daño del láser (si existe)
        for ataque in self.ataques_activos:
            # Esto se rellenará cuando se implemente AtaqueLaser
            if hasattr(ataque, 'verificar_colision_jugador'):
                ataque.verificar_colision_jugador(jugador, jugador_rect)


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


# ============================================================================
# ATAQUE 1: ABANICO FRAGMENTADO (FANOUT)
# ============================================================================

class AtaqueFanout(AtaqueBoss):
    """
    Dispara 6 proyectiles en abanico de 120 grados.
    Cada proyectil se pausa en el aire y explota en 4 hijos en forma de cruz.
    """

    N_PROYECTILES = 6
    ANGULO_TOTAL = 120  # grados del abanico
    VELOCIDAD_PADRE = 400  # px/segundo (aumentado de 300)
    VELOCIDAD_HIJO = 500   # px/segundo (aumentado de 400)
    DAÑO_PADRE = 1
    DAÑO_HIJO = 1
    RADIO_PADRE = 10
    RADIO_HIJO = 6
    TIEMPO_EXPLOSION = 0.6  # segundos antes de pausarse (viaja más lejos)

    def __init__(self, boca_x: float, boca_y: float,
                 jugador, lista_proyectiles: list):
        """
        Args:
            boca_x, boca_y: Posición donde se generan los proyectiles
            jugador: Jugador objetivo (para calcular ángulo base)
            lista_proyectiles: Lista donde se añaden los proyectiles generados
        """
        super().__init__()
        self.lista_proyectiles = lista_proyectiles
        self.padres_activos = []

        # Calcular dirección base hacia el jugador más cercano
        dx_base = jugador.x - boca_x
        dy_base = jugador.y - boca_y
        dist = max(1, math.sqrt(dx_base**2 + dy_base**2))

        # Ángulo base normalizado
        ang_base = math.degrees(
            math.atan2(dy_base / dist, dx_base / dist)
        )

        # Crear 6 proyectiles padre en abanico
        for i in range(self.N_PROYECTILES):
            # Interpolación lineal de 0 a 1
            t = i / (self.N_PROYECTILES - 1)

            # Calcular ángulo para este proyectil
            ang = ang_base - self.ANGULO_TOTAL / 2 + t * self.ANGULO_TOTAL
            rad = math.radians(ang)

            # Vector de dirección
            dx = math.cos(rad)
            dy = math.sin(rad)

            # Crear proyectil padre
            proj = ProyectilBoss(
                x=boca_x,
                y=boca_y,
                dx=dx,
                dy=dy,
                daño=self.DAÑO_PADRE,
                radio=self.RADIO_PADRE,
                color=(220, 60, 60),
                color_borde=(255, 180, 180),
                puede_explotar=True,
                tiempo_explosion=self.TIEMPO_EXPLOSION,
                velocidad=self.VELOCIDAD_PADRE
            )
            self.padres_activos.append(proj)
            lista_proyectiles.append(proj)

        print(f"[ATAQUE] AtaqueFanout: {self.N_PROYECTILES} proyectiles "
              f"en abanico de {self.ANGULO_TOTAL}°")

    def update(self, dt: float, jugadores: list) -> None:
        """
        Verifica si algún proyectil padre explotó y crea los hijos.
        Termina cuando todos los padres están inactivos.
        """
        # Verificar si algún padre explotó
        for padre in self.padres_activos:
            if padre.explotar_flag and not padre.activo:
                self._crear_hijos(padre)
                padre.explotar_flag = False

        # Terminar cuando todos los padres estén inactivos
        if all(not p.activo for p in self.padres_activos):
            self.terminado = True

    def _crear_hijos(self, padre: ProyectilBoss) -> None:
        """
        Crea 4 proyectiles hijo en forma de cruz (cardinal).
        Se disparan desde la posición del padre en el momento de explosión.
        """
        # Direcciones cardinales: arriba, abajo, izquierda, derecha
        direcciones = [
            (0, -1),  # arriba
            (0, 1),   # abajo
            (-1, 0),  # izquierda
            (1, 0),   # derecha
        ]

        for dx, dy in direcciones:
            hijo = ProyectilBoss(
                x=padre.x,
                y=padre.y,
                dx=dx,
                dy=dy,
                daño=self.DAÑO_HIJO,
                radio=self.RADIO_HIJO,
                color=(255, 140, 60),
                color_borde=(255, 220, 150),
                puede_explotar=False,
                velocidad=self.VELOCIDAD_HIJO
            )
            self.lista_proyectiles.append(hijo)

    def render(self, surface: pygame.Surface,
               camera_offset=(0, 0)) -> None:
        """Los proyectiles se renderizan solos en _render_ataques()."""
        pass


# ============================================================================
# ATAQUE 2: ZIGZAG DE BALAS
# ============================================================================

class ProyectilZigzag:
    """
    Proyectil especial para zigzag que se mueve en patrón sinusoidal.
    Se mueve hacia abajo mientras oscila lado a lado.
    """
    def __init__(self, x: float, y: float, lado: int,
                 radio: int = 8, velocidad_y: float = 350):
        self.x = x
        self.y = y
        self.radio = radio
        self.velocidad_y = velocidad_y
        self.lado = lado  # +1 o -1 para dirección inicial
        self.activo = True

        # Oscilación lateral (zigzag)
        self.amplitud = 80  # píxeles de desviación
        self.frecuencia = 0.08  # ciclos por segundo
        self.timer_oscilacion = 0.0

        self.color = (200, 50, 200)
        self.color_borde = (255, 180, 255)
        self.daño = 1

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x) - self.radio,
            int(self.y) - self.radio,
            self.radio * 2,
            self.radio * 2
        )

    def update(self, dt: float):
        if not self.activo:
            return

        # Movimiento vertical (hacia abajo)
        self.y += self.velocidad_y * dt

        # Movimiento horizontal (zigzag sinusoidal)
        self.timer_oscilacion += dt
        offset_x = self.amplitud * math.sin(self.timer_oscilacion * self.frecuencia * 2 * math.pi)
        self.x += offset_x * dt * self.lado

        # Eliminar si sale de pantalla
        if self.y > 680 or self.x < -100 or self.x > 1060:
            self.activo = False

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        if not self.activo:
            return

        px = int(self.x - camera_offset[0])
        py = int(self.y - camera_offset[1])

        # Halo
        halo = pygame.Surface((self.radio * 4, self.radio * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*self.color, 40), (self.radio * 2, self.radio * 2), self.radio * 2)
        surface.blit(halo, (px - self.radio * 2, py - self.radio * 2))

        # Cuerpo
        pygame.draw.circle(surface, self.color, (px, py), self.radio)
        # Borde
        pygame.draw.circle(surface, self.color_borde, (px, py), self.radio, 2)


class AtaqueZigzag(AtaqueBoss):
    """
    Dispara 12 proyectiles que se mueven en patrón zigzag descendente.
    Los proyectiles oscilan mientras bajan hacia el jugador.
    Incluye telegraph visual antes de comenzar el disparo.
    """

    N_BALAS = 12
    INTERVALO = 0.08  # segundos entre disparos
    VELOCIDAD_Y = 250  # px/segundo hacia abajo
    DAÑO = 1
    RADIO = 8
    TELEGRAPH = 0.3  # segundos de aviso visual

    def __init__(self, boca_x: float, boca_y: float,
                 lista_proyectiles: list):
        """
        Args:
            boca_x, boca_y: Posición donde se generan los proyectiles
            lista_proyectiles: Lista donde se añaden los proyectiles generados
        """
        super().__init__()
        self.boca_x = boca_x
        self.boca_y = boca_y
        self.lista_proyectiles = lista_proyectiles

        # Control del disparo
        self.balas_disparadas = 0
        self.timer_bala = 0.0
        self.lado = 1  # Alterna +1 (derecha) y -1 (izquierda)

        # Fase de telegraph
        self.fase = "telegraph"  # telegraph → activo → terminado
        self.timer_fase = 0.0

        print(f"[ATAQUE] AtaqueZigzag: {self.N_BALAS} proyectiles en zigzag")

    def update(self, dt: float, jugadores: list) -> None:
        """
        Actualiza el ataque: telegraph → disparo de balas → terminado.
        """
        self.timer_fase += dt

        if self.fase == "telegraph":
            # Esperar fase de telegraph
            if self.timer_fase >= self.TELEGRAPH:
                self.fase = "activo"
                self.timer_fase = 0.0
            return

        if self.fase == "activo":
            # Disparar balas
            if self.balas_disparadas >= self.N_BALAS:
                self.terminado = True
                return

            self.timer_bala += dt
            if self.timer_bala >= self.INTERVALO:
                self.timer_bala -= self.INTERVALO
                self._disparar_bala()

    def _disparar_bala(self) -> None:
        """
        Dispara un proyectil zigzag que oscila mientras baja.
        """
        # Posición X ligeramente aleatoria para variedad
        offset_x = random.uniform(-60, 60)

        # Crear proyectil zigzag
        proj = ProyectilZigzag(
            x=self.boca_x + offset_x,
            y=self.boca_y,
            lado=self.lado,
            radio=self.RADIO,
            velocidad_y=self.VELOCIDAD_Y
        )
        self.lista_proyectiles.append(proj)

        # Contabilizar disparo y alternar lado
        self.balas_disparadas += 1
        self.lado *= -1  # Alternar dirección (izquierda <-> derecha)

    def render(self, surface: pygame.Surface,
               camera_offset=(0, 0)) -> None:
        """
        Los proyectiles se renderizan solos en _render_ataques().
        No necesita renderizado adicional.
        """
        pass


# ============================================================================
# ATAQUE 3: LÁSER DE BARRIDO
# ============================================================================

class AtaqueLaser(AtaqueBoss):
    """
    Dispara un láser ancho (80px) hacia abajo cuando un jugador está
    debajo del boss.
    Tiene fase de telegraph (aviso visual) antes de activarse.
    Causa daño continuo mientras está activo.
    """

    ANCHO_LASER = 80  # píxeles de ancho
    DURACION = 1.5  # segundos de activo
    TELEGRAPH = 0.6  # segundos de aviso visual
    DAÑO_POR_INTERVALO = 1  # daño por aplicación
    DAÑO_INTERVALO = 0.3  # cada cuántos segundos aplica daño
    LASER_HEIGHT = 640  # altura máxima (llega hasta el suelo)

    def __init__(self, boca_x: float, boca_y: float,
                 boss_render_w: int, boss_x: float):
        """
        Args:
            boca_x: Centro X donde sale el láser
            boca_y: Y donde sale el láser (boca del boss)
            boss_render_w: Ancho del sprite del boss (para referencias)
            boss_x: X del boss (para referencias)
        """
        super().__init__()
        self.boca_x = boca_x
        self.boca_y = boca_y
        self.boss_render_w = boss_render_w
        self.boss_x = boss_x

        # Control de fases
        self.fase_laser = "telegraph"  # telegraph → activo → terminado
        self.timer = 0.0
        self.timer_daño = 0.0

        # Altura del láser (desde boca hasta el suelo)
        self.laser_alto = self.LASER_HEIGHT

        print(f"[ATAQUE] AtaqueLaser: telegraph ({self.TELEGRAPH}s) "
              f"→ activo ({self.DURACION}s)")

    def update(self, dt: float, jugadores: list) -> None:
        """
        Actualiza las fases del láser.
        Telegraph → Activo → Terminado.
        """
        self.timer += dt

        if self.fase_laser == "telegraph":
            # Esperar a que termine la fase de telegraph
            if self.timer >= self.TELEGRAPH:
                self.fase_laser = "activo"
                self.timer = 0.0

        elif self.fase_laser == "activo":
            # Contador para daño continuo
            self.timer_daño += dt

            # Verificar si terminó la duración
            if self.timer >= self.DURACION:
                self.fase_laser = "terminado"
                self.terminado = True

        elif self.fase_laser == "terminado":
            self.terminado = True

    def verificar_colision_jugador(self, jugador,
                                    jugador_rect: pygame.Rect) -> None:
        """
        Verifica si el jugador está dentro del área del láser.
        Aplica daño continuamente si está en contacto.

        Args:
            jugador: Objeto jugador
            jugador_rect: pygame.Rect del jugador
        """
        if self.fase_laser != "activo":
            return

        # Crear rect del láser
        laser_rect = pygame.Rect(
            self.boca_x - self.ANCHO_LASER // 2,
            self.boca_y,
            self.ANCHO_LASER,
            self.laser_alto
        )

        # Verificar colisión
        if laser_rect.colliderect(jugador_rect):
            # Aplicar daño cada DAÑO_INTERVALO segundos
            if self.timer_daño >= self.DAÑO_INTERVALO:
                jugador.take_damage(self.DAÑO_POR_INTERVALO)
                self.timer_daño = 0.0

    def render(self, surface: pygame.Surface,
               camera_offset=(0, 0)) -> None:
        """
        Renderiza el láser con sus dos fases visuales:
        - Telegraph: líneas rojas parpadeantes de aviso
        - Activo: láser rojo/blanco con efectos visuales
        """
        cx = int(self.boca_x - camera_offset[0])
        top = int(self.boca_y - camera_offset[1])
        bot = int((self.boca_y + self.laser_alto) - camera_offset[1])

        if self.fase_laser == "telegraph":
            # Fase de aviso: mostrar dónde irá el láser
            progreso = self.timer / self.TELEGRAPH
            alpha = int(40 + 140 * progreso)  # Se vuelve más opaco

            # Superficie para el telegraph
            tell_surf = pygame.Surface(
                (self.ANCHO_LASER, max(1, bot - top)),
                pygame.SRCALPHA
            )
            tell_surf.fill((255, 50, 50, alpha // 3))

            # Líneas de borde rojo del telegraph
            pygame.draw.line(
                tell_surf,
                (255, 50, 50, alpha),
                (0, 0),
                (0, max(1, bot - top)),
                1
            )
            pygame.draw.line(
                tell_surf,
                (255, 50, 50, alpha),
                (self.ANCHO_LASER - 1, 0),
                (self.ANCHO_LASER - 1, max(1, bot - top)),
                1
            )

            # Blittear telegraph
            surface.blit(tell_surf, (cx - self.ANCHO_LASER // 2, top))

            # Triángulo de aviso en la boca del boss
            pygame.draw.polygon(
                surface,
                (255, 200, 0),
                [
                    (cx, top),
                    (cx - 15, top - 20),
                    (cx + 15, top - 20),
                ]
            )

        elif self.fase_laser == "activo":
            # Fase activa: mostrar el láser disparando
            progreso_vida = self.timer / self.DURACION

            # Núcleo del láser (blanco brillante)
            nucleo_w = max(4, int(self.ANCHO_LASER * 0.3))
            nucleo = pygame.Surface(
                (nucleo_w, max(1, bot - top)),
                pygame.SRCALPHA
            )
            nucleo.fill((255, 255, 255, 230))
            surface.blit(nucleo, (cx - nucleo_w // 2, top))

            # Cuerpo del láser (rojo, se desvanece ligeramente)
            cuerpo = pygame.Surface(
                (self.ANCHO_LASER, max(1, bot - top)),
                pygame.SRCALPHA
            )
            alpha_cuerpo = int(180 * (1 - progreso_vida * 0.3))
            cuerpo.fill((255, 40, 40, alpha_cuerpo))
            surface.blit(cuerpo, (cx - self.ANCHO_LASER // 2, top))

            # Bordes brillantes del láser
            pygame.draw.line(
                surface,
                (255, 150, 150),
                (cx - self.ANCHO_LASER // 2, top),
                (cx - self.ANCHO_LASER // 2, bot),
                2
            )
            pygame.draw.line(
                surface,
                (255, 150, 150),
                (cx + self.ANCHO_LASER // 2, top),
                (cx + self.ANCHO_LASER // 2, bot),
                2
            )

            # Partículas de impacto en el suelo
            for _ in range(3):
                px = cx + random.randint(
                    -self.ANCHO_LASER // 2,
                    self.ANCHO_LASER // 2
                )
                pygame.draw.circle(
                    surface,
                    (255, 100, 50),
                    (px, bot),
                    random.randint(2, 5)
                )


# ============================================================================
# ATAQUE 4: PULSO EMP
# ============================================================================

class ProyectilEMP:
    """
    Proyectil especial para EMP que se expande lentamente.
    Representa una bala/pulso de energía que crece en tamaño.
    """
    def __init__(self, cx: float, cy: float, radio_inicial: int = 20):
        self.cx = cx
        self.cy = cy
        self.radio = radio_inicial
        self.radio_max = 600  # muy grande, llena pantalla
        self.velocidad_expansion = 80  # muy lento
        self.activo = True
        self.dañado = set()  # jugadores ya dañados
        self.color = (100, 200, 255)  # azul cian
        self.daño = 1

    def update(self, dt: float):
        if not self.activo:
            return

        self.radio += self.velocidad_expansion * dt

        if self.radio >= self.radio_max:
            self.activo = False

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        if not self.activo:
            return

        cx = int(self.cx - camera_offset[0])
        cy = int(self.cy - camera_offset[1])
        radio = int(self.radio)

        # Limitar el radio de renderizado para evitar crashes de pygame
        # cuando el círculo es muy grande
        if radio > 800:
            return

        try:
            # Bala/pulso expandiéndose
            pygame.draw.circle(surface, self.color, (cx, cy), radio, 4)
            # Anillo interior más brillante
            if radio > 10:
                pygame.draw.circle(surface, (180, 240, 255), (cx, cy), int(radio * 0.7), 2)
        except (pygame.error, OverflowError, ValueError) as e:
            # Silenciar errores de pygame si el círculo es muy grande
            print(f"[EMP] Error renderizando pulso: {e}")

    def verificar_colision(self, jugador) -> bool:
        """Verifica si el jugador toca este pulso."""
        if not hasattr(jugador, 'x') or not hasattr(jugador, 'y'):
            return False

        jid = id(jugador)
        if jid in self.dañado:
            return False

        jcx = jugador.x + getattr(jugador, 'w', 32) // 2
        jcy = jugador.y + getattr(jugador, 'h', 48) // 2

        dist = math.sqrt((jcx - self.cx)**2 + (jcy - self.cy)**2)

        if abs(dist - self.radio) < 30:
            self.dañado.add(jid)
            return True

        return False


class AtaqueEMP(AtaqueBoss):
    """
    Emite 3 pulsos/balas de choque que se expanden lentamente desde el boss.
    Los pulsos dañan al jugador cuando los cruza.
    Incluye telegraph visual con pulso azul de aviso.
    """

    N_ONDAS = 3
    INTERVALO_ONDAS = 0.5  # segundos entre pulsos (más espaciado)
    DAÑO = 1
    TELEGRAPH = 0.6  # segundos de aviso visual

    def __init__(self, boca_x: float, boca_y: float,
                 lista_proyectiles: list):
        """
        Args:
            boca_x: Centro X de expansión (generalmente centro del boss)
            boca_y: Centro Y de expansión (generalmente centro del boss)
            lista_proyectiles: Lista de proyectiles (no se usa, pero por consistencia)
        """
        super().__init__()
        self.cx = boca_x
        self.cy = boca_y
        self.lista_proyectiles = lista_proyectiles

        # Control de pulsos
        self.pulsos_creados = 0
        self.timer_pulso = 0.0
        self.pulsos_activos = []  # lista de ProyectilEMP

        # Fase de telegraph
        self.fase = "telegraph"  # telegraph → activo → terminado
        self.timer_fase = 0.0

        print(f"[ATAQUE] AtaqueEMP: {self.N_ONDAS} pulsos expansivos (con telegraph)")

    def update(self, dt: float, jugadores: list) -> None:
        """
        Actualiza el ataque EMP: telegraph → pulsos expansivos → terminado.
        """
        self.timer_fase += dt

        # Fase de telegraph: mostrar aviso visual
        if self.fase == "telegraph":
            if self.timer_fase >= self.TELEGRAPH:
                self.fase = "activo"
                self.timer_fase = 0.0
            return

        # Fase activa: crear y expandir pulsos
        if self.fase == "activo":
            # Crear nuevos pulsos en intervalos
            if self.pulsos_creados < self.N_ONDAS:
                self.timer_pulso += dt
                if self.timer_pulso >= self.INTERVALO_ONDAS:
                    self.timer_pulso -= self.INTERVALO_ONDAS
                    pulso = ProyectilEMP(self.cx, self.cy)
                    self.pulsos_activos.append(pulso)
                    self.lista_proyectiles.append(pulso)
                    self.pulsos_creados += 1

        # Actualizar pulsos existentes
        for pulso in self.pulsos_activos:
            pulso.update(dt)

            # Verificar colisión con jugadores
            for jugador in jugadores:
                if pulso.verificar_colision(jugador):
                    jugador.take_damage(self.DAÑO)

        # Limpiar pulsos inactivos (no modificar self.lista_proyectiles,
        # ya que el boss es responsable de limpiarla)
        self.pulsos_activos = [p for p in self.pulsos_activos if p.activo]

        # Terminar cuando todos los pulsos se disiparon
        if (self.pulsos_creados >= self.N_ONDAS and
                not self.pulsos_activos):
            self.terminado = True

    def render(self, surface: pygame.Surface,
               camera_offset=(0, 0)) -> None:
        """
        Renderiza telegraph visual (pulso azul de aviso).
        Los pulsos activos se renderizan solos a través de ProyectilEMP.render().
        """
        cx = int(self.cx - camera_offset[0])
        cy = int(self.cy - camera_offset[1])

        # Renderizar telegraph visual (pulso azul de aviso)
        if self.fase == "telegraph":
            progreso = self.timer_fase / self.TELEGRAPH
            alpha = int(150 * (1 - progreso))  # Se desvanece
            radio_pulso = int(50 * progreso)  # Crece desde pequeño

            # Pulso azul expandiéndose
            pulso_surf = pygame.Surface(
                (radio_pulso * 2 + 100, radio_pulso * 2 + 100),
                pygame.SRCALPHA
            )
            pulso_centro = (radio_pulso + 50, radio_pulso + 50)

            # Anillo azul pulsante
            pygame.draw.circle(
                pulso_surf,
                (100, 200, 255, alpha),
                pulso_centro,
                radio_pulso + 30,
                3
            )

            # Anillo interno más brillante
            pygame.draw.circle(
                pulso_surf,
                (150, 220, 255, alpha),
                pulso_centro,
                radio_pulso + 15,
                2
            )

            # Blittear el pulso
            surface.blit(
                pulso_surf,
                (cx - radio_pulso - 50, cy - radio_pulso - 50)
            )
