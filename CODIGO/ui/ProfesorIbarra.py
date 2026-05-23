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
import random
from pathlib import Path
import pygame
from narrative.text_renderer import TextRenderer


# ---------------------------------------------------------------------------
# Sistema de progreso del Profesor Ibarra
# ---------------------------------------------------------------------------
class ProgresoIbarra:
    """
    Rastrea cuántas preguntas del Profesor Ibarra ha respondido
    el jugador en el run actual (sin importar si acertó o falló).
    """

    MAX_PREGUNTAS = 5  # Total de preguntas posibles en un run

    def __init__(self):
        self.preguntas_respondidas = 0
        self.respuestas_correctas = 0
        self.preguntas_hechas = set()  # Set de índices de preguntas ya respondidas

    def registrar_respuesta(self, fue_correcta: bool, pregunta_idx: int | None = None) -> None:
        """Registra una respuesta a una pregunta del profesor.

        Args:
            fue_correcta: True si la respuesta fue correcta
            pregunta_idx: Índice de la pregunta en la pool (para evitar repetidas)
        """
        self.preguntas_respondidas += 1
        if fue_correcta:
            self.respuestas_correctas += 1
        if pregunta_idx is not None:
            self.preguntas_hechas.add(pregunta_idx)

    def reset(self) -> None:
        """Reinicia el progreso (llamar al iniciar un nuevo run)."""
        self.preguntas_respondidas = 0
        self.respuestas_correctas = 0
        self.preguntas_hechas = set()

    @property
    def porcentaje(self) -> float:
        """Retorna el porcentaje de preguntas respondidas (0.0 a 1.0)."""
        if self.MAX_PREGUNTAS == 0:
            return 0.0
        return self.preguntas_respondidas / self.MAX_PREGUNTAS

    @property
    def porcentaje_correctas(self) -> float:
        """Retorna el porcentaje de respuestas correctas (0.0 a 1.0)."""
        if self.preguntas_respondidas == 0:
            return 0.0
        return self.respuestas_correctas / self.preguntas_respondidas


