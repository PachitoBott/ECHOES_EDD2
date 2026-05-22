"""
Minijuego Papers Please estilo - Clasificación de publicaciones sobre ciberacoso.
El jugador debe clasificar 5 publicaciones correctamente para entrar al boss.
"""

from __future__ import annotations

import random
from typing import Optional

import pygame


# ============================================================================
# PALETA DE COLORES DEL MINIJUEGO
# ============================================================================

# Fondo general
COLOR_BG_OUTER = (4, 2, 8)  # casi negro morado
COLOR_BG_INNER = (8, 4, 12)  # fondo del area central

# Tarjeta principal
COLOR_CARD_BG = (12, 8, 18)  # fondo tarjeta
COLOR_CARD_BORDER = (45, 20, 70)  # borde morado oscuro
COLOR_CARD_HEADER = (18, 10, 25)  # header más oscuro
COLOR_CARD_FOOTER = (15, 8, 22)  # footer stats

# Glitch/corrupciones
COLOR_GLITCH_RED = (180, 0, 0)  # rojo corrupto
COLOR_GLITCH_PURPLE = (120, 0, 180)  # morado corrupto
COLOR_STATIC = (30, 15, 45)  # estática de fondo

# Avatar
COLOR_AVATAR_BG = (25, 10, 40)  # fondo avatar
COLOR_AVATAR_BORDER = (80, 30, 120)  # borde avatar

# Texto
COLOR_USERNAME = (200, 160, 255)  # morado claro
COLOR_TIMESTAMP = (80, 60, 100)  # gris morado
COLOR_POST_TEXT = (230, 220, 240)  # casi blanco
COLOR_STATS = (100, 80, 130)  # stats apagados

# Botones
COLOR_BTN_REPORT_BG = (120, 0, 0)  # rojo oscuro
COLOR_BTN_REPORT_HOVER = (200, 0, 0)  # rojo brillante
COLOR_BTN_REPORT_BORDER = (255, 40, 40)  # borde rojo
COLOR_BTN_IGNORE_BG = (25, 20, 35)  # gris morado
COLOR_BTN_IGNORE_HOVER = (45, 35, 60)  # gris morado claro
COLOR_BTN_IGNORE_BORDER = (80, 60, 100)  # borde gris

# Feedback
COLOR_CORRECT_TINT = (0, 150, 50)
COLOR_INCORRECT_TINT = (180, 0, 0)
COLOR_FEEDBACK_GOOD = (0, 220, 80)  # verde feedback
COLOR_FEEDBACK_BAD = (255, 60, 60)  # rojo feedback


# ============================================================================
# DATOS DE PUBLICACIONES
# ============================================================================

PUBLICACIONES = [
    {
        "id": 1,
        "seed": 42,
        "es_acoso": True,
        "texto": (
            "jajaja vieron lo que hizo?? "
            "qué asco de persona, merece "
            "todo lo que le pasa lol"
        ),
        "accion_correcta": "REPORTAR",
        "feedback_correcto": (
            "Correcto. Burlarse y desear daño "
            "a alguien es acoso directo."
        ),
        "feedback_incorrecto": (
            "Incorrecto. Esto es acoso directo. "
            "Reportar protege a la víctima."
        ),
        "nivel_actividad": 0.85,
    },
    {
        "id": 2,
        "seed": 77,
        "es_acoso": False,
        "texto": (
            "esto no es verdad, conozco a "
            "esta persona y nunca haría eso. "
            "por favor dejen de compartir."
        ),
        "accion_correcta": "IGNORAR",
        "feedback_correcto": (
            "Correcto. Este mensaje defiende "
            "a la víctima. No es acoso."
        ),
        "feedback_incorrecto": (
            "Incorrecto. Este mensaje es de apoyo. "
            "Reportarlo silenciaría a un aliado."
        ),
        "nivel_actividad": 0.25,
    },
    {
        "id": 3,
        "seed": 13,
        "es_acoso": True,
        "texto": (
            "no sé si creerle pero bueno... "
            "yo solo lo comparto por si acaso, "
            "cada quien que opine lo que quiera"
        ),
        "accion_correcta": "REPORTAR",
        "feedback_correcto": (
            "Correcto. Compartir rumores "
            "sin verificar es acoso pasivo."
        ),
        "feedback_incorrecto": (
            "Incorrecto. Difundir rumores "
            "amplifica el daño aunque 'no opines'."
        ),
        "nivel_actividad": 0.60,
    },
    {
        "id": 4,
        "seed": 99,
        "es_acoso": True,
        "texto": (
            "claro que sí, 'accidentalmente' "
            "le tomaron la foto jajaja todo "
            "fue un accidente obvio 🙄🙄"
        ),
        "accion_correcta": "REPORTAR",
        "feedback_correcto": (
            "Correcto. El sarcasmo hostil "
            "y la burla también son acoso."
        ),
        "feedback_incorrecto": (
            "Incorrecto. Aunque no insulte "
            "directamente, el sarcasmo hostil "
            "es acoso encubierto."
        ),
        "nivel_actividad": 0.72,
    },
    {
        "id": 5,
        "seed": 55,
        "es_acoso": True,
        "texto": (
            "yo no opino ni me meto "
            "pero la verdad el video "
            "está ahí y habla solo. "
            "no digo más 👀"
        ),
        "accion_correcta": "REPORTAR",
        "feedback_correcto": (
            "Correcto. Insinuar sin decir "
            "directamente también hace daño."
        ),
        "feedback_incorrecto": (
            "Incorrecto. El silencio cómplice "
            "con insinuación es acoso pasivo. "
            "Los 👀 no son neutrales."
        ),
        "nivel_actividad": 0.55,
    },
]


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================


