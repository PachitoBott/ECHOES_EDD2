"""
Profesor Eduardo Ibarra — NPC hologramático de ECHOES.

Orientador universitario del mundo real que se proyecta como holograma
en la Red para guiar a Daniel Vega. Aparece como tienda especial:
antes de abrir el inventario obliga al jugador a responder una pregunta
educativa sobre ciberacoso.

Flujo de estado:
  IDLE  ->  (E)  ->  PREGUNTA  ->  (1/2/3)  ->  FEEDBACK  ->  (E/Enter/Space)  ->  TIENDA
  LISTO ->  (E)  ->  TIENDA  (pregunta ya respondida en esta sala)
"""
from __future__ import annotations
import math
from pathlib import Path
import pygame


# ---------------------------------------------------------------------------
# Banco de preguntas (una por zona; agregar más aquí)
# ---------------------------------------------------------------------------
PREGUNTAS: list[dict] = [
    {
        "zona": 1,
        "texto": [
            "Si una publicación falsa sobre ti empieza a circular,",
            "¿qué es lo primero que deberías hacer?",
        ],
        "opciones": [
            "1. Compartirla para defenderte.",
            "2. Guardar capturas, enlaces y buscar apoyo.",
            "3. Responder atacando a todos.",
        ],
        "correcta": 1,   # índice 0-based → opción 2
        "feedback_correcto": [
            "Correcto. La evidencia y el apoyo son",
            "la mejor forma de empezar a defenderte.",
        ],
        "feedback_incorrecto": [
            "No exactamente. Responder con rabia puede empeorar la situación.",
            "Primero guarda pruebas y busca apoyo.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "Si ves que están atacando a alguien en redes,",
            "¿cuál es la mejor acción?",
        ],
        "opciones": [
            "1. Compartirlo porque todos lo están haciendo.",
            "2. Ignorarlo siempre.",
            "3. No compartir, reportar y apoyar a la persona afectada.",
        ],
        "correcta": 2,   # índice 0-based → opción 3
        "feedback_correcto": [
            "Bien. No todo se combate con fuerza.",
            "A veces la mejor defensa es guardar pruebas y pedir ayuda.",
        ],
        "feedback_incorrecto": [
            "Todavía estás reaccionando desde el miedo.",
            "Respira. Primero evidencia, luego apoyo, luego acción.",
        ],
    },
    {
        "zona": 0,   # Zona 0 = alternativa/comodín
        "texto": [
            "¿Por qué no deberías compartir una publicación",
            "ofensiva aunque parezca graciosa?",
        ],
        "opciones": [
            "1. Porque puedes ayudar a que el daño se vuelva más grande.",
            "2. Porque las redes se dañan.",
            "3. Porque pierdes monedas automáticamente.",
        ],
        "correcta": 0,   # índice 0-based → opción 1
        "feedback_correcto": [
            "Exacto. Compartir aumenta el alcance del daño.",
            "Detenerlo empieza por no propagarlo.",
        ],
        "feedback_incorrecto": [
            "No es eso. Compartir contenido ofensivo amplifica el daño",
            "real sobre la persona afectada.",
        ],
    },
]

RECOMPENSA_CORRECTA   = 15   # microchips de evidencia
RECOMPENSA_INCORRECTA = 5