# Instancia global del progreso
progreso_ibarra = ProgresoIbarra()


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
        "correcta": 1,
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
        "correcta": 2,
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
        "zona": 0,
        "texto": [
            "¿Por qué no deberías compartir una publicación",
            "ofensiva aunque parezca graciosa?",
        ],
        "opciones": [
            "1. Porque puedes ayudar a que el daño se vuelva más grande.",
            "2. Porque las redes se dañan.",
            "3. Porque pierdes monedas automáticamente.",
        ],
        "correcta": 0,
        "feedback_correcto": [
            "Exacto. Compartir aumenta el alcance del daño.",
            "Detenerlo empieza por no propagarlo.",
        ],
        "feedback_incorrecto": [
            "No es eso. Compartir contenido ofensivo amplifica el daño",
            "real sobre la persona afectada.",
        ],
    },
    {
        "zona": 1,
        "texto": [
            "¿Cuál es la mejor forma de proteger tu privacidad",
            "en redes sociales?",
        ],
        "opciones": [
            "1. Compartir todo públicamente para demostrar confianza.",
            "2. Revisar configuración de privacidad y limitar quién ve tu contenido.",
            "3. No usar redes sociales nunca.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Controlar quién ve tu información es clave",
            "para mantenerte seguro en línea.",
        ],
        "feedback_incorrecto": [
            "No exactamente. Puedes usar redes pero con cuidado.",
            "Revisa tu privacidad regularmente.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "Si alguien te pide enviar fotos íntimas, ¿qué haces?",
        ],
        "opciones": [
            "1. Las envías porque es normal entre amigos.",
            "2. Rechazas, bloqueas y avisas a un adulto.",
            "3. Las envías pero pides que no las compartan.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Tu cuerpo es tuyo. Nunca compartas imágenes íntimas,",
            "aunque confíes en quien las pide.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Ninguna condición es segura.",
            "Aún si confías, las fotos pueden compartirse sin tu consentimiento.",
        ],
    },
    {
        "zona": 0,
        "texto": [
            "¿Qué es el ciberacoso?",
        ],
        "opciones": [
            "1. Solo bromas sin intención de dañar.",
            "2. Acosar, amenazar o humillar a alguien en línea, a menudo de forma repetida.",
            "3. Ignorar mensajes de gente que no conoces.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. El ciberacoso es acoso digital intencional",
            "que causa daño emocional.",
        ],
        "feedback_incorrecto": [
            "No. El ciberacoso es más que bromas.",
            "Es acoso intencional que causa daño real.",
        ],
    },
    {
        "zona": 1,
        "texto": [
            "Si un extraño en línea te dice que eres especial",
            "y quiere ser tu amigo secreto, ¿qué significa?",
        ],
        "opciones": [
            "1. Que realmente le caes bien.",
            "2. Es una estrategia común de depredadores para ganarse tu confianza.",
            "3. Que deberías compartir tu información personal.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Los depredadores usan halagos y secretos para",
            "ganarse la confianza. Avisa a un adulto de inmediato.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Desconfía de extraños que ofrecen amistad especial.",
            "Es una bandera roja de peligro.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "¿Cuál es el riesgo de usar la misma contraseña",
            "en todas tus cuentas?",
        ],
        "opciones": [
            "1. Ninguno, es más fácil de recordar.",
            "2. Si una cuenta es hackeada, todas quedan comprometidas.",
            "3. Las redes sociales lo recomiendan.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Si una contraseña se filtra, los hackers pueden",
            "acceder a TODAS tus cuentas.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Usar contraseñas únicas es más seguro.",
            "Así si una se compromete, las otras siguen protegidas.",
        ],
    },
    {
        "zona": 0,
        "texto": [
            "¿Qué debe hacer si recibes un mensaje amenazante?",
        ],
        "opciones": [
            "1. Responder con más amenazas.",
            "2. Ignorarlo y esperar que se vaya.",
            "3. Guardar evidencia, no responder y reportar a las autoridades.",
        ],
        "correcta": 2,
        "feedback_correcto": [
            "Correcto. Las amenazas son delitos.",
            "Guarda pruebas y reporta a adultos de confianza.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Las amenazas son serias.",
            "Nunca respondas. Busca ayuda de adultos.",
        ],
    },
    {
        "zona": 1,
        "texto": [
            "¿Por qué es peligroso compartir tu ubicación en línea?",
        ],
        "opciones": [
            "1. No es peligroso, todos hacen check-in.",
            "2. Puede permitir que personas malintencionadas te localicen físicamente.",
            "3. Solo es peligroso si eres famoso.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Compartir ubicación puede poner en riesgo tu seguridad física.",
            "Desactiva ubicación en redes sociales.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. La ubicación en línea puede usarse para acosarte.",
            "Es riesgo para cualquiera, no solo famosos.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "¿Qué es el grooming?",
        ],
        "opciones": [
            "1. Arreglarse y verse bien.",
            "2. Cuando un adulto gana confianza de un menor para explotarlo sexualmente.",
            "3. Un juego en línea muy popular.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. El grooming es estrategia de depredadores.",
            "Si esto ocurre, denuncia inmediatamente.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. El grooming es un delito grave.",
            "Un adulto que gana confianza de un menor para explotarlo.",
        ],
    },
    {
        "zona": 0,
        "texto": [
            "Si ves que publican una foto tuya sin permiso, ¿qué haces?",
        ],
        "opciones": [
            "1. Dejas que se viralice, total es gratis publicidad.",
            "2. Reportas la foto y pides que la remuevan.",
            "3. Publicas fotos de esa persona en represalia.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Reportar es lo adecuado.",
            "También puedes avisar a un adulto si es grave.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Tu imagen es tuya. Reporta y busca ayuda.",
            "No represalias, eso empeora las cosas.",
        ],
    },
    {
        "zona": 1,
        "texto": [
            "¿Cuándo es apropiado creer en algo que ves en redes sin verificar?",
        ],
        "opciones": [
            "1. Siempre. Todo en internet es verdad.",
            "2. Nunca. Debes verificar la fuente antes de creer o compartir.",
            "3. Solo si está en mayúsculas.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. La información falsa se propaga rápido.",
            "Siempre verifica antes de compartir.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Mucha desinformación circula en línea.",
            "Antes de creer algo, busca fuentes confiables.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "¿Cuál es un buen indicador de que una app solicita permisos sospechosos?",
        ],
        "opciones": [
            "1. Pide acceso a tu cámara, micrófono y ubicación sin razón clara.",
            "2. Es normal que todas las apps lo hagan.",
            "3. Solo es problema si la app es nueva.",
        ],
        "correcta": 0,
        "feedback_correcto": [
            "Correcto. Si una app pide permisos sin necesidad clara,",
            "rechaza y busca alternativa más segura.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Lee siempre qué permisos solicita una app.",
            "Rechaza si parece innecesario.",
        ],
    },
    {
        "zona": 0,
        "texto": [
            "¿Qué debes hacer si un amigo está siendo acosado?",
        ],
        "opciones": [
            "1. Ignorarlo para no meterte en problemas.",
            "2. Apoyarlo, guardar evidencia y reportar con él.",
            "3. Publicar su historia sin permiso.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. El apoyo es fundamental para víctimas de acoso.",
            "Juntos pueden reportar a las autoridades.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Tu amigo necesita apoyo.",
            "No estar solo es lo más importante.",
        ],
    },
    {
        "zona": 1,
        "texto": [
            "¿Por qué es peligroso aceptar solicitudes de amigos",
            "de personas desconocidas?",
        ],
        "opciones": [
            "1. No es peligroso, es bueno tener muchos amigos.",
            "2. Puede dar acceso a personas malintencionadas a tu información.",
            "3. Solo es peligroso si publicas mucho.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Extraños pueden reunir información para estafarte",
            "o acosarte.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Sé selectivo con tus conexiones.",
            "Solo acepta de gente que realmente conoces.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "¿Qué es una suplantación de identidad en línea?",
        ],
        "opciones": [
            "1. Cuando alguien crea una cuenta falsa pretendiendo ser tú.",
            "2. Un juego de rol inofensivo.",
            "3. Cambiar tu nombre de usuario.",
        ],
        "correcta": 0,
        "feedback_correcto": [
            "Correcto. Alguien suplanta tu identidad para estafar o dañar.",
            "Reporta estas cuentas inmediatamente.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. La suplantación es un delito.",
            "Puede usarse para estafar a tus amigos.",
        ],
    },
    {
        "zona": 0,
        "texto": [
            "¿Cuál es la mejor respuesta ante un comentario hiriente en línea?",
        ],
        "opciones": [
            "1. Responder con otro insulto igual o peor.",
            "2. Ignorar, bloquear y reportar si es grave.",
            "3. Publicar la conversación para que todos lo vean.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. No responder evita escalar el conflicto.",
            "Bloquear elimina el contacto.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Responder agrede más la situación.",
            "Lo mejor es desengancharse.",
        ],
    },
    {
        "zona": 1,
        "texto": [
            "¿Por qué los jóvenes son blanco frecuente de ciberdelincuentes?",
        ],
        "opciones": [
            "1. No lo son, es un mito.",
            "2. Porque suelen ser menos desconfiados y más abiertos en línea.",
            "3. Porque no tienen dinero.",
        ],
        "correcta": 1,
        "feedback_correcto": [
            "Correcto. Los jóvenes son blanco porque pueden ser más confiados.",
            "Por eso es vital que desarrolles habilidades digitales seguras.",
        ],
        "feedback_incorrecto": [
            "Incorrecto. Los jóvenes sí son blanco común.",
            "Por eso es importante estar alerta.",
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
        "descripcion": "Recupera 2 HP. Comprable 3 veces.",
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
        "descripcion": "Invulnerable 5 seg con tecla R.",
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
        "descripcion": "Congela enemigos 4 seg con Q.",
        "icon_color": (255, 220, 60),
        "icon_char": "~",
    },
    {
        "id": "eco_senal",
        "name": "Eco de Señal",
        "price": 90,
        "max_buys": 1,
        "desc_lines": [
            "Tu señal rebota en las redes.",
            "Cada disparo lanza una bala",
            "paralela al mismo tiempo.",
            "",
            "Solo puedes comprarla una vez.",
        ],
        "descripcion": "Doble disparo en paralelo permanente.",
        "icon_color": (255, 140, 40),
        "icon_char": "»",
    },
]


