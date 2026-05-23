"""
ui/versus_screen.py
===================
Pantalla de versus estilo Binding of Isaac.
Aparece después del minijuego y antes del boss.

Layout:
┌─────────────────────────────────────────────┐
│   P1  P2  VS  ECO    ← texto arriba         │
│                                             │
│  [P1]→      ←[BOSS]                        │
│  [P2]→                                      │
│         (centro vacío)                      │
└─────────────────────────────────────────────┘

Los jugadores se mueven MUY lentamente hacia
el centro sin llegar nunca. El boss está fijo
a la derecha.
"""
from __future__ import annotations

import pygame
import math
from pathlib import Path


class PantallaVersus:
    """
    Pantalla de versus estilo Binding of Isaac.
    Aparece después del minijuego y antes del boss.
    """

    # Duración total de la pantalla
    DURACION = 5.0  # segundos

    # Velocidad de acercamiento de los jugadores
    VELOCIDAD_JUGADOR = 10.0  # px/segundo

    # Velocidad del boss
    VELOCIDAD_BOSS = 10.0  # px/segundo - igual que jugador 1

    # Límite de avance: los jugadores no pasan del centro - este margen
    MARGEN_CENTRO = 150  # px desde el centro — mucho menos avance

    # Tamaño del retrato del boss
    BOSS_W = 280
    BOSS_H = 280

    # Tamaño de los sprites idle de jugadores
    JUGADOR_SIZE = 150  # px escalados para el versus — más grande

    # Colores del texto
    COLOR_P1 = (220, 100, 100)  # rojo
    COLOR_P2 = (100, 160, 220)  # azul
    COLOR_VS = (255, 220, 50)  # dorado
    COLOR_ECO = (180, 80, 200)  # morado

    def __init__(
        self,
        logical_w: int,
        logical_h: int,
        hay_p2: bool,
        anim_p1,  # Animation de P1
        anim_p2=None,  # Animation de P2 (None si no hay)
    ) -> None:
        self.lw = logical_w
        self.lh = logical_h
        self.hay_p2 = hay_p2
        self.anim_p1 = anim_p1
        self.anim_p2 = anim_p2 if hay_p2 else None

        self.terminado = False
        self.timer = 0.0

        # Posición inicial de los jugadores (lado izquierdo)
        self.cx = logical_w // 2
        self.cy = logical_h // 2

        # P1 empieza en el cuarto izquierdo de la pantalla
        self.p1_x = float(logical_w * 0.15)
        self.p2_x = float(logical_w * 0.15)

        # Y de los jugadores — centrados verticalmente
        # Si hay P2, P1 arriba y P2 abajo ligeramente
        if hay_p2:
            self.p1_y = float(self.cy - self.JUGADOR_SIZE // 2 - 20)
            self.p2_y = float(self.cy + 20)
        else:
            self.p1_y = float(self.cy - self.JUGADOR_SIZE // 2)
            self.p2_y = self.p1_y

        # Límite de avance: no pasar del centro - margen
        self.limite_x = float(self.cx - self.MARGEN_CENTRO)

        # Cargar assets
        self.fondo = None
        self.boss_portrait = None
        self._cargar_assets()
        self._cargar_fuentes()

        # Posición del boss (lado derecho)
        self.boss_x = float(logical_w * 0.85 - 150)  # 100px más a la izquierda
        self.boss_y = self.cy - self.BOSS_H // 2

        # Efectos de entrada
        self.alpha_general = 0.0  # fade in
        self.FADE_IN_TIEMPO = 0.4  # segundos

        # Timer de animación idle
        self.timer_anim = 0.0

    def _cargar_assets(self) -> None:
        """Carga fondo y retrato del boss."""
        # Obtener ruta base correcta
        base_dir = Path(__file__).parent.parent.resolve()
        assets_dir = base_dir / "assets" / "ui"

        # Fondo
        self.fondo = None  # Por ahora sin fondo de imagen

        # Retrato del boss
        try:
            boss_path = assets_dir / "boss_versus.png"
            if boss_path.exists():
                img_boss = pygame.image.load(str(boss_path)).convert_alpha()
                # Escalar al tamaño definido
                self.boss_portrait = pygame.transform.scale(img_boss, (self.BOSS_W, self.BOSS_H))
            else:
                self.boss_portrait = None
        except Exception as e:
            print(f"[VERSUS] Error cargando boss_versus.png: {e}")
            self.boss_portrait = None

    def _cargar_fuentes(self) -> None:
        """Carga fuentes para el texto del versus."""
        try:
            base_path = Path(__file__).parent.parent.resolve()
            ui_path = base_path / "assets" / "ui"

            def _cargar_fuente(filename: str, size: int) -> pygame.font.Font:
                font_path = ui_path / filename
                if font_path.exists():
                    try:
                        return pygame.font.Font(str(font_path), size)
                    except Exception:
                        pass
                return pygame.font.SysFont("monospace", size, bold=True)

            self.font_vs = _cargar_fuente("VT323-Regular.ttf", 42)
            self.font_nombre = _cargar_fuente("VT323-Regular.ttf", 28)
            self.font_small = _cargar_fuente("VT323-Regular.ttf", 14)
        except Exception:
            f = pygame.font.Font(None, 36)
            self.font_vs = f
            self.font_nombre = f
            self.font_small = f

    def update(self, dt: float) -> None:
        """Actualiza estado, animaciones y posiciones."""
        self.timer += dt
        self.timer_anim += dt

        # Actualizar animaciones idle
        if self.anim_p1:
            self.anim_p1.update(dt)
        if self.anim_p2:
            self.anim_p2.update(dt)

        # Fade in
        if self.timer < self.FADE_IN_TIEMPO:
            self.alpha_general = (self.timer / self.FADE_IN_TIEMPO) * 255
        else:
            self.alpha_general = 255.0

        # Mover jugadores y boss lentamente hacia el centro
        limite_p1 = self.limite_x
        limite_boss = float(self.cx + self.MARGEN_CENTRO)

        # P1 se mueve desde la izquierda hacia el centro
        if self.p1_x < limite_p1:
            self.p1_x += self.VELOCIDAD_JUGADOR * dt
            self.p1_x = min(self.p1_x, limite_p1)

        # P2 se mueve desde la izquierda hacia el centro
        if self.hay_p2 and self.p2_x < limite_p1:
            self.p2_x += self.VELOCIDAD_JUGADOR * dt
            self.p2_x = min(self.p2_x, limite_p1)

        # Boss se mueve desde la derecha hacia el centro
        boss_limite_izq = float(self.cx + self.MARGEN_CENTRO)
        if self.boss_x > boss_limite_izq:
            self.boss_x -= self.VELOCIDAD_BOSS * dt
            self.boss_x = max(self.boss_x, boss_limite_izq)

        # Terminar después de la duración
        if self.timer >= self.DURACION:
            self.terminado = True

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Permite saltar la pantalla con ENTER o ESPACIO.
        """
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.terminado = True

        if event.type == pygame.MOUSEBUTTONDOWN:
            self.terminado = True

    def render(self, surface: pygame.Surface) -> None:
        """Renderiza la pantalla completa de versus."""
        alpha = int(self.alpha_general)

        # Crear superficie temporal para el fade in
        if alpha < 255:
            temp = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
            self._render_contenido(temp)
            temp.set_alpha(alpha)
            surface.blit(temp, (0, 0))
        else:
            self._render_contenido(surface)

    def _render_contenido(self, surface: pygame.Surface) -> None:
        """Renderiza todo el contenido de la pantalla."""
        # 1. Fondo
        if self.fondo:
            surface.blit(self.fondo, (0, 0))
        else:
            surface.fill((4, 2, 8))

        # 2. Línea divisoria central sutil
        self._render_linea_central(surface)

        # 3. Retrato del boss (derecha, fijo)
        self._render_boss(surface)

        # 4. Jugadores (izquierda, moviéndose)
        self._render_jugadores(surface)

        # 5. Texto del versus (arriba)
        self._render_texto_versus(surface)

        # 6. Hint para saltar
        self._render_hint(surface)

    def _render_linea_central(self, surface: pygame.Surface) -> None:
        """Línea vertical sutil en el centro (DESACTIVADA)."""
        # Línea divisoria removida
        pass

    def _render_boss(self, surface: pygame.Surface) -> None:
        """Renderiza el retrato del boss a la derecha."""
        if not self.boss_portrait:
            # Placeholder si falta el PNG
            pygame.draw.rect(
                surface,
                (40, 0, 0),
                (int(self.boss_x), int(self.boss_y), self.BOSS_W, self.BOSS_H),
            )
            txt = self.font_small.render("BOSS", False, (150, 50, 50))
            surface.blit(
                txt,
                (
                    int(self.boss_x) + self.BOSS_W // 2 - txt.get_width() // 2,
                    int(self.boss_y) + self.BOSS_H // 2 - txt.get_height() // 2,
                ),
            )
            return

        # Pulso sutil de escala del boss
        pulso = math.sin(self.timer_anim * 1.5) * 3
        w_boss = self.BOSS_W + int(pulso)
        h_boss = self.BOSS_H + int(pulso)

        if pulso != 0:
            boss_scaled = pygame.transform.scale(self.boss_portrait, (w_boss, h_boss))
        else:
            boss_scaled = self.boss_portrait

        bx = int(self.boss_x - (w_boss - self.BOSS_W) // 2)
        by = int(self.boss_y - (h_boss - self.BOSS_H) // 2)
        surface.blit(boss_scaled, (bx, by))

        # Nombre del boss debajo del retrato
        txt_eco = self.font_nombre.render("El Echo", False, self.COLOR_ECO)
        sombra_eco = self.font_nombre.render("El Echo", False, (40, 0, 60))
        eco_x = int(self.boss_x) + self.BOSS_W // 2 - txt_eco.get_width() // 2
        eco_y = int(self.boss_y) + self.BOSS_H + 10
        surface.blit(sombra_eco, (eco_x + 2, eco_y + 2))
        surface.blit(txt_eco, (eco_x, eco_y))

    def _render_jugadores(self, surface: pygame.Surface) -> None:
        """
        Renderiza P1 (y P2 si existe) mirando hacia
        la derecha, moviéndose lentamente al centro.
        """
        # P1
        self._render_sprite_jugador(
            surface,
            self.anim_p1,
            int(self.p1_x),
            int(self.p1_y),
            flip=False,  # mira a la derecha
            es_p2=False,
        )

        # P2 si existe
        if self.hay_p2:
            self._render_sprite_jugador(
                surface,
                self.anim_p2,
                int(self.p2_x),
                int(self.p2_y),
                flip=False,  # también mira a la derecha
                es_p2=True,
            )

    def _render_sprite_jugador(
        self,
        surface: pygame.Surface,
        anim,
        x: int,
        y: int,
        flip: bool,
        es_p2: bool,
    ) -> None:
        """Renderiza un sprite idle de jugador."""
        if anim is None:
            # Placeholder cubo negro para P2 sin sprites
            color = (30, 30, 50) if es_p2 else (50, 30, 30)
            pygame.draw.rect(surface, color, (x, y, self.JUGADOR_SIZE, self.JUGADOR_SIZE))
            pygame.draw.rect(
                surface,
                (60, 50, 80) if es_p2 else (80, 50, 60),
                (x, y, self.JUGADOR_SIZE, self.JUGADOR_SIZE),
                2,
            )
            lbl = self.font_small.render(
                "P2" if es_p2 else "P1",
                False,
                (100, 120, 180) if es_p2 else (180, 120, 100),
            )
            surface.blit(
                lbl,
                (
                    x + self.JUGADOR_SIZE // 2 - lbl.get_width() // 2,
                    y + self.JUGADOR_SIZE // 2 - lbl.get_height() // 2,
                ),
            )
            return

        # Obtener frame actual del Animator
        try:
            frame = anim.current_frame()
        except Exception:
            frame = None

        if frame is None:
            return

        # Escalar al tamaño del versus
        frame_scaled = pygame.transform.scale(frame, (self.JUGADOR_SIZE, self.JUGADOR_SIZE))

        # flip=False → mira a la derecha (hacia el boss)
        # Si el sprite por defecto mira a la izquierda,
        # hacer flip aquí. Verificar y ajustar.
        if flip:
            frame_scaled = pygame.transform.flip(frame_scaled, True, False)

        surface.blit(frame_scaled, (x, y))

        # Nombre del jugador encima del sprite
        nombre = "JUGADOR 2" if es_p2 else "JUGADOR 1"
        color = self.COLOR_P2 if es_p2 else self.COLOR_P1
        txt = self.font_small.render(nombre, False, color)
        surface.blit(
            txt,
            (
                x + self.JUGADOR_SIZE // 2 - txt.get_width() // 2,
                y - 20,
            ),
        )

    def _render_texto_versus(self, surface: pygame.Surface) -> None:
        """
        Renderiza el texto en la parte superior:
        "P1  ECO"  o  "P1  P2  ECO"
        """
        TEXTO_Y = 60  # Más abajo
        cx = self.lw // 2

        if self.hay_p2:
            partes = [
                ("JUGADOR 1", self.COLOR_P1),
                ("  ", (255, 255, 255)),
                ("JUGADOR 2", self.COLOR_P2),
                ("  VS  ", self.COLOR_VS),
                ("El Echo", self.COLOR_ECO),
            ]
        else:
            partes = [
                ("JUGADOR 1", self.COLOR_P1),
                ("  VS  ", self.COLOR_VS),
                ("El Echo", self.COLOR_ECO),
            ]

        # Usar fuente más grande
        font_grande = pygame.font.SysFont("monospace", 48, bold=True)

        # Calcular ancho total para centrar
        ancho_total = sum(font_grande.size(txt)[0] for txt, _ in partes)

        x_actual = cx - ancho_total // 2

        for texto, color in partes:
            # Sombra
            sombra = font_grande.render(texto, False, (0, 0, 0))
            surface.blit(sombra, (x_actual + 2, TEXTO_Y + 2))

            # Texto principal
            txt_surf = font_grande.render(texto, False, color)
            surface.blit(txt_surf, (x_actual, TEXTO_Y))
            x_actual += txt_surf.get_width()

        # Sin línea decorativa

    def _render_hint(self, surface: pygame.Surface) -> None:
        """Hint para saltar la pantalla."""
        # Solo mostrar después de 1 segundo
        if self.timer < 1.0:
            return

        alpha_hint = min(255, int(((self.timer - 1.0) / 0.5) * 255))

        txt = self.font_small.render(
            "[ ENTER / CLICK ] para continuar", False, (60, 50, 80)
        )
        txt.set_alpha(alpha_hint)
        surface.blit(
            txt,
            (
                self.lw // 2 - txt.get_width() // 2,
                self.lh - 30,
            ),
        )


__all__ = ["PantallaVersus"]