def dibujar_avatar(surface: pygame.Surface, x: int, y: int, size: int, seed: int) -> None:
    """
    Genera un avatar único basado en seed.
    Silueta pixelada con corrupción digital.
    """
    # Fondo del avatar
    pygame.draw.rect(surface, COLOR_AVATAR_BG, (x, y, size, size))
    pygame.draw.rect(surface, COLOR_AVATAR_BORDER, (x, y, size, size), 1)

    # Silueta de cabeza (círculo simple)
    cx = x + size // 2
    cy = y + size // 3
    radio_cabeza = size // 5
    pygame.draw.circle(surface, COLOR_GLITCH_PURPLE, (cx, cy), radio_cabeza)

    # Silueta de cuerpo
    pygame.draw.rect(
        surface,
        COLOR_GLITCH_PURPLE,
        (x + size // 4, y + size // 2, size // 2, size // 3),
    )

    # Efecto glitch: líneas horizontales desplazadas
    rng = random.Random(seed)
    for _ in range(3):
        gy = y + rng.randint(2, size - 2)
        offset = rng.randint(-4, 4)
        ancho = rng.randint(size // 3, size)
        franja = pygame.Surface((ancho, 2), pygame.SRCALPHA)
        franja.fill((*COLOR_GLITCH_RED, 120))
        surface.blit(franja, (x + offset, gy))

    # Scanlines sutiles
    for i in range(0, size, 3):
        scanline = pygame.Surface((size, 1), pygame.SRCALPHA)
        scanline.fill((0, 0, 0, 40))
        surface.blit(scanline, (x, y + i))


def generar_nombre_usuario(seed: int) -> str:
    """
    Genera nombres de usuario estilo red social corrupta.
    Mezcla de palabras comunes + números + caracteres raros.
    """
    rng = random.Random(seed)

    prefijos = [
        "Us3r",
        "An0n",
        "X_",
        "D4rk",
        "Ph4nt0m",
        "Gh0st",
        "N4m3l3ss",
        "Vox",
    ]
    sufijos = [
        "_real",
        "_oficial",
        "2024",
        "_xd",
        "_lol",
        "404",
        "_ok",
        "_true",
    ]
    numero = rng.randint(100, 9999)

    return f"{rng.choice(prefijos)}{numero}{rng.choice(sufijos)}"


def generar_timestamp() -> str:
    """Timestamp falso creíble."""
    opciones = [
        "hace 2 min",
        "hace 5 min",
        "hace 12 min",
        "hace 28 min",
        "hace 1 hora",
        "hace 3 horas",
    ]
    return random.choice(opciones)


def generar_stats(seed: int, es_acoso: bool) -> dict:
    """
    Stats falsos pero creíbles.
    Posts de acoso tienen más engagement (triste pero real).
    """
    rng = random.Random(seed)

    if es_acoso:
        likes = rng.randint(200, 2000)
        compartir = rng.randint(100, 1000)
        comenta = rng.randint(50, 500)
        reportes = rng.randint(2, 30)
    else:
        likes = rng.randint(10, 200)
        compartir = rng.randint(5, 80)
        comenta = rng.randint(3, 50)
        reportes = rng.randint(0, 5)

    def formatear(n):
        return f"{n/1000:.1f}K" if n >= 1000 else str(n)

    return {
        "likes": formatear(likes),
        "compartir": formatear(compartir),
        "comenta": formatear(comenta),
        "reportes": formatear(reportes),
    }


def dibujar_barra_actividad(
    surface: pygame.Surface, x: int, y: int, ancho: int, nivel: float
) -> None:
    """
    Barra horizontal que muestra el 'calor' de la publicación.
    nivel: 0.0 a 1.0
    Color: verde (bajo) → amarillo (medio) → rojo (alto)
    """
    ALTO = 4

    # Fondo de la barra
    pygame.draw.rect(surface, (20, 10, 30), (x, y, ancho, ALTO))

    # Calcular color según nivel
    if nivel < 0.5:
        r = int(nivel * 2 * 255)
        g = 200
        b = 50
    else:
        r = 255
        g = int((1 - nivel) * 2 * 200)
        b = 0

    # Relleno
    fill_w = int(ancho * nivel)
    if fill_w > 0:
        pygame.draw.rect(surface, (r, g, b), (x, y, fill_w, ALTO))

    # Borde
    pygame.draw.rect(surface, (60, 30, 80), (x, y, ancho, ALTO), 1)


# ============================================================================
# CLASE PRINCIPAL DEL MINIJUEGO
# ============================================================================


class MinijuegoPapers:
    """
    Minijuego estilo Papers Please.
    El jugador debe clasificar 5 publicaciones correctamente para poder entrar al boss.
    Sin límite de tiempo. Debe responder todo bien. Si falla una, reinicia desde el principio.
    """

    ESTADO_INTRO = "intro"
    ESTADO_JUGANDO = "jugando"
    ESTADO_FEEDBACK = "feedback"
    ESTADO_FALLIDO = "fallido"
    ESTADO_COMPLETADO = "completado"

    def __init__(self, logical_w: int, logical_h: int):
        self.lw = logical_w
        self.lh = logical_h
        self.estado = self.ESTADO_INTRO
        self.terminado = False
        self.aprobado = False
        self.pub_actual = 0
        self.correctas = 0
        self.timer_feedback = 0.0
        self.TIEMPO_FEEDBACK = 2.5  # segundos de feedback

        # Animación de entrada/salida de tarjeta
        self.card_offset_x = logical_w  # empieza fuera
        self.card_animando = False
        self.card_dir = -1  # -1 entra, 1 sale

        # Última acción para feedback
        self.ultima_accion = None
        self.ultimo_correcto = False

        # Rects de botones
        self.rect_btn_reportar = pygame.Rect(0, 0, 0, 0)
        self.rect_btn_ignorar = pygame.Rect(0, 0, 0, 0)

        # Mostrar cursor del ratón durante el minijuego
        pygame.mouse.set_visible(True)

        self._cargar_fuentes()

    def _cargar_fuentes(self):
        """Carga las fuentes para el minijuego."""
        try:
            self.font_title = pygame.font.SysFont("monospace", 20, bold=True)
            self.font_user = pygame.font.SysFont("monospace", 14, bold=True)
            self.font_text = pygame.font.SysFont("monospace", 13)
            self.font_stats = pygame.font.SysFont("monospace", 11)
            self.font_btn = pygame.font.SysFont("monospace", 15, bold=True)
            self.font_feed = pygame.font.SysFont("monospace", 13)
        except Exception:
            f = pygame.font.Font(None, 16)
            self.font_title = f
            self.font_user = f
            self.font_text = f
            self.font_stats = f
            self.font_btn = f
            self.font_feed = f

    def reset(self):
        """Reiniciar desde el principio."""
        self.pub_actual = 0
        self.correctas = 0
        self.estado = self.ESTADO_JUGANDO
        self.card_offset_x = self.lw
        self.card_animando = True
        self.card_dir = -1
        self._update_button_rects()

    def _update_button_rects(self):
        """Actualizar posiciones y rects de los botones."""
        BTN_W = 220
        BTN_H = 50
        BTN_Y = self.lh - 100
        GAP = 40

        TOTAL_W = BTN_W * 2 + GAP
        BTN_R_X = (self.lw - TOTAL_W) // 2
        BTN_I_X = BTN_R_X + BTN_W + GAP

        self.rect_btn_reportar = pygame.Rect(BTN_R_X, BTN_Y, BTN_W, BTN_H)
        self.rect_btn_ignorar = pygame.Rect(BTN_I_X, BTN_Y, BTN_W, BTN_H)

    def on_accion(self, accion: str):
        """
        Llamar cuando el jugador presiona REPORTAR o IGNORAR.
        accion: "REPORTAR" o "IGNORAR"
        """
        if self.estado != self.ESTADO_JUGANDO:
            return

        pub = PUBLICACIONES[self.pub_actual]
        self.ultima_accion = accion
        self.ultimo_correcto = accion == pub["accion_correcta"]

        if self.ultimo_correcto:
            self.correctas += 1
            self.estado = self.ESTADO_FEEDBACK
            self.timer_feedback = 0.0
        else:
            # Falló — mostrar feedback y luego reiniciar
            self.estado = self.ESTADO_FALLIDO
            self.timer_feedback = 0.0

    def update(self, dt: float):
        """Actualizar lógica del minijuego."""
        # Actualizar rects de botones
        self._update_button_rects()

        # Animación de la tarjeta
        if self.card_animando:
            velocidad = 1800 * dt
            if self.card_dir == -1:
                self.card_offset_x = max(0, self.card_offset_x - velocidad)
                if self.card_offset_x <= 0:
                    self.card_animando = False
            else:
                self.card_offset_x = min(
                    self.lw, self.card_offset_x + velocidad
                )
                if self.card_offset_x >= self.lw:
                    self.card_animando = False
                    self.card_offset_x = self.lw
                    self.pub_actual += 1

                    if self.pub_actual >= len(PUBLICACIONES):
                        self.estado = self.ESTADO_COMPLETADO
                        self.aprobado = True
                        self.terminado = True
                    else:
                        # Animar entrada de siguiente tarjeta
                        self.card_dir = -1
                        self.card_animando = True

        # Timer de feedback
        if self.estado in (self.ESTADO_FEEDBACK, self.ESTADO_FALLIDO):
            self.timer_feedback += dt
            if self.timer_feedback >= self.TIEMPO_FEEDBACK:
                if self.estado == self.ESTADO_FEEDBACK:
                    # Avanzar a siguiente tarjeta
                    self.estado = self.ESTADO_JUGANDO
                    self.card_dir = 1
                    self.card_animando = True
                else:
                    # Reiniciar todo
                    self.reset()

    def handle_event(self, event):
        """Manejar eventos del minijuego."""
        if self.estado == self.ESTADO_INTRO:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.reset()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Click cualquiera en intro también inicia
                self.reset()
            return

        if self.estado != self.ESTADO_JUGANDO:
            return

        # Manejar clicks del mouse
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Click izquierdo
                mx, my = event.pos
                # Nota: event.pos ya viene en coordenadas de pantalla escaladas
                if self.rect_btn_reportar.collidepoint(mx, my):
                    self.on_accion("REPORTAR")
                    return
                elif self.rect_btn_ignorar.collidepoint(mx, my):
                    self.on_accion("IGNORAR")
                    return

        # Manejar teclas
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.on_accion("REPORTAR")
            elif event.key == pygame.K_i:
                self.on_accion("IGNORAR")

    def render(self, surface: pygame.Surface):
        """Renderizar el minijuego."""
        # Fondo completo
        surface.fill(COLOR_BG_OUTER)
        self._render_static_bg(surface)

        if self.estado == self.ESTADO_INTRO:
            self._render_intro(surface)
            return

        if self.estado == self.ESTADO_COMPLETADO:
            self._render_completado(surface)
            return

        # Tarjeta con offset de animación
        pub = PUBLICACIONES[min(self.pub_actual, len(PUBLICACIONES) - 1)]
        self._render_header(surface)
        self._render_tarjeta(surface, pub)
        self._render_botones(surface)
        self._render_progreso(surface)

        if self.estado in (self.ESTADO_FEEDBACK, self.ESTADO_FALLIDO):
            self._render_feedback(surface, pub)

    def _render_static_bg(self, surface):
        """Estática de fondo muy sutil."""
        for _ in range(150):
            x = random.randint(0, self.lw)
            y = random.randint(0, self.lh)
            s = random.randint(1, 2)
            a = random.randint(10, 40)
            dot = pygame.Surface((s, s), pygame.SRCALPHA)
            dot.fill((150, 100, 200, a))
            surface.blit(dot, (x, y))

    def _render_header(self, surface):
        """Header del minijuego."""
        HEADER_H = 60
        # Fondo header
        pygame.draw.rect(surface, (8, 4, 15), (0, 0, self.lw, HEADER_H))
        pygame.draw.line(
            surface,
            COLOR_GLITCH_PURPLE,
            (0, HEADER_H),
            (self.lw, HEADER_H),
            1,
        )

        # Título
        titulo = self.font_title.render(
            "== MÓDULO DE CLASIFICACIÓN -- NIVEL 3",
            False,
            (180, 120, 255),
        )
        surface.blit(titulo, (20, 10))

        # Subtítulo
        sub = self.font_stats.render(
            "Clasifica estas publicaciones para continuar. "
            "Debes acertar todas.",
            False,
            (100, 70, 140),
        )
        surface.blit(sub, (20, 35))

        # Indicador de teclas
        hint = self.font_stats.render(
            "[R] REPORTAR    [I] IGNORAR", False, (70, 50, 100)
        )
        surface.blit(hint, (self.lw - 220, 35))

    def _render_tarjeta(self, surface, pub):
        """Renderiza la tarjeta de publicación."""
        CARD_W = 600
        CARD_H = 280
        CARD_X = (self.lw - CARD_W) // 2 + int(self.card_offset_x)
        CARD_Y = 80

        # Sombra de la tarjeta
        sombra = pygame.Surface((CARD_W + 8, CARD_H + 8), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 100))
        surface.blit(sombra, (CARD_X + 4, CARD_Y + 4))

        # Fondo tarjeta
        pygame.draw.rect(surface, COLOR_CARD_BG, (CARD_X, CARD_Y, CARD_W, CARD_H))

        # Borde con brillo sutil
        pygame.draw.rect(
            surface, COLOR_CARD_BORDER, (CARD_X, CARD_Y, CARD_W, CARD_H), 1
        )
        pygame.draw.rect(
            surface, (60, 30, 90), (CARD_X + 1, CARD_Y + 1, CARD_W - 2, CARD_H - 2), 1
        )

        # Header de la tarjeta (avatar + usuario + timestamp)
        HEADER_CARD_H = 55
        pygame.draw.rect(
            surface, COLOR_CARD_HEADER, (CARD_X, CARD_Y, CARD_W, HEADER_CARD_H)
        )
        pygame.draw.line(
            surface,
            COLOR_CARD_BORDER,
            (CARD_X, CARD_Y + HEADER_CARD_H),
            (CARD_X + CARD_W, CARD_Y + HEADER_CARD_H),
            1,
        )

        # Avatar
        AVATAR_SIZE = 40
        AVATAR_X = CARD_X + 12
        AVATAR_Y = CARD_Y + 8
        dibujar_avatar(surface, AVATAR_X, AVATAR_Y, AVATAR_SIZE, pub["seed"])

        # Nombre de usuario
        nombre = generar_nombre_usuario(pub["seed"])
        txt_nombre = self.font_user.render(nombre, False, COLOR_USERNAME)
        surface.blit(txt_nombre, (AVATAR_X + AVATAR_SIZE + 10, CARD_Y + 12))

        # Badge verificado corrupto
        badge = self.font_stats.render("[V] verificado", False, (80, 50, 120))
        surface.blit(badge, (AVATAR_X + AVATAR_SIZE + 10, CARD_Y + 28))

        # Timestamp
        ts = self.font_stats.render(generar_timestamp(), False, COLOR_TIMESTAMP)
        surface.blit(ts, (CARD_X + CARD_W - 100, CARD_Y + 20))

        # Ícono de exclamación (contenido reportable)
        if pub["es_acoso"]:
            exc = self.font_stats.render("<!!!>", False, (120, 0, 0))
            surface.blit(exc, (CARD_X + CARD_W - 50, CARD_Y + 8))

        # Texto del post con word wrap
        self._render_texto_post(
            surface,
            pub["texto"],
            CARD_X + 15,
            CARD_Y + HEADER_CARD_H + 15,
            CARD_W - 30,
            120,
        )

        # Footer stats
        FOOTER_Y = CARD_Y + CARD_H - 55
        pygame.draw.line(
            surface,
            COLOR_CARD_BORDER,
            (CARD_X, FOOTER_Y),
            (CARD_X + CARD_W, FOOTER_Y),
            1,
        )

        stats = generar_stats(pub["seed"], pub["es_acoso"])
        self._render_stats(surface, stats, CARD_X + 15, FOOTER_Y + 8, CARD_W - 30)

        # Barra de actividad
        dibujar_barra_actividad(
            surface,
            CARD_X + 15,
            FOOTER_Y + 38,
            CARD_W - 30,
            pub["nivel_actividad"],
        )

        # Overlay de feedback si aplica
        if self.estado in (self.ESTADO_FEEDBACK, self.ESTADO_FALLIDO):
            progreso = min(
                1.0, self.timer_feedback / self.TIEMPO_FEEDBACK
            )
            if self.ultimo_correcto:
                color = (0, 180, 60, int(80 * (1 - progreso)))
            else:
                color = (180, 0, 0, int(80 * (1 - progreso)))

            overlay = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            overlay.fill(color)
            surface.blit(overlay, (CARD_X, CARD_Y))

    def _render_texto_post(self, surface, texto, x, y, max_w, max_h):
        """Renderiza texto con word wrap."""
        palabras = texto.split(" ")
        linea = ""
        lineas = []

        for palabra in palabras:
            prueba = linea + (" " if linea else "") + palabra
            if self.font_text.size(prueba)[0] <= max_w:
                linea = prueba
            else:
                if linea:
                    lineas.append(linea)
                linea = palabra
        if linea:
            lineas.append(linea)

        line_h = self.font_text.get_height() + 4
        for i, l in enumerate(lineas):
            if i * line_h > max_h:
                break
            txt = self.font_text.render(l, False, COLOR_POST_TEXT)
            surface.blit(txt, (x, y + i * line_h))

    def _render_stats(self, surface, stats, x, y, ancho):
        """Renderiza los stats de la publicación."""
        items = [
            (f"LIKE {stats['likes']}", COLOR_GLITCH_RED),
            (f"[->] {stats['compartir']}", COLOR_STATS),
            (f"[o] {stats['comenta']}", COLOR_STATS),
            (f"[!] {stats['reportes']}", (100, 60, 0)),
        ]
        gap = ancho // len(items)
        for i, (texto, color) in enumerate(items):
            txt = self.font_stats.render(texto, False, color)
            surface.blit(txt, (x + i * gap, y))

    def _render_botones(self, surface):
        """Renderiza los botones REPORTAR e IGNORAR."""
        mx, my = pygame.mouse.get_pos()

        # Botón REPORTAR
        hover_r = self.rect_btn_reportar.collidepoint(mx, my)
        color_r = COLOR_BTN_REPORT_HOVER if hover_r else COLOR_BTN_REPORT_BG
        pygame.draw.rect(surface, color_r, self.rect_btn_reportar)
        pygame.draw.rect(
            surface, COLOR_BTN_REPORT_BORDER, self.rect_btn_reportar, 2
        )

        txt_r = self.font_btn.render("[!] R E P O R T A R", False, (255, 200, 200))
        surface.blit(
            txt_r,
            (
                self.rect_btn_reportar.x + (self.rect_btn_reportar.width - txt_r.get_width()) // 2,
                self.rect_btn_reportar.y + (self.rect_btn_reportar.height - txt_r.get_height()) // 2,
            ),
        )

        # Hint tecla
        hint_r = self.font_stats.render("[R]", False, (120, 60, 60))
        surface.blit(hint_r, (self.rect_btn_reportar.x + 5, self.rect_btn_reportar.y + 5))

        # Botón IGNORAR
        hover_i = self.rect_btn_ignorar.collidepoint(mx, my)
        color_i = COLOR_BTN_IGNORE_HOVER if hover_i else COLOR_BTN_IGNORE_BG
        pygame.draw.rect(surface, color_i, self.rect_btn_ignorar)
        pygame.draw.rect(
            surface, COLOR_BTN_IGNORE_BORDER, self.rect_btn_ignorar, 2
        )

        txt_i = self.font_btn.render("[X] I G N O R A R", False, (180, 160, 200))
        surface.blit(
            txt_i,
            (
                self.rect_btn_ignorar.x + (self.rect_btn_ignorar.width - txt_i.get_width()) // 2,
                self.rect_btn_ignorar.y + (self.rect_btn_ignorar.height - txt_i.get_height()) // 2,
            ),
        )

        hint_i = self.font_stats.render("[I]", False, (80, 70, 100))
        surface.blit(hint_i, (self.rect_btn_ignorar.x + 5, self.rect_btn_ignorar.y + 5))

    def _render_progreso(self, surface):
        """Indicador de progreso — cuántas quedan."""
        total = len(PUBLICACIONES)
        actual = self.pub_actual + 1
        txt = self.font_stats.render(
            f"Publicación {actual} de {total}", False, (80, 60, 110)
        )
        surface.blit(txt, (self.lw - txt.get_width() - 20, self.lh - 30))

        # Puntos de progreso con contraste claro
        DOT_SIZE = 12
        DOT_GAP = 18
        total_w = total * (DOT_SIZE + DOT_GAP)
        start_x = (self.lw - total_w) // 2
        dot_y = self.lh - 28

        for i in range(total):
            # Puntos llenos: verde brillante | Puntos vacíos: gris oscuro
            if i < actual:
                color_fill = (0, 220, 100)  # Verde neón brillante
                color_border = (0, 255, 120)
            else:
                color_fill = (30, 25, 45)  # Gris oscuro casi negro
                color_border = (60, 50, 80)

            pygame.draw.rect(
                surface,
                color_fill,
                (start_x + i * (DOT_SIZE + DOT_GAP), dot_y, DOT_SIZE, DOT_SIZE),
            )
            pygame.draw.rect(
                surface,
                color_border,
                (start_x + i * (DOT_SIZE + DOT_GAP), dot_y, DOT_SIZE, DOT_SIZE),
                2,
            )

    def _render_feedback(self, surface, pub):
        """Panel de feedback educativo."""
        FEED_H = 70
        FEED_Y = self.lh - 170

        # Fondo del feedback
        feed_surf = pygame.Surface((self.lw, FEED_H), pygame.SRCALPHA)
        if self.ultimo_correcto:
            feed_surf.fill((0, 60, 20, 200))
        else:
            feed_surf.fill((60, 0, 0, 200))
        surface.blit(feed_surf, (0, FEED_Y))

        pygame.draw.line(
            surface,
            COLOR_FEEDBACK_GOOD if self.ultimo_correcto else COLOR_FEEDBACK_BAD,
            (0, FEED_Y),
            (self.lw, FEED_Y),
            1,
        )

        # Icono y texto
        if self.ultimo_correcto:
            icono = "[OK] CORRECTO"
            color = COLOR_FEEDBACK_GOOD
            texto = pub["feedback_correcto"]
        else:
            icono = "[XX] INCORRECTO"
            color = COLOR_FEEDBACK_BAD
            texto = pub["feedback_incorrecto"]

        txt_icono = self.font_btn.render(icono, False, color)
        surface.blit(txt_icono, (30, FEED_Y + 8))

        txt_feed = self.font_feed.render(texto, False, (200, 180, 220))
        surface.blit(txt_feed, (30, FEED_Y + 35))

        # Si falló, mostrar mensaje grande de reinicio centrado
        if self.estado == self.ESTADO_FALLIDO:
            # Crear fuente más grande para el mensaje de reinicio
            font_restart = pygame.font.SysFont("monospace", 36, bold=True)
            msg_restart = "REINICIANDO..."
            txt_restart = font_restart.render(msg_restart, False, (255, 80, 80))

            # Centrar el mensaje en la pantalla
            restart_x = (self.lw - txt_restart.get_width()) // 2
            restart_y = (self.lh - txt_restart.get_height()) // 2

            # Fondo semitransparente detrás del mensaje
            bg_rect = txt_restart.get_rect(center=(self.lw // 2, self.lh // 2))
            bg_rect.inflate_ip(60, 40)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surf.fill((20, 0, 0, 220))
            surface.blit(bg_surf, bg_rect.topleft)

            # Borde rojo brillante
            pygame.draw.rect(surface, (255, 100, 100), bg_rect, 3)

            # Renderizar el texto
            surface.blit(txt_restart, (restart_x, restart_y))

    def _render_intro(self, surface):
        """Pantalla de introducción del minijuego."""
        cx = self.lw // 2
        cy = self.lh // 2

        # Panel central
        PAN_W, PAN_H = 600, 300
        PAN_X = cx - PAN_W // 2
        PAN_Y = cy - PAN_H // 2

        pygame.draw.rect(surface, (8, 4, 15), (PAN_X, PAN_Y, PAN_W, PAN_H))
        pygame.draw.rect(
            surface, COLOR_GLITCH_PURPLE, (PAN_X, PAN_Y, PAN_W, PAN_H), 1
        )

        titulo = self.font_title.render(
            "== MÓDULO DE CLASIFICACIÓN", False, (180, 120, 255)
        )
        surface.blit(titulo, (cx - titulo.get_width() // 2, PAN_Y + 30))

        lineas = [
            "Antes de enfrentar al origen del acoso,",
            "debes demostrar que sabes identificarlo.",
            "",
            "Se te mostrarán 5 publicaciones.",
            "Debes clasificar TODAS correctamente.",
            "Si fallas una, empiezas de nuevo.",
            "",
            "[R] Reportar    [I] Ignorar",
        ]

        for i, linea in enumerate(lineas):
            color = (200, 160, 255) if linea.startswith("[") else (160, 130, 200)
            txt = self.font_text.render(linea, False, color)
            surface.blit(txt, (cx - txt.get_width() // 2, PAN_Y + 90 + i * 22))

        # Prompt para continuar
        continuar = self.font_btn.render(
            "[ ESPACIO / ENTER para comenzar ]",
            False,
            (100, 70, 150),
        )
        surface.blit(continuar, (cx - continuar.get_width() // 2, PAN_Y + PAN_H - 40))

    def _render_completado(self, surface):
        """Pantalla de felicitación al completar."""
        cx = self.lw // 2
        cy = self.lh // 2

        PAN_W, PAN_H = 500, 220
        PAN_X = cx - PAN_W // 2
        PAN_Y = cy - PAN_H // 2

        pygame.draw.rect(surface, (4, 15, 8), (PAN_X, PAN_Y, PAN_W, PAN_H))
        pygame.draw.rect(surface, (0, 150, 60), (PAN_X, PAN_Y, PAN_W, PAN_H), 2)

        titulo = self.font_title.render(
            "[OK] MÓDULO COMPLETADO", False, COLOR_FEEDBACK_GOOD
        )
        surface.blit(titulo, (cx - titulo.get_width() // 2, PAN_Y + 30))

        lineas = [
            "Has demostrado que sabes identificar",
            "el ciberacoso. Estás listo.",
            "",
            "Las puertas se abren.",
        ]

        for i, linea in enumerate(lineas):
            txt = self.font_text.render(linea, False, (150, 220, 170))
            surface.blit(txt, (cx - txt.get_width() // 2, PAN_Y + 90 + i * 25))

    def run(self, background: pygame.Surface | None = None) -> bool:
        """
        Ejecutar el minijuego de forma bloqueante.
        Retorna True si aprobó, False si se canceló.
        """
        clock = pygame.time.Clock()
        screen = pygame.display.get_surface()

        while not self.terminado:
            dt = clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                self.handle_event(event)

            self.update(dt)

            # Renderizar
            if background:
                screen.blit(background, (0, 0))
            self.render(screen)
            pygame.display.flip()

        return self.aprobado