# ---------------------------------------------------------------------------
# Tooltip para items de la tienda
# ---------------------------------------------------------------------------
class ItemTooltip:
    """
    Tooltip que aparece al hacer hover sobre un item de la tienda.
    Se posiciona cerca del cursor sin salirse de la pantalla.
    """

    PADDING = 8  # píxeles lógicos de padding interno
    MAX_WIDTH = 180  # píxeles lógicos de ancho máximo
    BG_COLOR = (15, 15, 25)
    BG_ALPHA = 220
    BORDER_COLOR = (60, 60, 80)
    TEXT_COLOR = (200, 200, 210)
    COLOR_AGOTADO = (120, 60, 60)

    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.visible = False
        self.texto = ""
        self.x = 0
        self.y = 0
        self.color = self.TEXT_COLOR

    def mostrar(self, texto: str, mouse_x: int, mouse_y: int,
                agotado: bool = False) -> None:
        """Muestra el tooltip con el texto dado."""
        self.visible = True
        self.texto = "Agotado" if agotado else texto
        self.color = self.COLOR_AGOTADO if agotado else self.TEXT_COLOR
        self._calcular_posicion(mouse_x, mouse_y)

    def ocultar(self) -> None:
        """Oculta el tooltip."""
        self.visible = False

    def _calcular_posicion(self, mx: int, my: int) -> None:
        """Calcula la posición del tooltip cerca del cursor sin salirse de pantalla."""
        from core.config import Config
        cfg = Config()
        LOGICAL_WIDTH = cfg.SCREEN_W
        LOGICAL_HEIGHT = cfg.SCREEN_H

        offset_x = 15
        offset_y = -10
        self.x = mx + offset_x
        self.y = my + offset_y

        # Ajustar si se sale por la derecha
        ancho_estimado = self.MAX_WIDTH
        if self.x + ancho_estimado > LOGICAL_WIDTH - 10:
            self.x = mx - ancho_estimado - offset_x

        # Ajustar si se sale por arriba
        if self.y < 10:
            self.y = my + 20

    def render(self, surface: pygame.Surface) -> None:
        """Renderiza el tooltip en la superficie."""
        if not self.visible or not self.texto:
            return

        # Renderizar texto con word wrap
        palabras = self.texto.split(" ")
        lineas = []
        linea_actual = ""

        for palabra in palabras:
            prueba = linea_actual + (" " if linea_actual else "") + palabra
            if self.font.size(prueba)[0] <= self.MAX_WIDTH - self.PADDING * 2:
                linea_actual = prueba
            else:
                if linea_actual:
                    lineas.append(linea_actual)
                linea_actual = palabra
        if linea_actual:
            lineas.append(linea_actual)

        line_h = self.font.get_height() + 2
        total_h = len(lineas) * line_h + self.PADDING * 2
        max_w = max(
            (self.font.size(l)[0] for l in lineas), default=0
        ) + self.PADDING * 2

        # Fondo semitransparente
        bg = pygame.Surface((max_w, total_h), pygame.SRCALPHA)
        bg.fill((*self.BG_COLOR, self.BG_ALPHA))
        pygame.draw.rect(bg, self.BORDER_COLOR, (0, 0, max_w, total_h), 1)
        surface.blit(bg, (self.x, self.y))

        # Renderizar texto
        for i, linea in enumerate(lineas):
            txt = self.font.render(linea, False, self.color)
            surface.blit(txt, (
                self.x + self.PADDING,
                self.y + self.PADDING + i * line_h
            ))


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

        # La pregunta se selecciona cuando inicia la interacción
        self.pregunta: dict = {}
        self._pregunta_idx: int = -1

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
        self._item_images_cache: dict[str, pygame.Surface] = {}  # Cache de imágenes

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

        # --- Typewriter effect para feedback ---
        self._text_renderer: TextRenderer | None = None
        self._typewriter_fps: int = 30  # caracteres por segundo

        # --- Tooltip para items de la tienda ---
        # Se inicializa con un font dummy, se actualiza en draw_screen()
        self.tooltip = ItemTooltip(pygame.font.SysFont(None, 14))
        self._item_hover = False  # Rastrea si hay hover activo sobre un item

        # --- Sonido de compra ---
        self._buy_sound = None
        try:
            self._buy_sound = pygame.mixer.Sound("assets/audio/buy_sfx.mp3")
            self._buy_sound.set_volume(0.6)
        except (pygame.error, FileNotFoundError):
            pass  # Sin sonido si no se encuentra

    # ------------------------------------------------------------------
    # Selección de preguntas
    # ------------------------------------------------------------------
    def _seleccionar_pregunta_aleatoria(self) -> None:
        """Selecciona una pregunta aleatoria que no haya sido respondida en este run."""
        preguntas_disponibles = [
            (i, p) for i, p in enumerate(PREGUNTAS)
            if i not in progreso_ibarra.preguntas_hechas
        ]

        if not preguntas_disponibles:
            # Si todas las preguntas fueron hechas, resetear y seleccionar de todas
            preguntas_disponibles = list(enumerate(PREGUNTAS))

        if preguntas_disponibles:
            self._pregunta_idx, self.pregunta = random.choice(preguntas_disponibles)
        else:
            # Fallback: usar la primera pregunta
            self._pregunta_idx = 0
            self.pregunta = PREGUNTAS[0]

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
        """Inicia interacción: hace nueva pregunta o abre tienda si ya respondió.

        Si está en LISTO (cerró tienda), permite nueva pregunta automáticamente.
        """
        # Si está en LISTO, resetear para permitir nueva pregunta
        if self.estado == self.LISTO:
            self.pregunta_respondida = False

        if self.pregunta_respondida:
            # Ya respondió esta pregunta, ir directamente a tienda
            self.estado = self.TIENDA
            self._play_professor_sound()
        else:
            # Primera vez o nueva pregunta: seleccionar pregunta aleatoria
            self._seleccionar_pregunta_aleatoria()
            self.estado = self.PREGUNTA
            self._play_professor_sound()

    def responder(self, opcion_idx: int, player) -> None:
        """Registra la respuesta, otorga recompensa y cambia a FEEDBACK."""
        fue_correcta = opcion_idx == self.pregunta["correcta"]

        if fue_correcta:
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

        # Registrar respuesta en el progreso global (con índice para evitar repetir)
        progreso_ibarra.registrar_respuesta(fue_correcta, self._pregunta_idx)

        # Crear TextRenderer para el efecto typewriter
        # Unir líneas con saltos de línea para renderización
        feedback_text = "\n".join(lines)
        self._text_renderer = TextRenderer(
            feedback_text,
            typewriter_fps=self._typewriter_fps,
            typewriter_sound_path=None  # Sin sonido para feedback
        )

        self.pregunta_respondida = True
        self.estado              = self.FEEDBACK

    def abrir_tienda(self) -> None:
        """Entra al estado TIENDA (carousel)."""
        self.estado = self.TIENDA

    def cerrar_tienda(self) -> None:
        """Cierra la tienda y vuelve a LISTO.
        Permite hacer una nueva pregunta si se interactúa de nuevo."""
        self.estado = self.LISTO
        self._last_msg = ""
        self._msg_timer = 0.0
        # Resetear para permitir nueva pregunta en próxima interacción
        self.pregunta_respondida = False

    def _play_professor_sound(self) -> None:
        """Reproduce un sonido aleatorio del profesor al hablar."""
        try:
            import random
            from pathlib import Path
            # Elegir uno de los tres sonidos aleatoriamente
            sfx_num = random.randint(0, 2)
            sound_path = Path(__file__).parent.parent / "assets" / "audio" / f"shopkeeper_sfx_{sfx_num}.mp3"
            if sound_path.exists():
                sound = pygame.mixer.Sound(str(sound_path))
                sound.set_volume(0.5)
                sound.play()
        except Exception:
            pass

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

        # Reproducir sonido de compra
        if self._buy_sound:
            try:
                self._buy_sound.play()
            except pygame.error:
                pass

    def _apply_item(self, iid: str, player) -> None:
        """Aplica o almacena el efecto del ítem comprado."""
        if iid == "red_apoyo":
            # Se guarda para usar con Z (restaura FULL HP cuando se activa)
            # NO se aplica efecto inmediato - el jugador decide cuándo usarlo
            # Acumula múltiples usos (contador)
            player._ibarra_red_apoyo = getattr(player, "_ibarra_red_apoyo", 0) + 1

        elif iid == "modo_privado":
            # Se guarda para usar con R
            player._ibarra_modo_privado = True

        elif iid == "emp":
            # Se guarda para usar con Q
            player._ibarra_emp = True

        elif iid == "eco_senal":
            # Doble disparo: Player.try_shoot() lo detecta
            player._ibarra_double_shot = True

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
                # Si el typewriter aún está en progreso, completarlo
                if self._text_renderer and not self._text_renderer.is_finished():
                    self._text_renderer.force_finish()
                else:
                    # Si ya terminó, pasar a la tienda
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

        # Actualizar typewriter effect en estado FEEDBACK
        if self.estado == self.FEEDBACK and self._text_renderer:
            self._text_renderer.update(real_dt)

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

    def _get_item_image(self, item_id: str, size: int = 100) -> pygame.Surface | None:
        """Carga la imagen del ítem. Cachea para evitar recargar cada frame."""
        cache_key = f"{item_id}_{size}"
        if cache_key in self._item_images_cache:
            return self._item_images_cache[cache_key]

        img_path = Path(__file__).parent.parent / "assets" / "ui" / f"{item_id}.png"
        if not img_path.exists():
            return None

        try:
            img = pygame.image.load(str(img_path)).convert_alpha()
            img = pygame.transform.smoothscale(img, (size, size))
            self._item_images_cache[cache_key] = img
            return img
        except Exception:
            return None

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

    def update_hover(self, mouse_pos: tuple[int, int], screen_size: tuple[int, int]) -> None:
        """
        Detecta si el mouse está sobre el item actual y actualiza el tooltip.
        Se llama en cada frame cuando la tienda está abierta.
        """
        if self.estado != self.TIENDA:
            self.tooltip.ocultar()
            self._item_hover = False
            return

        mx, my = mouse_pos
        sw, sh = screen_size

        item = IBARRA_CATALOG[self._carousel_idx]
        iid = item["id"]
        bought = self._purchase_counts.get(iid, 0)
        max_buys = item["max_buys"]
        agotado = bought >= max_buys

        # Mostrar tooltip si mouse está en región izquierda del panel (donde está el icono)
        if mx < sw // 2:
            self.tooltip.mostrar(
                item["descripcion"],
                mx, my,
                agotado
            )
            self._item_hover = True
        else:
            self.tooltip.ocultar()
            self._item_hover = False

    def draw_screen(self, screen: pygame.Surface) -> None:
        """Dibuja los paneles de diálogo directamente en el screen surface (encima del HUD)."""
        font = self._get_screen_font()
        screen_size = screen.get_size()

        # Actualizar tooltip si está en tienda
        if self.estado == self.TIENDA:
            try:
                mouse_pos = pygame.mouse.get_pos()
                self.update_hover(mouse_pos, screen_size)
            except Exception as e:
                # Silenciar errores de hover para no romper tienda
                self.tooltip.ocultar()
                self._item_hover = False

        if self.estado == self.PREGUNTA:
            self._draw_question_ui(screen, font)
        elif self.estado == self.FEEDBACK:
            self._draw_feedback_ui(screen, font)
        elif self.estado == self.TIENDA:
            self._draw_tienda_ui(screen, font)
            # Renderizar tooltip al final (encima de todo)
            self.tooltip.render(screen)

    def draw_idle_hint(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        cx, cy = self.pos
        if self.estado == self.LISTO:
            # En LISTO, mostrar que puede hacer otra pregunta
            hint = font.render("E - Otra pregunta", True, (100, 255, 150))
        else:
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

        # Obtener el texto visible del renderer
        if self._text_renderer:
            visible_text = self._text_renderer.current_text()
            visible_lines = visible_text.split("\n")
        else:
            visible_lines = self._feedback_lines

        # Renderizar las líneas visibles con sus colores apropiados
        for line_idx, line in enumerate(visible_lines):
            # Determinar color basado en el contenido de la línea
            if line.startswith("+"):
                color = (100, 255, 140)  # Verde para recompensa
            elif "incorrecto" in line.lower() or "no " in line.lower():
                color = (255, 160, 100)  # Naranja para incorrecto
            else:
                color = (180, 225, 255)  # Azul claro para normal

            surface.blit(font.render(line, True, color), (text_x, y))
            y += lh

        # Mostrar indicador de continuar cuando el typewriter termina
        if self._text_renderer and self._text_renderer.is_finished():
            continue_text = font.render("[Presiona E, Enter o Espacio para continuar]", True, (140, 170, 200))
            surface.blit(continue_text, (text_x, y + 8))


    # --- barra de progreso ---
    def _draw_progress_bar(self, surface: pygame.Surface, font: pygame.font.Font,
                          x: int, y: int) -> None:
        """
        Dibuja la barra de progreso de preguntas respondidas.
        Muestra iconos individuales por cada pregunta (completada/pendiente).
        """
        ICON_SIZE = 14  # píxeles lógicos
        ICON_GAP = 6    # píxeles entre iconos

        total = progreso_ibarra.MAX_PREGUNTAS
        respondidas = progreso_ibarra.preguntas_respondidas

        # Título
        titulo = font.render("Preguntas respondidas", True, (140, 140, 160))
        surface.blit(titulo, (x, y))

        # Iconos de progreso
        icon_y = y + titulo.get_height() + 6

        for i in range(total):
            icon_x = x + i * (ICON_SIZE + ICON_GAP)
            completado = i < respondidas

            # Colores
            color_fill = (76, 175, 80) if completado else (25, 25, 40)
            color_border = (100, 200, 100) if completado else (50, 50, 70)

            # Dibujar cuadrado del icono
            rect = pygame.Rect(icon_x, icon_y, ICON_SIZE, ICON_SIZE)
            pygame.draw.rect(surface, color_fill, rect)
            pygame.draw.rect(surface, color_border, rect, 1)

            # Dibujar checkmark en los completados
            if completado:
                cx = icon_x + ICON_SIZE // 2
                cy = icon_y + ICON_SIZE // 2
                pygame.draw.line(surface, (255, 255, 255),
                               (cx - 3, cy), (cx, cy + 3), 1)
                pygame.draw.line(surface, (255, 255, 255),
                               (cx, cy + 3), (cx + 4, cy - 3), 1)

        # Contador numérico al lado
        contador = font.render(f"{respondidas}/{total}", True, (180, 180, 200))
        surface.blit(contador, (
            x + total * (ICON_SIZE + ICON_GAP) + 8,
            icon_y + 1
        ))

    # --- tienda carousel ---
    def _draw_tienda_ui(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        sw, sh   = surface.get_size()
        lh       = font.get_height() + 4
        desc_lh  = font.get_height() + 3

        # ── Dimensiones ─────────────────────────────────────────────────
        HEADER_H   = 54
        CTRL_BAR_H = 40
        LEFT_W     = 220          # columna izquierda (icono + nav)
        ICON_SIZE  = 100
        max_desc   = max(len(it["desc_lines"]) for it in IBARRA_CATALOG)
        right_content_h = (lh + 10 +           # nombre
                           lh + 8 +            # precio | disponib.
                           8 +                 # separador
                           max_desc * desc_lh + 20 +  # descripcion
                           lh + 8)             # mensaje
        ph = max(HEADER_H + right_content_h + CTRL_BAR_H + 16, 420)
        pw = min(sw - 40, 760)

        px = sw // 2 - pw // 2
        py = sh // 2 - ph // 2

        # ── Panel principal ──────────────────────────────────────────────
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((2, 6, 20, 252))

        # Borde teal doble
        pygame.draw.rect(panel, (0, 185, 235, 255), (0, 0, pw, ph), 2)
        pygame.draw.rect(panel, (0, 80, 120, 100),  (5, 5, pw-10, ph-10), 1)

        # Esquinas L
        C = 20
        cc = (0, 220, 255, 255)
        for cx2, cy2, dx, dy in [(0,0,1,1),(pw,0,-1,1),(0,ph,1,-1),(pw,ph,-1,-1)]:
            pygame.draw.line(panel, cc, (cx2, cy2), (cx2 + dx*C, cy2), 3)
            pygame.draw.line(panel, cc, (cx2, cy2), (cx2, cy2 + dy*C), 3)

        # Línea bajo el header
        pygame.draw.line(panel, (0, 150, 200, 220), (14, HEADER_H), (pw-14, HEADER_H), 1)
        # Diamantes en los extremos
        for ddx in [12, pw-12]:
            pts = [(ddx, HEADER_H-5),(ddx+5,HEADER_H),(ddx,HEADER_H+5),(ddx-5,HEADER_H)]
            pygame.draw.polygon(panel, (0, 200, 250, 220), pts)

        # Divisor vertical columna izquierda
        pygame.draw.line(panel, (0, 100, 145, 160),
                         (LEFT_W, HEADER_H+1), (LEFT_W, ph-CTRL_BAR_H-1), 1)

        # Línea footer
        pygame.draw.line(panel, (0, 90, 130, 150), (14, ph-CTRL_BAR_H), (pw-14, ph-CTRL_BAR_H), 1)

        surface.blit(panel, (px, py))

        # ── Header ───────────────────────────────────────────────────────
        title = font.render("◈  INVENTARIO DEL PROFESOR IBARRA  ◈", True, (0, 230, 255))
        surface.blit(title, (px + pw//2 - title.get_width()//2,
                              py + HEADER_H//2 - title.get_height()//2))

        # ── Datos del ítem ───────────────────────────────────────────────
        item      = IBARRA_CATALOG[self._carousel_idx]
        iid       = item["id"]
        bought    = self._purchase_counts.get(iid, 0)
        max_buys  = item["max_buys"]
        remaining = max_buys - bought
        exhausted = remaining <= 0
        icon_col  = item["icon_color"] if not exhausted else (50, 52, 62)
        arr_col   = (70, 185, 235) if not exhausted else (45, 58, 75)

        # ────────────────── COLUMNA IZQUIERDA ──────────────────────────
        left_cx = px + LEFT_W // 2          # centro horizontal izq
        body_top = py + HEADER_H + 1
        body_h   = ph - HEADER_H - CTRL_BAR_H - 2
        icon_y   = body_top + body_h // 2 - ICON_SIZE // 2 - 18

        # Halo del icono
        if not exhausted:
            halo = pygame.Surface((ICON_SIZE+32, ICON_SIZE+32), pygame.SRCALPHA)
            pygame.draw.rect(halo, (*icon_col, 28), (0,0,ICON_SIZE+32,ICON_SIZE+32),
                             border_radius=18)
            surface.blit(halo, (left_cx - (ICON_SIZE+32)//2, icon_y-16))

        # Icono — intenta cargar PNG, fallback a cuadrado coloreado
        img = self._get_item_image(item["id"], ICON_SIZE)
        if img:
            # Usar imagen del ítem
            surface.blit(img, (left_cx - ICON_SIZE//2, icon_y))
        else:
            # Fallback: cuadrado coloreado con letra
            icon_sf = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
            pygame.draw.rect(icon_sf, (*icon_col, 225), (0,0,ICON_SIZE,ICON_SIZE), border_radius=14)
            pygame.draw.rect(icon_sf, (255,255,255,170), (0,0,ICON_SIZE,ICON_SIZE), 2, border_radius=14)
            # Reflejo sutil en la esquina superior
            shine = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
            pygame.draw.rect(shine, (255,255,255,22), (4,4,ICON_SIZE-8,ICON_SIZE//3), border_radius=10)
            icon_sf.blit(shine, (0,0))
            try:
                ifont = pygame.font.SysFont(None, 64)
            except Exception:
                ifont = font
            ch = ifont.render(item["icon_char"], True, (255,255,255))
            icon_sf.blit(ch, (ICON_SIZE//2-ch.get_width()//2, ICON_SIZE//2-ch.get_height()//2))
            surface.blit(icon_sf, (left_cx - ICON_SIZE//2, icon_y))

        # Overlay de hover semitransparente
        if self._item_hover and not exhausted:
            overlay = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, 30))
            surface.blit(overlay, (left_cx - ICON_SIZE//2, icon_y))

        # Overlay de agotado (más oscuro)
        if exhausted:
            overlay = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 80))
            surface.blit(overlay, (left_cx - ICON_SIZE//2, icon_y))

        # Flechas
        arr_y = icon_y + ICON_SIZE // 2 - lh // 2
        la = font.render("◀", True, arr_col)
        ra = font.render("▶", True, arr_col)
        surface.blit(la, (px + 10, arr_y))
        surface.blit(ra, (px + LEFT_W - ra.get_width() - 10, arr_y))

        # Índice numérico  "2 / 4"
        idx_str  = f"{self._carousel_idx+1} / {len(IBARRA_CATALOG)}"
        idx_surf = font.render(idx_str, True, (60, 130, 165))
        surface.blit(idx_surf, (left_cx - idx_surf.get_width()//2, icon_y + ICON_SIZE + 8))

        # Dots
        n = len(IBARRA_CATALOG)
        ds = 16
        dot_y = icon_y + ICON_SIZE + 8 + lh + 4
        dx0 = left_cx - (n * ds) // 2
        for i in range(n):
            dcx = dx0 + i * ds + ds // 2
            if i == self._carousel_idx:
                pygame.draw.circle(surface, (0, 210, 255), (dcx, dot_y), 5)
                pygame.draw.circle(surface, (0, 180, 220, 90), (dcx, dot_y), 9, 1)
            else:
                pygame.draw.circle(surface, (35, 65, 95), (dcx, dot_y), 3)

        # ────────────────── COLUMNA DERECHA ────────────────────────────
        rx   = px + LEFT_W + 18
        rw   = pw - LEFT_W - 32
        ry   = body_top + 18

        # ── Badge de estado ─────────────────────────────────────────────
        if exhausted:
            badge_txt = "AGOTADO"
            badge_bg  = (120, 20, 20, 180)
            badge_fg  = (255, 80, 80)
        elif remaining == max_buys:
            badge_txt = "DISPONIBLE"
            badge_bg  = (10, 80, 40, 180)
            badge_fg  = (60, 220, 120)
        else:
            badge_txt = f"{remaining} RESTANTE{'S' if remaining!=1 else ''}"
            badge_bg  = (20, 70, 110, 180)
            badge_fg  = (80, 190, 240)

        b_surf = font.render(badge_txt, True, badge_fg)
        b_pw   = b_surf.get_width() + 18
        b_ph   = b_surf.get_height() + 6
        badge  = pygame.Surface((b_pw, b_ph), pygame.SRCALPHA)
        badge.fill(badge_bg)
        pygame.draw.rect(badge, (*badge_fg, 180), (0,0,b_pw,b_ph), 1)
        badge.blit(b_surf, (9, 3))
        surface.blit(badge, (rx + rw - b_pw, ry))

        # ── Nombre ──────────────────────────────────────────────────────
        name_col  = (255, 255, 210) if not exhausted else (95, 95, 85)
        name_surf = font.render(item["name"], True, name_col)
        surface.blit(name_surf, (rx, ry + b_ph + 6))
        ry += b_ph + 6 + lh

        # Línea bajo el nombre
        pygame.draw.line(surface, (0, 100, 140, 130), (rx, ry+2), (rx+rw, ry+2), 1)
        ry += 10

        # ── Precio ──────────────────────────────────────────────────────
        price_col = (255, 215, 40) if not exhausted else (70, 70, 60)
        coin_surf = font.render("⬡", True, price_col)
        amt_surf  = font.render(f" {item['price']} microchips", True, price_col)
        surface.blit(coin_surf, (rx, ry))
        surface.blit(amt_surf,  (rx + coin_surf.get_width(), ry))
        ry += lh + 10

        # ── Panel descripción ────────────────────────────────────────────
        desc_lines = item["desc_lines"]
        d_ph = len(desc_lines) * desc_lh + 18
        desc_bg = pygame.Surface((rw, d_ph), pygame.SRCALPHA)
        desc_bg.fill((5, 14, 38, 215))
        pygame.draw.rect(desc_bg, (0, 105, 155, 170), (0, 0, rw, d_ph), 1)
        # Acento izquierdo de color
        pygame.draw.rect(desc_bg, (*icon_col, 180), (0, 0, 3, d_ph))
        surface.blit(desc_bg, (rx, ry))

        dy = ry + 9
        for line in desc_lines:
            if line:
                dl = font.render(line, True, (160, 208, 255))
                surface.blit(dl, (rx + 10, dy))
            dy += desc_lh
        ry += d_ph + 10

        # ── Mensaje temporal ─────────────────────────────────────────────
        if self._last_msg:
            mc  = (70, 255, 130) if "Comprado" in self._last_msg else (255, 80, 80)
            ms  = font.render(self._last_msg, True, mc)
            surface.blit(ms, (rx, ry))

        # ── Barra de progreso de preguntas ───────────────────────────────
        # Posicionar dentro del panel, cerca del footer (más abajo)
        self._draw_progress_bar(surface, font, px + 20, py + ph - CTRL_BAR_H - 55)

        # ── Barra de controles ───────────────────────────────────────────
        ctrl_y = py + ph - CTRL_BAR_H + (CTRL_BAR_H - lh) // 2
        ctrls  = [("◀ / ▶", "Navegar"), ("E / Enter", "Comprar"), ("ESC", "Cerrar")]
        sep    = font.render("  ·  ", True, (30, 58, 85))
        parts: list[tuple] = [
            (font.render(k, True, (0, 190, 230)),
             font.render(f" {a}", True, (105, 140, 170)))
            for k, a in ctrls
        ]
        tot_w = sum(k.get_width() + a.get_width() for k,a in parts) + sep.get_width()*(len(parts)-1)
        cx2   = px + pw//2 - tot_w//2
        for i, (ks, as_) in enumerate(parts):
            surface.blit(ks,  (cx2, ctrl_y)); cx2 += ks.get_width()
            surface.blit(as_, (cx2, ctrl_y)); cx2 += as_.get_width()
            if i < len(parts)-1:
                surface.blit(sep, (cx2, ctrl_y)); cx2 += sep.get_width()
