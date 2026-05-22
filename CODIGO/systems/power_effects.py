"""
systems/power_effects.py
========================
Gestor de efectos visuales para poderes del Profesor Ibarra.
Similar a DeathEffectManager pero para EMP, Invulnerabilidad y Cura.

Usa pygame puro — sin assets externos.
"""

import pygame
import math
import random


class EfectoEMP:
    """
    Onda expansiva circular que se expande desde el centro del jugador.
    Color: azul eléctrico cian.
    Duración: ~0.8 segundos.
    """

    COLOR_PRINCIPAL = (0, 200, 255)      # cian eléctrico
    COLOR_SECUNDARIO = (100, 100, 255)   # azul eléctrico
    COLOR_BORDE = (200, 240, 255)        # blanco azulado

    VELOCIDAD_EXPANSION = 600   # px/segundo
    RADIO_MAXIMO = 400          # px — hasta dónde llega la onda
    GROSOR_ONDA = 4             # px de grosor del anillo
    NUM_CHISPAS = 20            # fragmentos de electricidad

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radio = 0.0
        self.terminado = False
        self.timer = 0.0
        self.duracion = self.RADIO_MAXIMO / self.VELOCIDAD_EXPANSION

        # Generar chispas estáticas
        self.chispas = [self._crear_chispa() for _ in range(self.NUM_CHISPAS)]

        # Segunda onda más pequeña con delay
        self.radio_2 = -50.0  # empieza detrás
        self.alpha_2 = 200

    def _crear_chispa(self) -> dict:
        """Crea una chispa de electricidad en posición aleatoria."""
        angulo = random.uniform(0, math.pi * 2)
        distancia = random.uniform(30, self.RADIO_MAXIMO * 0.8)
        return {
            "angulo": angulo,
            "distancia": distancia,
            "largo": random.randint(8, 25),
            "alpha": 255,
            "delay": random.uniform(0, 0.3),
            "activa": False,
        }

    def update(self, dt: float):
        """Actualiza expansión de onda y devanecimiento de chispas."""
        self.timer += dt

        # Expandir onda principal
        self.radio += self.VELOCIDAD_EXPANSION * dt

        # Expandir segunda onda (ligeramente más lenta)
        self.radio_2 += self.VELOCIDAD_EXPANSION * 0.7 * dt

        # Desvanecer chispas
        for chispa in self.chispas:
            if self.timer >= chispa["delay"]:
                chispa["activa"] = True
                fade = 1.0 - (self.timer / self.duracion)
                chispa["alpha"] = int(255 * max(0, fade))

        if self.radio >= self.RADIO_MAXIMO:
            self.terminado = True

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        """Renderiza onda expansiva cian + chispas eléctricas."""
        cx = int(self.x - camera_offset[0])
        cy = int(self.y - camera_offset[1])

        progreso = self.radio / self.RADIO_MAXIMO
        alpha = int(255 * (1.0 - progreso))

        # Onda principal
        if self.radio > 0 and alpha > 10:
            radio_int = int(self.radio)
            onda_surf = pygame.Surface(
                (radio_int * 2 + 20, radio_int * 2 + 20), pygame.SRCALPHA
            )
            centro = (radio_int + 10, radio_int + 10)

            # Anillo exterior blanco azulado
            pygame.draw.circle(
                onda_surf,
                (*self.COLOR_BORDE, min(255, alpha + 50)),
                centro,
                radio_int,
                self.GROSOR_ONDA + 2,
            )

            # Anillo principal cian
            pygame.draw.circle(onda_surf, (*self.COLOR_PRINCIPAL, alpha), centro, radio_int, self.GROSOR_ONDA)

            # Anillo interior más tenue
            if radio_int > 10:
                pygame.draw.circle(
                    onda_surf, (*self.COLOR_SECUNDARIO, alpha // 2), centro, radio_int - 8, 2
                )

            surface.blit(onda_surf, (cx - radio_int - 10, cy - radio_int - 10))

        # Segunda onda
        if self.radio_2 > 0:
            r2 = int(self.radio_2)
            a2 = int(self.alpha_2 * (1.0 - self.radio_2 / self.RADIO_MAXIMO))
            if r2 > 0 and a2 > 10:
                s2 = pygame.Surface((r2 * 2 + 10, r2 * 2 + 10), pygame.SRCALPHA)
                pygame.draw.circle(s2, (*self.COLOR_SECUNDARIO, a2), (r2 + 5, r2 + 5), r2, 2)
                surface.blit(s2, (cx - r2 - 5, cy - r2 - 5))

        # Chispas de electricidad
        for chispa in self.chispas:
            if not chispa["activa"] or chispa["alpha"] <= 0:
                continue
            angulo = chispa["angulo"]
            dist = chispa["distancia"]
            px = cx + int(math.cos(angulo) * dist)
            py = cy + int(math.sin(angulo) * dist)
            px2 = px + int(math.cos(angulo + 0.3) * chispa["largo"])
            py2 = py + int(math.sin(angulo + 0.3) * chispa["largo"])

            pygame.draw.line(surface, (0, 200, 255, chispa["alpha"]), (px, py), (px2, py2), 2)


class EfectoInvulnerabilidad:
    """
    Aura pulsante dorada que rodea al jugador mientras
    está protegido. Emite destellos de luz. Flash al recibir impacto.
    Color: dorado (#FFD700).
    Duración: 5 segundos (sincronizada con invulnerable_timer).
    """

    COLOR_AURA = (255, 215, 0)        # dorado
    COLOR_DESTELLO = (255, 255, 180)  # blanco dorado
    COLOR_INTERIOR = (255, 180, 0)    # naranja dorado

    RADIO_BASE = 32       # px — radio del aura alrededor del jugador
    PULSO_VELOCIDAD = 3.0  # Hz — veces que pulsa por segundo
    NUM_DESTELLOS = 6      # rayos de luz emanando

    def __init__(self, jugador):
        self.jugador = jugador  # referencia al jugador
        self.terminado = False
        self.timer = 0.0
        self.duracion = 5.0  # debe coincidir con duración del poder
        self.flash_timer = 0.0  # para flash al recibir daño
        self.terminando = False
        self.timer_fin = 0.0
        self.particulas_fin = []

    def flash_impacto(self):
        """Llamar cuando el jugador recibe daño ignorado por invulnerabilidad."""
        self.flash_timer = 0.2

    def terminar(self):
        """Llamar cuando el poder termina para crear explosión."""
        self.terminando = True
        self.timer_fin = 0.0
        self.particulas_fin = [
            {
                "angulo": random.uniform(0, math.pi * 2),
                "velocidad": random.uniform(80, 200),
                "alpha": 255,
                "size": random.randint(3, 8),
            }
            for _ in range(16)
        ]

    def update(self, dt: float):
        """Actualiza el pulso del aura y sincroniza con invulnerable_timer."""
        self.timer += dt
        if self.flash_timer > 0:
            self.flash_timer -= dt

        # Sincronizar con duración real del poder
        if hasattr(self.jugador, "invulnerable_timer"):
            if self.jugador.invulnerable_timer <= 0:
                self.terminar()

        if self.terminando:
            self.timer_fin += dt
            for p in self.particulas_fin:
                p["alpha"] -= 400 * dt
            if self.timer_fin > 0.5:
                self.terminado = True

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        """Renderiza aura pulsante + destellos + explosión final."""
        cx = int(self.jugador.x - camera_offset[0] + self.jugador.w // 2)
        cy = int(self.jugador.y - camera_offset[1] + self.jugador.h // 2)

        # Si está terminando, mostrar explosión
        if self.terminando:
            self._render_explosion_final(surface, cx, cy)
            return

        # Pulso senoidal
        pulso = math.sin(self.timer * self.PULSO_VELOCIDAD * math.pi * 2)
        radio = self.RADIO_BASE + pulso * 6

        # Factor de flash al recibir impacto
        flash = min(1.0, self.flash_timer / 0.2)
        alpha = int(180 + flash * 75)
        color_a = tuple(min(255, int(c + flash * (255 - c))) for c in self.COLOR_AURA)

        # Aura exterior
        aura_size = int(radio * 2 + 20)
        aura_surf = pygame.Surface((aura_size, aura_size), pygame.SRCALPHA)
        centro = (aura_size // 2, aura_size // 2)

        pygame.draw.circle(aura_surf, (*color_a, alpha), centro, int(radio), 3)
        pygame.draw.circle(aura_surf, (*self.COLOR_INTERIOR, alpha // 2), centro, int(radio - 6), 2)
        pygame.draw.circle(aura_surf, (*self.COLOR_DESTELLO, alpha // 3), centro, int(radio + 6), 1)

        surface.blit(aura_surf, (cx - aura_size // 2, cy - aura_size // 2))

        # Destellos radiales (rayos de luz)
        for i in range(self.NUM_DESTELLOS):
            angulo_base = (i / self.NUM_DESTELLOS) * math.pi * 2
            angulo = angulo_base + self.timer * 1.5
            dist_ini = radio + 2
            dist_fin = radio + 10 + pulso * 5

            x1 = cx + int(math.cos(angulo) * dist_ini)
            y1 = cy + int(math.sin(angulo) * dist_ini)
            x2 = cx + int(math.cos(angulo) * dist_fin)
            y2 = cy + int(math.sin(angulo) * dist_fin)

            pygame.draw.line(surface, (*self.COLOR_DESTELLO, alpha), (x1, y1), (x2, y2), 2)

    def _render_explosion_final(self, surface, cx, cy):
        """Explosión de partículas doradas al terminar."""
        for p in self.particulas_fin:
            if p["alpha"] <= 0:
                continue
            dist = self.timer_fin * p["velocidad"]
            px = cx + int(math.cos(p["angulo"]) * dist)
            py = cy + int(math.sin(p["angulo"]) * dist)
            alpha = max(0, int(p["alpha"]))
            pygame.draw.rect(surface, (*self.COLOR_AURA, alpha), (px, py, p["size"], p["size"]))


class EfectoCura:
    """
    Partículas ascendentes de colores verdes/rosas + flash verde + número flotante.
    Color: verde esmeralda (#00FF88) con rosa (#FF88AA).
    Duración: ~1.2 segundos.
    """

    COLOR_VERDE = (0, 220, 120)      # verde esmeralda
    COLOR_ROSA = (255, 140, 180)     # rosa suave
    COLOR_BLANCO = (220, 255, 220)   # verde muy claro

    NUM_PARTICULAS = 12
    FLASH_DURACION = 0.15  # segundos del flash verde

    def __init__(self, x: float, y: float, cantidad_curada: int = 2):
        self.x = x
        self.y = y
        self.terminado = False
        self.timer = 0.0
        self.flash_timer = self.FLASH_DURACION
        self.cantidad = cantidad_curada
        self.numero_y = float(y)
        self.numero_alpha = 255

        # Partículas ascendentes
        self.particulas = [
            {
                "x": x + random.uniform(-20, 20),
                "y": y + random.uniform(-10, 10),
                "vy": random.uniform(-80, -160),  # sube
                "vx": random.uniform(-30, 30),
                "alpha": 255,
                "size": random.randint(4, 10),
                "color": random.choice([self.COLOR_VERDE, self.COLOR_ROSA, self.COLOR_BLANCO]),
                "forma": random.choice(["rombo", "cruz"]),
                "delay": random.uniform(0, 0.2),
            }
            for _ in range(self.NUM_PARTICULAS)
        ]

    def update(self, dt: float):
        """Actualiza partículas y número flotante."""
        self.timer += dt
        self.flash_timer -= dt

        # Mover número flotante hacia arriba
        self.numero_y -= 60 * dt
        self.numero_alpha = max(0, int(255 * (1.0 - self.timer / 1.2)))

        # Actualizar partículas
        vivas = 0
        for p in self.particulas:
            if self.timer < p["delay"]:
                vivas += 1
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] *= 1 - dt * 1.5  # desacelerar
            p["alpha"] -= 200 * dt
            if p["alpha"] > 0:
                vivas += 1

        if vivas == 0 and self.numero_alpha <= 0:
            self.terminado = True

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        """Renderiza flash, partículas y número flotante."""
        ox, oy = camera_offset

        # Flash verde sobre el jugador
        if self.flash_timer > 0:
            progreso = self.flash_timer / self.FLASH_DURACION
            alpha = int(120 * progreso)
            flash_surf = pygame.Surface((40, 60), pygame.SRCALPHA)
            flash_surf.fill((*self.COLOR_VERDE, alpha))
            surface.blit(flash_surf, (int(self.x - ox - 20), int(self.y - oy - 30)))

        # Partículas
        for p in self.particulas:
            if self.timer < p["delay"] or p["alpha"] <= 0:
                continue
            px = int(p["x"] - ox)
            py = int(p["y"] - oy)
            alpha = max(0, int(p["alpha"]))
            color = (*p["color"], alpha)
            size = p["size"]

            part_surf = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
            centro = (size + 1, size + 1)

            if p["forma"] == "rombo":
                puntos = [
                    (centro[0], centro[1] - size),
                    (centro[0] + size, centro[1]),
                    (centro[0], centro[1] + size),
                    (centro[0] - size, centro[1]),
                ]
                pygame.draw.polygon(part_surf, color, puntos)
            else:  # cruz
                pygame.draw.rect(part_surf, color, (centro[0] - 1, centro[1] - size, 2, size * 2))
                pygame.draw.rect(part_surf, color, (centro[0] - size, centro[1] - 1, size * 2, 2))

            surface.blit(part_surf, (px - size - 1, py - size - 1))

        # Número flotante "+2"
        if self.numero_alpha > 20:
            try:
                font = pygame.font.SysFont("monospace", 22, bold=True)
                texto = f"+{self.cantidad}"

                # Sombra
                sombra = font.render(texto, False, (0, 80, 40))
                sombra.set_alpha(self.numero_alpha // 2)
                surface.blit(sombra, (int(self.x - ox) + 1, int(self.numero_y - oy) + 1))

                # Texto principal
                txt = font.render(texto, False, self.COLOR_VERDE)
                txt.set_alpha(self.numero_alpha)
                surface.blit(txt, (int(self.x - ox), int(self.numero_y - oy)))
            except Exception:
                pass


class PowerEffectManager:
    """
    Gestor central de efectos visuales de poderes.
    Similar a DeathEffectManager pero para poderes activos.
    """

    def __init__(self):
        self.efectos_activos = []

    def spawn_emp(self, x: float, y: float):
        """Disparar efecto EMP desde la posición dada."""
        self.efectos_activos.append(EfectoEMP(x, y))

    def spawn_invulnerabilidad(self, jugador):
        """Iniciar efecto de aura de invulnerabilidad."""
        self.efectos_activos.append(EfectoInvulnerabilidad(jugador))

    def spawn_cura(self, x: float, y: float, cantidad_curada: int = 2):
        """Disparar efecto de cura en la posición dada."""
        self.efectos_activos.append(EfectoCura(x, y, cantidad_curada))

    def update(self, dt: float):
        """Actualiza todos los efectos activos."""
        for e in self.efectos_activos:
            e.update(dt)
        self.efectos_activos = [e for e in self.efectos_activos if not e.terminado]

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)):
        """Renderiza todos los efectos activos."""
        for e in self.efectos_activos:
            e.render(surface, camera_offset)

    def limpiar(self):
        """Limpia todos los efectos (al cambiar sala o reiniciar)."""
        self.efectos_activos.clear()


# Instancia global
power_effect_manager = PowerEffectManager()