# ---------------------------------------------------------------------------
# Catálogo de la tienda del Profesor Ibarra
# ---------------------------------------------------------------------------
IBARRA_CATALOG: list[dict] = [
    {
        "id": "red_apoyo",
        "name": "Red de Apoyo",
        "price": 30,
        "max_buys": 3,
        "desc_lines": [
            "Tus aliados te respaldan.",
            "Recupera 2 puntos de vida.",
            "",
            "Puedes comprarla hasta 3 veces.",
        ],
        "icon_color": (80, 200, 120),
        "icon_char": "+",
    },
    {
        "id": "modo_privado",
        "name": "Modo Privado",
        "price": 50,
        "max_buys": 1,
        "desc_lines": [
            "Desapareces de las redes.",
            "Invulnerable por 5 segundos.",
            "",
            "Solo puedes comprarla una vez.",
        ],
        "icon_color": (100, 180, 255),
        "icon_char": "M",
    },
    {
        "id": "emp",
        "name": "EMP",
        "price": 45,
        "max_buys": 1,
        "desc_lines": [
            "Pulso electromagnético.",
            "Congela todos los enemigos",
            "en la sala durante 4 segundos.",
            "",
            "Solo puedes comprarla una vez.",
        ],
        "icon_color": (255, 220, 60),
        "icon_char": "~",
    },
    {
        "id": "evidencia_guardada",
        "name": "Evidencia Guardada",
        "price": 60,
        "max_buys": 1,
        "desc_lines": [
            "Guardas pruebas de todo.",
            "Revela el mapa completo",
            "de manera permanente.",
            "",
            "Solo puedes comprarla una vez.",
        ],
        "icon_color": (220, 120, 255),
        "icon_char": "E",
    },
]


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class ProfesorIbarra:
    """NPC hologramático del Profesor Eduardo Ibarra."""

    IDLE         = "idle"
    PREGUNTA     = "pregunta"
    FEEDBACK     = "feedback"
    TIENDA       = "tienda"
    LISTO        = "listo"

    def __init__(self, pos: tuple[int, int], zona: int = 1) -> None:
        self.pos = pos
        cx, cy = pos
        self.rect = pygame.Rect(cx - 16, cy - 30, 32, 60)
        self.interact_radius = 28

        # Seleccionar pregunta por zona; cae al comodín si no hay
        candidates = [p for p in PREGUNTAS if p["zona"] == zona]
        self.pregunta: dict = candidates[0] if candidates else PREGUNTAS[0]

        self.estado              = self.IDLE
        self.pregunta_respondida = False
        self._feedback_lines: list[str] = []

        self._time      = 0.0
        self._last_tick = pygame.time.get_ticks()

        # --- Tienda carousel ---
        self._carousel_idx: int = 0
        self._purchase_counts: dict[str, int] = {item["id"]: 0 for item in IBARRA_CATALOG}
        self._last_msg: str = ""
        self._msg_timer: float = 0.0

        # --- Efectos pendientes (Game.py los consume) ---
        self.emp_pending: bool = False
        self.map_reveal_pending: bool = False

        # --- Sprite sheet animado (conversación) ---
        self._talk_frames: list[pygame.Surface] = self._load_talk_frames()
        self._talk_frame_idx: int = 0
        self._talk_anim_timer: float = 0.0
        self._TALK_FRAME_SPEED: float = 0.10  # segundos por frame

        # --- Sprite sheet idle (en partida) ---
        self._idle_frames: list[pygame.Surface] = self._load_idle_frames()
        self._idle_frame_idx: int = 0
        self._idle_anim_timer: float = 0.0
        self._IDLE_FRAME_SPEED: float = 0.20  # segundos por frame (idle más lento)

    # ------------------------------------------------------------------
    # Interacción
    # ------------------------------------------------------------------
    def can_interact(self, player_rect) -> bool:
        if not isinstance(player_rect, pygame.Rect):
            try:
                player_rect = pygame.Rect(*player_rect)
            except Exception:
                return False
        area = self.rect.inflate(self.interact_radius * 2, self.interact_radius * 2)
        return area.colliderect(player_rect)

    def iniciar_interaccion(self) -> None:
        if self.pregunta_respondida:
            self.estado = self.TIENDA
        else:
            self.estado = self.PREGUNTA

    def responder(self, opcion_idx: int, player) -> None:
        """Registra la respuesta, otorga recompensa y cambia a FEEDBACK."""
        if opcion_idx == self.pregunta["correcta"]:
            reward = RECOMPENSA_CORRECTA
            lines  = list(self.pregunta["feedback_correcto"])
        else:
            reward = RECOMPENSA_INCORRECTA
            lines  = list(self.pregunta["feedback_incorrecto"])

        player.gold = getattr(player, "gold", 0) + reward
        lines.append("")
        lines.append(f"+{reward} microchips de evidencia.")
        lines.append("")
        lines.append("Ahora sí. Te enviaré algunos recursos desde el mundo real.")
        lines.append("(Presiona E, Enter o Espacio para abrir la tienda)")

        self._feedback_lines   = lines
        self.pregunta_respondida = True
        self.estado              = self.FEEDBACK

    def abrir_tienda(self) -> None:
        """Entra al estado TIENDA (carousel)."""
        self.estado = self.TIENDA

    def cerrar_tienda(self) -> None:
        """Cierra la tienda y vuelve a LISTO."""
        self.estado = self.LISTO
        self._last_msg = ""
        self._msg_timer = 0.0

    # ------------------------------------------------------------------
    # Manejo de eventos de la tienda carousel
    # ------------------------------------------------------------------
    def handle_tienda_event(self, ev: pygame.event.Event, player) -> None:
        """Procesa teclas dentro del carrusel de la tienda."""
        if ev.type != pygame.KEYDOWN:
            return

        n = len(IBARRA_CATALOG)

        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self._carousel_idx = (self._carousel_idx - 1) % n
            self._last_msg = ""
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self._carousel_idx = (self._carousel_idx + 1) % n
            self._last_msg = ""
        elif ev.key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
            self._try_buy_carousel(player)
        elif ev.key == pygame.K_ESCAPE:
            self.cerrar_tienda()

    def _try_buy_carousel(self, player) -> None:
        """Intenta comprar el ítem actual del carrusel."""
        item  = IBARRA_CATALOG[self._carousel_idx]
        iid   = item["id"]
        price = item["price"]
        max_b = item["max_buys"]
        bought = self._purchase_counts.get(iid, 0)

        if bought >= max_b:
            self._set_msg("Ya compraste el maximo de este item.")
            return

        gold = getattr(player, "gold", 0)
        if gold < price:
            self._set_msg("No tienes suficientes microchips.")
            return

        # Cobrar
        player.gold = gold - price
        self._purchase_counts[iid] = bought + 1

        # Aplicar efecto
        self._apply_item(iid, player)
        remaining = max_b - self._purchase_counts[iid]
        if remaining > 0:
            self._set_msg(f"Comprado! ({remaining} restante{'s' if remaining != 1 else ''})")
        else:
            self._set_msg("Comprado! (limite alcanzado)")

    def _apply_item(self, iid: str, player) -> None:
        """Aplica o almacena el efecto del ítem comprado."""
        if iid == "red_apoyo":
            # Efecto inmediato: recuperar 2 HP
            max_hp = getattr(player, "max_hp", getattr(player, "hp", 1))
            hp     = getattr(player, "hp", max_hp)
            new_hp = min(max_hp, hp + 2)
            setattr(player, "hp", new_hp)
            if hasattr(player, "_hits_taken_current_life"):
                setattr(player, "_hits_taken_current_life", max(0, max_hp - new_hp))

        elif iid == "modo_privado":
            # Se guarda para usar con R
            player._ibarra_modo_privado = True

        elif iid == "emp":
            # Se guarda para usar con Q
            player._ibarra_emp = True

        elif iid == "evidencia_guardada":
            # Efecto inmediato: revelar mapa
            self.map_reveal_pending = True

    def _set_msg(self, msg: str, duration: float = 2.5) -> None:
        self._last_msg   = msg
        self._msg_timer  = duration

    # ------------------------------------------------------------------
    # Eventos generales
    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event, player) -> None:
        """Procesa un evento dentro del estado activo del profesor."""

        # Click del mouse en opciones de pregunta
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.estado == self.PREGUNTA:
                for idx, rect in enumerate(getattr(self, "_option_rects", [])):
                    if rect.collidepoint(ev.pos):
                        self.responder(idx, player)
                        return
            elif self.estado == self.TIENDA:
                self.handle_tienda_event(ev, player)
                return

        if ev.type != pygame.KEYDOWN:
            return

        if self.estado == self.PREGUNTA:
            key_to_idx = {
                pygame.K_1: 0, pygame.K_KP1: 0,
                pygame.K_2: 1, pygame.K_KP2: 1,
                pygame.K_3: 2, pygame.K_KP3: 2,
            }
            idx = key_to_idx.get(ev.key)
            if idx is not None:
                self.responder(idx, player)

        elif self.estado == self.FEEDBACK:
            if ev.key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                self.estado = self.TIENDA

        elif self.estado == self.TIENDA:
            self.handle_tienda_event(ev, player)

    def update(self, dt: float = 0.0) -> None:
        """Actualiza el timer interno del holograma."""
        now = pygame.time.get_ticks()
        elapsed = (now - self._last_tick) / 1000.0
        self._time += elapsed
        self._last_tick = now

        # Usar el dt real de ticks si no se pasó explícitamente
        real_dt = elapsed if dt == 0.0 else dt
        if self._msg_timer > 0.0:
            self._msg_timer = max(0.0, self._msg_timer - real_dt)
            if self._msg_timer <= 0.0:
                self._last_msg = ""

        # Avanzar animación de hablar en estados de conversación
        if self.estado in (self.PREGUNTA, self.FEEDBACK):
            self._tick_talk_anim(real_dt)

        # Avanzar animación idle siempre
        if self._idle_frames:
            self._idle_anim_timer += real_dt
            if self._idle_anim_timer >= self._IDLE_FRAME_SPEED:
                self._idle_anim_timer -= self._IDLE_FRAME_SPEED
                self._idle_frame_idx = (self._idle_frame_idx + 1) % len(self._idle_frames)

    # ------------------------------------------------------------------
    # Sprite sheet animado
    # ------------------------------------------------------------------
    def _load_talk_frames(self) -> list[pygame.Surface]:
        """Carga los primeros 10 frames del sprite sheet 4×3 de 128×128 px por frame."""
        sheet_path = Path(__file__).parent.parent / "assets" / "npc" / "profesor_ibarra_sheet.png"
        if not sheet_path.exists():
            return []
        try:
            sheet = pygame.image.load(str(sheet_path)).convert_alpha()
        except Exception:
            return []

        FRAME_W, FRAME_H = 192, 192
        COLS = 4
        MAX_FRAMES = 10
        frames: list[pygame.Surface] = []
        for i in range(MAX_FRAMES):
            col = i % COLS
            row = i // COLS
            rect = pygame.Rect(col * FRAME_W, row * FRAME_H, FRAME_W, FRAME_H)
            frame = pygame.Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            # Escalar a 96×96 para usar dentro del panel de diálogo
            frame = pygame.transform.smoothscale(frame, (96, 96))
            frames.append(frame)
        return frames

    def _load_idle_frames(self) -> list[pygame.Surface]:
        """Carga los 3 primeros frames del sprite sheet idle 2×2 de 196×196 px por frame."""
        sheet_path = Path(__file__).parent.parent / "assets" / "npc" / "profesor_ibarra_idle.png"
        if not sheet_path.exists():
            return []
        try:
            sheet = pygame.image.load(str(sheet_path)).convert_alpha()
        except Exception:
            return []

        FRAME_W, FRAME_H = 196, 196
        COLS = 2
        MAX_FRAMES = 3
        frames: list[pygame.Surface] = []
        for i in range(MAX_FRAMES):
            col = i % COLS
            row = i // COLS
            rect = pygame.Rect(col * FRAME_W, row * FRAME_H, FRAME_W, FRAME_H)
            frame = pygame.Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            frame = pygame.transform.smoothscale(frame, (98, 98))
            frames.append(frame)
        return frames

    def _tick_talk_anim(self, dt: float) -> None:
        """Avanza la animación de hablar."""
        if not self._talk_frames:
            return
        self._talk_anim_timer += dt
        if self._talk_anim_timer >= self._TALK_FRAME_SPEED:
            self._talk_anim_timer -= self._TALK_FRAME_SPEED
            self._talk_frame_idx = (self._talk_frame_idx + 1) % len(self._talk_frames)

    def _draw_talk_sprite(self, surface: pygame.Surface, panel_x: int, panel_y: int, panel_w: int) -> None:
        """Obsoleto — el retrato ahora va integrado dentro del panel via _draw_portrait_box."""
        pass

    # ------------------------------------------------------------------
    # Renderizado
    # ------------------------------------------------------------------
    def _get_screen_font(self) -> pygame.font.Font:
        """Fuente para dibujar el diálogo directamente en screen (tamaño 2x)."""
        if not hasattr(self, "_screen_font_cache"):
            vt323 = Path(__file__).parent.parent / "assets" / "ui" / "VT323-Regular.ttf"
            try:
                self._screen_font_cache = pygame.font.Font(str(vt323), 34)
            except Exception:
                self._screen_font_cache = pygame.font.SysFont("consolas", 26)
        return self._screen_font_cache

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Dibuja solo el sprite/hologram en el world surface."""
        self.update()
        self._draw_hologram(surface)
        # Los paneles de diálogo se dibujan en screen via draw_screen()

    def draw_screen(self, screen: pygame.Surface) -> None:
        """Dibuja los paneles de diálogo directamente en el screen surface (encima del HUD)."""
        font = self._get_screen_font()
        if self.estado == self.PREGUNTA:
            self._draw_question_ui(screen, font)
        elif self.estado == self.FEEDBACK:
            self._draw_feedback_ui(screen, font)
        elif self.estado == self.TIENDA:
            self._draw_tienda_ui(screen, font)

    def draw_idle_hint(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        cx, cy = self.pos
        hint = font.render("E - Hablar con el Profesor Ibarra", True, (140, 210, 255))
        surface.blit(hint, (cx - hint.get_width() // 2, cy - 58))

    # --- hologram body ---
    def _draw_hologram(self, surface: pygame.Surface) -> None:
        cx, cy = self.pos

        # Si hay sprite idle, usarlo en lugar del placeholder
        if self._idle_frames:
            frame = self._idle_frames[self._idle_frame_idx]
            fw, fh = frame.get_size()
            surface.blit(frame, (cx - fw // 2, cy - fh // 2))
            return

        # Fallback: placeholder hologramático
        t       = self._time
        alpha   = int(155 + 65 * math.sin(t * 3.7))
        flicker = int(18 * math.sin(t * 11.3))
        head_c  = (50 + flicker, 170 + flicker, 240)
        body_c  = (30 + flicker, 140 + flicker, 215)

        tmp = pygame.Surface((44, 72), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (*head_c, alpha), (22, 10), 9)
        pygame.draw.rect(tmp, (*body_c, alpha), (14, 21, 16, 22))
        pygame.draw.rect(tmp, (*body_c, alpha), (5,  22, 9, 16))
        pygame.draw.rect(tmp, (*body_c, alpha), (30, 22, 9, 16))
        pygame.draw.rect(tmp, (*body_c, alpha), (14, 43, 7, 16))
        pygame.draw.rect(tmp, (*body_c, alpha), (23, 43, 7, 16))
        scan_a = max(0, min(255, 65 + flicker))
        for yl in range(0, 72, 4):
            pygame.draw.line(tmp, (*head_c, scan_a), (0, yl), (43, yl))
        surface.blit(tmp, (cx - 22, cy - 36))

        sig_a = int(175 + 80 * math.sin(t * 2.8))
        sig   = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(sig, (120, 230, 255, sig_a), (3, 3), 3)
        surface.blit(sig, (cx + 16, cy - 44))

    # --- panel helper (bottom-aligned, estilo RPG) ---
    def _draw_dialogue_panel(self, surface: pygame.Surface, ph: int) -> tuple[int, int, int]:
        """Dibuja el panel de diálogo en la parte inferior. Retorna (px, py, pw)."""
        sw, sh = surface.get_size()
        pw = sw - 32
        px = 16
        py = sh - ph - 175  # margen para quedar por encima del HUD

        # Fondo principal
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((3, 8, 24, 235))

        # Borde exterior teal
        pygame.draw.rect(panel, (0, 160, 210, 220), (0, 0, pw, ph), 2)
        # Borde interior más oscuro (doble borde)
        pygame.draw.rect(panel, (0, 80, 120, 140), (3, 3, pw - 6, ph - 6), 1)

        # Línea decorativa superior
        pygame.draw.line(panel, (0, 200, 255, 180), (12, 2), (pw - 12, 2), 1)

        # Esquinas decoradas
        corner = 8
        col = (0, 200, 255, 200)
        for cx2, cy2, dx, dy in [(0,0,1,1),(pw,0,-1,1),(0,ph,1,-1),(pw,ph,-1,-1)]:
            pygame.draw.line(panel, col, (cx2, cy2), (cx2 + dx*corner, cy2), 2)
            pygame.draw.line(panel, col, (cx2, cy2), (cx2, cy2 + dy*corner), 2)

        surface.blit(panel, (px, py))
        return px, py, pw

    def _draw_panel(self, surface: pygame.Surface, pw: int, ph: int,
                    cx: int | None = None, cy: int | None = None) -> tuple[int, int]:
        """Panel centrado genérico (usado por la tienda)."""
        sw, sh = surface.get_size()
        if cx is None:
            cx = sw // 2
        if cy is None:
            cy = sh // 2
        px = max(4, cx - pw // 2)
        py = max(4, cy - ph // 2)
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((3, 8, 24, 235))
        pygame.draw.rect(panel, (0, 160, 210, 220), (0, 0, pw, ph), 2)
        pygame.draw.rect(panel, (0, 80, 120, 140), (3, 3, pw - 6, ph - 6), 1)
        surface.blit(panel, (px, py))
        return px, py

    def _draw_portrait_box(self, surface: pygame.Surface, px: int, py: int, ph: int) -> int:
        """Dibuja el recuadro del retrato con el sprite animado. Retorna el x donde empieza el texto."""
        PORTRAIT_SIZE = 210
        PORTRAIT_PAD  = 12
        box_x = px + PORTRAIT_PAD
        box_y = py + (ph - PORTRAIT_SIZE) // 2
        box_rect = pygame.Rect(box_x, box_y, PORTRAIT_SIZE, PORTRAIT_SIZE)

        # Fondo del retrato
        portrait_bg = pygame.Surface((PORTRAIT_SIZE, PORTRAIT_SIZE), pygame.SRCALPHA)
        portrait_bg.fill((0, 20, 50, 200))
        pygame.draw.rect(portrait_bg, (0, 160, 220, 180), (0, 0, PORTRAIT_SIZE, PORTRAIT_SIZE), 2)
        surface.blit(portrait_bg, box_rect.topleft)

        # Sprite animado (escalar al tamaño del recuadro)
        if self._talk_frames:
            frame = pygame.transform.smoothscale(self._talk_frames[self._talk_frame_idx],
                                                  (PORTRAIT_SIZE, PORTRAIT_SIZE))
            surface.blit(frame, box_rect.topleft)

        # Nombre debajo del retrato
        return box_x + PORTRAIT_SIZE + 12  # x donde empieza el texto

    # --- pregunta ---
    def _draw_question_ui(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        lh = font.get_height() + 4
        ph = 16 + lh * 2 + 6 + lh * len(self.pregunta["texto"]) + 6 + lh * len(self.pregunta["opciones"]) + 6 + lh + 10
        ph = max(ph, 270)

        px, py, pw = self._draw_dialogue_panel(surface, ph)
        text_x = self._draw_portrait_box(surface, px, py, ph)
        text_w = pw - (text_x - px) - 10

        # Nameplate
        name_surf = font.render("◈  PROF. EDUARDO IBARRA", True, (0, 220, 255))
        surface.blit(name_surf, (text_x, py + 8))

        # Línea separadora bajo el nombre
        pygame.draw.line(surface, (0, 140, 180, 160),
                         (text_x, py + 8 + lh + 1),
                         (text_x + text_w, py + 8 + lh + 1), 1)

        y = py + 8 + lh + 8

        # Intro en gris azulado
        for line in ["Daniel, antes de comprar nada, necesito saber",
                     "si estás entendiendo cómo sobrevivir a esto."]:
            surface.blit(font.render(line, True, (140, 190, 220)), (text_x, y)); y += lh

        y += 4
        # Pregunta en blanco cálido
        for line in self.pregunta["texto"]:
            surface.blit(font.render(line, True, (240, 240, 200)), (text_x, y)); y += lh

        y += 6
        # Opciones clickeables con numeración clara
        mouse_pos = pygame.mouse.get_pos()
        self._option_rects: list[pygame.Rect] = []
        for idx, opcion in enumerate(self.pregunta["opciones"]):
            label = f"  {idx + 1}.  {opcion.split('.', 1)[-1].strip()}"
            opt_rect = pygame.Rect(text_x, y, text_w, lh + 2)
            self._option_rects.append(opt_rect)
            hovered = opt_rect.collidepoint(mouse_pos)
            bg_col = (0, 80, 60, 120) if hovered else (0, 0, 0, 0)
            if hovered:
                bg = pygame.Surface((text_w, lh + 4), pygame.SRCALPHA)
                bg.fill(bg_col)
                surface.blit(bg, (text_x, y - 2))
            text_col = (120, 255, 180) if hovered else (200, 230, 170)
            surface.blit(font.render(label, True, text_col), (text_x, y))
            y += lh + 4

        y += 2
        # Hint parpadeante
        hint_alpha = int(160 + 80 * math.sin(self._time * 4.0))
        hint_surf = font.render("[ 1 / 2 / 3 ]  o haz click en una opción", True, (80, 160, 130))
        hint_surf.set_alpha(hint_alpha)
        surface.blit(hint_surf, (text_x, y))

    # --- feedback ---
    def _draw_feedback_ui(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        lh = font.get_height() + 4
        ph = max(270, 16 + lh + 8 + lh * len(self._feedback_lines) + 10)

        px, py, pw = self._draw_dialogue_panel(surface, ph)
        text_x = self._draw_portrait_box(surface, px, py, ph)
        text_w = pw - (text_x - px) - 10

        # Nameplate
        name_surf = font.render("◈  PROF. EDUARDO IBARRA", True, (0, 220, 255))
        surface.blit(name_surf, (text_x, py + 8))

        pygame.draw.line(surface, (0, 140, 180, 160),
                         (text_x, py + 8 + lh + 1),
                         (text_x + text_w, py + 8 + lh + 1), 1)

        y = py + 8 + lh + 10
        for line in self._feedback_lines:
            if line.startswith("+"):
                color = (100, 255, 140)
            elif "incorrecto" in line.lower() or "no " in line.lower():
                color = (255, 160, 100)
            else:
                color = (180, 225, 255)
            surface.blit(font.render(line, True, color), (text_x, y)); y += lh

        # Hint
        hint_alpha = int(160 + 80 * math.sin(self._time * 4.0))
        hint_surf = font.render("[ E / ESPACIO ]  Continuar", True, (80, 160, 130))
        hint_surf.set_alpha(hint_alpha)
        surface.blit(hint_surf, (text_x, py + ph - lh - 8))

    # --- tienda carousel ---
    def _draw_tienda_ui(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        sw, sh = surface.get_size()
        lh = font.get_height() + 4

        # Dimensiones del panel principal
        pw = min(sw - 16, 480)
        max_desc_lines = max(len(it["desc_lines"]) for it in IBARRA_CATALOG)
        ph = 30 + 52 + 4 + 16 + lh * 2 + 4 + (lh + 2) * max_desc_lines + 10 + lh + 16
        ph = max(ph, 260)
        px, py = self._draw_panel(surface, pw, ph)

        # Título
        title_surf = font.render("[ Tienda del Profesor Ibarra ]", True, (100, 200, 255))
        surface.blit(title_surf, (px + pw // 2 - title_surf.get_width() // 2, py + 8))

        item = IBARRA_CATALOG[self._carousel_idx]
        iid  = item["id"]
        bought   = self._purchase_counts.get(iid, 0)
        max_buys = item["max_buys"]
        remaining = max_buys - bought
        exhausted = remaining <= 0

        # --- Icono del ítem (cuadrado coloreado con char) ---
        icon_size = 52
        icon_x    = px + pw // 2 - icon_size // 2
        icon_y    = py + 30

        icon_color = item["icon_color"] if not exhausted else (80, 80, 80)
        icon_surf  = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        pygame.draw.rect(icon_surf, (*icon_color, 200), (0, 0, icon_size, icon_size), border_radius=8)
        pygame.draw.rect(icon_surf, (255, 255, 255, 120), (0, 0, icon_size, icon_size), 2, border_radius=8)

        # Carácter en el centro del ícono
        try:
            icon_font = pygame.font.SysFont(None, 36)
        except Exception:
            icon_font = font
        ch_surf = icon_font.render(item["icon_char"], True, (255, 255, 255))
        icon_surf.blit(ch_surf, (icon_size // 2 - ch_surf.get_width() // 2,
                                  icon_size // 2 - ch_surf.get_height() // 2))
        surface.blit(icon_surf, (icon_x, icon_y))

        # Flechas de navegación ← →
        arrow_col = (160, 200, 255) if not exhausted else (80, 80, 100)
        lbl = font.render("<", True, arrow_col)
        surface.blit(lbl, (icon_x - lbl.get_width() - 16, icon_y + icon_size // 2 - lh // 2))
        rbl = font.render(">", True, arrow_col)
        surface.blit(rbl, (icon_x + icon_size + 16, icon_y + icon_size // 2 - lh // 2))

        # Indicador de posición  ○●○○
        dot_y = icon_y + icon_size + 4
        n = len(IBARRA_CATALOG)
        dot_spacing = 14
        dots_x_start = px + pw // 2 - (n * dot_spacing) // 2
        for i in range(n):
            col = (140, 210, 255) if i == self._carousel_idx else (70, 90, 120)
            pygame.draw.circle(surface, col, (dots_x_start + i * dot_spacing + dot_spacing // 2,
                                               dot_y + 5), 4 if i == self._carousel_idx else 3)

        # Nombre del ítem
        name_col  = (255, 255, 180) if not exhausted else (120, 120, 100)
        name_surf = font.render(item["name"], True, name_col)
        text_y    = dot_y + 16
        surface.blit(name_surf, (px + pw // 2 - name_surf.get_width() // 2, text_y))
        text_y   += lh

        # Precio  |  compras restantes
        price_col = (255, 220, 60) if not exhausted else (100, 100, 80)
        price_str = f"{item['price']} microchips"
        if remaining > 0:
            buy_str = f"Disponibles: {remaining}/{max_buys}"
        else:
            buy_str = "AGOTADO"
        info_surf  = font.render(f"{price_str}   |   {buy_str}", True, price_col)
        surface.blit(info_surf, (px + pw // 2 - info_surf.get_width() // 2, text_y))
        text_y += lh

        # --- Panel de descripción (mini panel debajo) ---
        desc_pw = pw - 16
        desc_lines = item["desc_lines"]
        desc_lh    = font.get_height() + 2
        desc_ph    = len(desc_lines) * desc_lh + 10
        desc_px    = px + 8
        desc_py    = text_y + 4

        desc_surf  = pygame.Surface((desc_pw, desc_ph), pygame.SRCALPHA)
        desc_surf.fill((12, 24, 52, 200))
        pygame.draw.rect(desc_surf, (60, 120, 200, 180), (0, 0, desc_pw, desc_ph), 1)
        surface.blit(desc_surf, (desc_px, desc_py))

        dy = desc_py + 5
        for line in desc_lines:
            dc = (185, 225, 255) if line else (0, 0, 0, 0)
            if line:
                dl = font.render(line, True, dc)
                surface.blit(dl, (desc_px + 8, dy))
            dy += desc_lh

        # Mensaje temporal (error/confirmación)
        if self._last_msg:
            msg_col  = (255, 200, 80) if "Comprado" in self._last_msg else (255, 100, 100)
            msg_surf = font.render(self._last_msg, True, msg_col)
            surface.blit(msg_surf, (px + pw // 2 - msg_surf.get_width() // 2,
                                     py + ph - lh - 4))

        # Instrucciones de control
        hint_lines = [
            "< / >  Navegar     E / Enter  Comprar     ESC  Cerrar",
        ]
        hint_y = py + ph + 4
        for hl in hint_lines:
            hs = font.render(hl, True, (90, 130, 170))
            surface.blit(hs, (px + pw // 2 - hs.get_width() // 2, hint_y))
            hint_y += lh
