from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

from Config import Config
from Statistics import StatisticsManager
from ui.lobby_screen import PantallaLobby


@dataclass(frozen=True)
class StartMenuResult:
    """Resultado devuelto por el menú de inicio."""
    start_game: bool
    seed: Optional[int]
    skin_path: Optional[str]
    modo_coop: bool = False  # True si se inició en modo co-op (con cliente conectado)


class StartMenu:
    """Pantalla de inicio configurable (CyberQuest Edition)."""

    BUTTON_PADDING_X = 32
    BUTTON_PADDING_Y = 14
    BUTTON_GAP = 8
    INPUT_WIDTH  = 380
    INPUT_HEIGHT = 48

    # Botones con tamaño fijo respetando el ratio del sprite (1080×335 ≈ 3.22:1)
    BUTTON_FIXED_W = 340
    BUTTON_FIXED_H = 106   # 340 / 3.22 ≈ 106

    # Paleta GHOSTED — crimson / rojo
    COLOR_CRIMSON     = (210, 35, 55)      # rojo carmesí principal
    COLOR_EMBER       = (255, 110, 50)     # naranja-rojo ember (hover/activo)
    COLOR_DARK_BG     = (8, 3, 6)         # fondo casi negro rojizo
    COLOR_GRID        = (28, 8, 12)        # grilla oscura carmesí
    COLOR_TEXT_WHITE  = (230, 218, 218)    # blanco cálido

    # Aliases para compatibilidad con código existente (overlays, slider, etc.)
    COLOR_TEAL        = COLOR_CRIMSON
    COLOR_HOVER_TEXT  = COLOR_EMBER
    COLOR_NEON_BLUE   = COLOR_CRIMSON
    COLOR_NEON_PINK   = COLOR_EMBER

    def __init__(
        self,
        screen: pygame.Surface,
        cfg: Config,
        *,
        stats_manager: StatisticsManager | None = None,
    ) -> None:
        self.screen = screen
        self.cfg = cfg
        self.menu_cfg = cfg.START_MENU
        
        pygame.display.set_caption("GHOSTED")
        self.clock = pygame.time.Clock()

        # --- GESTIÓN DE RUTAS ---
        # __file__ es CODIGO/ui/StartMenu.py → .parent.parent = CODIGO/
        self.base_dir = Path(__file__).parent.parent.resolve()
        self.ui_assets_dir = self.base_dir / "assets" / "ui"
        self.audio_assets_dir = self.base_dir / "assets" / "audio"

        print(f"--- DEBUG START MENU ---")
        print(f"Assets UI: {self.ui_assets_dir}")
        print(f"Assets Audio: {self.audio_assets_dir}")

        # --- Volumen ---
        self.volume: float = (
            pygame.mixer.music.get_volume() if pygame.mixer.get_init() else 0.01
        )
        self.dragging_volume = False
        self.VOLUME_BAR_SIZE = (360, 10)
        self.VOLUME_HANDLE_SIZE = (18, 26)
        self.volume_bar_rect = pygame.Rect(0, 0, *self.VOLUME_BAR_SIZE)
        self.volume_handle_rect = pygame.Rect(0, 0, *self.VOLUME_HANDLE_SIZE)

        # --- Inicializar Audio ---
        self._init_audio()

        # --- Carga de Fuentes ---
        self.title_font = self._get_font("VT323-Regular.ttf", 96)
        self.subtitle_font = self._get_font("VT323-Regular.ttf", 42)
        self.button_font = self._get_font("VT323-Regular.ttf", 48)
        self.small_font = self._get_font("VT323-Regular.ttf", 32)

        self.seed_text: str = ""
        self.input_active = False

        self.overlay_key: Optional[str] = None
        self.overlay_lines: tuple[str, ...] = ()
        self.stats_manager = stats_manager

        # --- Skins ---
        self.skin_options = self._build_skin_options()
        self.selected_skin_id = self._infer_default_skin_id()
        self.selected_body, self.selected_color = self._split_skin_id(self.selected_skin_id)
        self.body_cards: list[tuple[str, pygame.Rect]] = []
        self.color_rects: list[tuple[str, pygame.Rect]] = []
        self.skins_overlay_rect = pygame.Rect(0, 0, 0, 0)
        self.preview_anim_time = 0.0
        self.preview_cache: dict[tuple[str, str], list[pygame.Surface]] = {}

        self.button_rects: list[tuple[str, pygame.Rect]] = []
        self.seed_rect = pygame.Rect(0, 0, self.INPUT_WIDTH, self.INPUT_HEIGHT)

        # --- Carga de Fondo ---
        self.background    = self._load_image("FondoMenuPrincipal.png")
        self.btn_normal    = self._load_image("Boton_normal.png")
        self.btn_hover     = self._load_image("Boton_hover.png")
        
        if not self.background and self.menu_cfg.background_image:
             path_cfg = Path(self.menu_cfg.background_image)
             if path_cfg.exists():
                 try:
                    self.background = pygame.image.load(str(path_cfg)).convert_alpha()
                 except:
                     pass

        self.logo = self._load_image(self.menu_cfg.logo_image)
        self.credits_image = self._load_image("Creditos.png")
        self.controls_image = self._load_image("panel_controles.png")

        self._compute_layout()
        self._start_requested = False

        # --- Pantalla de Lobby (co-op) ---
        self.lobby: PantallaLobby | None = None
        self.net_manager = None  # Se asignará desde Game.py para detectar P2
        self.servidor_menu = None  # Se asignará desde Main.py si modo=servidor
        self.cliente_menu = None  # Se asignará desde Main.py si modo=cliente
        self.player_ref = None  # Se asignará desde Game.py para obtener animación idle
        self.modo_coop_solicitado = False  # Flag para indicar si inició en co-op

    def _init_audio(self) -> None:
        """Inicializa el mixer, carga efectos y arranca la música."""
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except pygame.error:
                print("No se pudo inicializar el módulo de audio.")
                return

        self.click_sound = self._load_sound("boton.mp3")

        music_file = "music_menu.mp3"
        music_path = self._get_audio_path(music_file)
        
        if music_path and music_path.exists():
            try:
                pygame.mixer.music.load(str(music_path))
                pygame.mixer.music.set_volume(0.01)
                pygame.mixer.music.play(-1)
                print(f"Reproduciendo música: {music_file}")
            except Exception as e:
                print(f"Error reproduciendo música {music_file}: {e}")
        else:
            print(f"No se encontró música: {music_path}")

        self._apply_volume()

    def _get_audio_path(self, filename: str) -> Path | None:
        """Busca archivos de audio en assets/audio."""
        candidates = [
            self.audio_assets_dir / filename,
            self.base_dir / "assets" / "audio" / filename,
            Path.cwd() / "assets" / "audio" / filename
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_sound(self, filename: str) -> pygame.mixer.Sound | None:
        path = self._get_audio_path(filename)
        if path:
            try:
                return pygame.mixer.Sound(str(path))
            except Exception as e:
                print(f"Error cargando SFX {filename}: {e}")
        return None

    def _play_click(self) -> None:
        """Helper para reproducir el sonido de click si existe."""
        if self.click_sound:
            self.click_sound.play()

    def _get_path(self, filename: str) -> Path:
        return self.ui_assets_dir / filename

    def _get_font(self, font_name: str, size: int) -> pygame.font.Font:
        font_path = self._get_path(font_name)
        if font_path.exists():
            try:
                return pygame.font.Font(str(font_path), size)
            except Exception as e:
                print(f"Error cargando fuente {font_name}: {e}")
        return pygame.font.SysFont("consolas", int(size * 0.7))

    def _load_image(self, filename: Optional[str]) -> Optional[pygame.Surface]:
        if not filename: return None
        clean_name = Path(filename).name
        image_path = self._get_path(clean_name)

        if not image_path.exists():
            return None

        try:
            image = pygame.image.load(str(image_path)).convert_alpha()
            return image
        except Exception:
            return None

    def _load_logo_title(self) -> Optional[pygame.Surface]:
        """Carga el logo GHOSTED desde assets/ui/logo_ghosted.png"""
        if not hasattr(self, "_logo_title_cache"):
            self._logo_title_cache = None
            image_path = Path(__file__).parent.parent / "assets" / "ui" / "logo_ghosted.png"
            if image_path.exists():
                try:
                    self._logo_title_cache = pygame.image.load(str(image_path)).convert_alpha()
                except Exception:
                    pass
        return self._logo_title_cache

    def _compute_layout(self) -> None:
        width, height = self.screen.get_size()
        center_x = width // 2

        self.button_rects.clear()

        if not self.menu_cfg.buttons:
            self.seed_rect.center = (center_x, height // 2)
            layout_bottom = self.seed_rect.bottom
        else:
            button_width  = self.BUTTON_FIXED_W
            button_height = self.BUTTON_FIXED_H

            total_height = len(self.menu_cfg.buttons) * button_height + (
                (len(self.menu_cfg.buttons) - 1) * self.BUTTON_GAP
            )

            start_y = height // 2 - total_height // 2 + 40

            for button in self.menu_cfg.buttons:
                rect = pygame.Rect(0, 0, button_width, button_height)
                rect.centerx = center_x
                rect.y = start_y
                self.button_rects.append((button.action, rect))
                start_y += button_height + self.BUTTON_GAP

            self.seed_rect.size = (self.INPUT_WIDTH, self.INPUT_HEIGHT)
            self.seed_rect.centerx = center_x
            self.seed_rect.y = start_y + 20
            layout_bottom = self.seed_rect.bottom

        self._position_volume_slider(center_x, layout_bottom)

    def _build_skin_options(self) -> list[dict[str, str]]:
        color_names = {
            "blue": "Azul",
            "red": "Rojo",
            "green": "Verde",
            "grey": "Gris",
        }
        body_names = {"flaco": "CYBER-067", "gordo": "CYBER-021"}
        base = Path("assets") / "player"
        options: list[dict[str, str]] = []
        for body in ("flaco", "gordo"):
            for color in ("blue", "red", "green", "grey"):
                skin_id = f"{color}_{body}"
                options.append(
                    {
                        "id": skin_id,
                        "label": f"{color_names[color]} {body_names[body]}",
                        "color": color_names[color],
                        "body": body_names[body],
                        "path": str(base / skin_id),
                    }
                )
        return options

    def _infer_default_skin_id(self) -> str:
        default = "blue_flaco"
        current = getattr(self.cfg, "PLAYER_SPRITES_PATH", None)
        if current:
            candidate = Path(current).name
            if any(option["id"] == candidate for option in self.skin_options):
                return candidate
        return default

    def _select_skin(self, skin_id: str) -> None:
        if any(option["id"] == skin_id for option in self.skin_options):
            self.selected_skin_id = skin_id
            self.selected_body, self.selected_color = self._split_skin_id(skin_id)

    def _split_skin_id(self, skin_id: str) -> tuple[str, str]:
        if "_" in skin_id:
            color, body = skin_id.split("_", 1)
            return body, color
        return "flaco", "blue"

    def _update_selected_skin(self) -> None:
        self.selected_skin_id = f"{self.selected_color}_{self.selected_body}"

    def selected_skin_path(self) -> str:
        match = next((opt for opt in self.skin_options if opt["id"] == self.selected_skin_id), None)
        if match:
            return match["path"]
        return str(Path("assets") / "player" / self.selected_skin_id)

    def _position_volume_slider(self, center_x: int, layout_bottom: int) -> None:
        slider_y = layout_bottom + 70
        self.volume_bar_rect.centerx = center_x
        self.volume_bar_rect.y = slider_y
        self._update_volume_handle_pos()

    def _update_volume_handle_pos(self) -> None:
        ratio = max(0.0, min(1.0, self.volume))
        handle_x = self.volume_bar_rect.left + ratio * self.volume_bar_rect.width
        self.volume_handle_rect.center = (
            int(handle_x),
            self.volume_bar_rect.centery,
        )

    def run(self) -> StartMenuResult:
        running = True
        while running:
            dt = self.clock.tick(self.cfg.FPS) / 1000.0
            self.preview_anim_time = (self.preview_anim_time + dt) % 9999

            # ================================================================
            # SINCRONIZACIÓN CON RED DEL MENÚ (CLIENTE)
            # ================================================================
            if self.cliente_menu:
                # Procesar mensajes del servidor
                self.cliente_menu.procesar_mensajes_pendientes()

                # Si el servidor ordenó iniciar el juego (thread-safe con lock)
                debe_iniciar = False
                seed_servidor = None
                with self.cliente_menu.lock:
                    debe_iniciar = self.cliente_menu.iniciar_juego
                    seed_servidor = self.cliente_menu.seed_juego
                    if debe_iniciar:
                        self.cliente_menu.iniciar_juego = False

                if debe_iniciar:
                    self.modo_coop_solicitado = True
                    self._start_requested = True
                    running = False
                    # Usar seed del servidor
                    if seed_servidor is not None:
                        self.seed_text = str(seed_servidor)
                    break

                # Sincronizar pantalla actual con servidor
                pantalla_del_servidor = self.cliente_menu.pantalla_actual
                if pantalla_del_servidor == "conectando":
                    # Mostrar pantalla de conexión
                    self._draw_menu()
                    # Dibujar overlay "Conectando..."
                    self._draw_connecting_overlay()
                    pygame.display.flip()
                    continue
                elif pantalla_del_servidor == "sin_conexion":
                    # Mostrar error de conexión
                    self._draw_menu()
                    self._draw_connection_error_overlay()
                    pygame.display.flip()
                    continue
                # Si está "principal", "lobby", etc., continuar normalmente

            # ================================================================
            # ACTUALIZAR LOBBY
            # ================================================================
            if self.lobby:
                try:
                    self.lobby.update(dt)

                    # Actualizar estado de conexión P2 en tiempo real
                    if self.net_manager:
                        try:
                            p2_conectado = "aliado" in self.net_manager.roles_conectados()
                            self.lobby.set_p2_conectado(p2_conectado)
                        except Exception as e:
                            print(f"[MENU] Error actualizando estado P2: {e}")
                except Exception as e:
                    print(f"[MENU] Error actualizando lobby: {e}")
                    import traceback
                    traceback.print_exc()

            # ================================================================
            # MANEJO DE EVENTOS
            # ================================================================
            es_cliente = self._es_cliente()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._start_requested = False
                    running = False
                    break

                # SIEMPRE permitir ESC para salir
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._start_requested = False
                    running = False
                    break

                # Si es cliente conectado, bloquear TODOS los otros eventos
                if es_cliente:
                    # Cliente solo puede presionar ESC (ya manejado arriba)
                    # Ignorar absolutamente todos los otros eventos
                    continue

                # Si no es cliente, procesar eventos normalmente
                if self.overlay_key == "lobby" and self.lobby:
                    # Manejar eventos del lobby
                    self.lobby.handle_event(event)
                elif self.overlay_key:
                    if self.overlay_key == "skins":
                        keep_running = self._handle_skins_event(event)
                    else:
                        keep_running = self._handle_overlay_event(event)
                    if not keep_running:
                        running = False
                        break
                else:
                    # Servidor o sin red: manejo normal
                    keep_running = self._handle_menu_event(event)
                    if not keep_running:
                        running = False
                        break

            if not running:
                break

            # ================================================================
            # PROCESAR RESULTADO DEL LOBBY
            # ================================================================
            try:
                if self.lobby and self.lobby.terminado:
                    # Solo el servidor puede terminar el lobby (cliente tiene eventos bloqueados)
                if self.lobby.resultado == "jugar":
                    # SERVIDOR: Iniciar juego
                    self.modo_coop_solicitado = self.lobby.p2_conectado
                    self.overlay_key = None

                    seed = self.selected_seed()
                    import random
                    if seed is None:
                        seed = random.randint(0, 999999)
                    self.seed_text = str(seed)

                    # Enviar START_GAME y esperar ACK del cliente (si hay cliente conectado)
                    if self.servidor_menu and self.servidor_menu.cliente_conectado:
                        print(f"[SERVIDOR] Enviando START_GAME con seed {seed}...")
                        cliente_listo = self.servidor_menu.enviar_inicio_juego(seed, timeout=5.0)

                        if cliente_listo:
                            print("[SERVIDOR] ✓ Cliente confirmó, iniciando juego...")
                        else:
                            print("[SERVIDOR] ⚠ Timeout esperando confirmación del cliente, iniciando igualmente...")
                            # Esperar un poco de todas formas
                            import time
                            time.sleep(1.0)
                    else:
                        print("[SERVIDOR] Iniciando juego (sin cliente conectado)")

                    self._start_requested = True
                    running = False

                elif self.lobby.resultado == "volver":
                    # Volver al menú principal
                    self.lobby = None
                    self.overlay_key = None
                    # Notificar al cliente (servidor)
                    if self.servidor_menu:
                        try:
                            self.servidor_menu.enviar_estado_menu("principal")
                        except Exception as e:
                            print(f"[MENU] Error notificando estado: {e}")
            except Exception as e:
                print(f"[MENU] Error procesando lobby: {e}")
                import traceback
                traceback.print_exc()

            # ================================================================
            # RENDERIZAR
            # ================================================================
            # Si es cliente conectado, renderizar según lo que dice el servidor
            if self.cliente_menu and self.cliente_menu.conectado:
                pantalla_actual = self.cliente_menu.pantalla_actual

                # Mapear nombres en inglés (del servidor) a español
                pantalla_mapeada = {
                    "credits": "creditos",
                    "statistics": "estadisticas",
                    "controls": "controls",  # ya en inglés pero consistente
                }.get(pantalla_actual, pantalla_actual)

                if pantalla_mapeada == "lobby":
                    # Renderizar lobby
                    if not self.lobby:
                        # Crear lobby si no existe
                        try:
                            width, height = self.screen.get_size()
                            self.lobby = PantallaLobby(
                                logical_w=width,
                                logical_h=height,
                                fondo_menu=self.background,
                                btn_asset=self.btn_normal,
                                anim_p1=None,
                            )
                            if self.net_manager:
                                try:
                                    p2_conectado = "aliado" in self.net_manager.roles_conectados()
                                    self.lobby.set_p2_conectado(p2_conectado)
                                except Exception as e:
                                    print(f"[MENU] Error detectando P2 en lobby: {e}")
                        except Exception as e:
                            print(f"[MENU] Error creando lobby: {e}")
                            import traceback
                            traceback.print_exc()

                    if self.lobby:
                        try:
                            self.lobby.render(self.screen)
                        except Exception as e:
                            print(f"[MENU] Error renderizando lobby: {e}")
                            import traceback
                            traceback.print_exc()

                elif pantalla_mapeada in ["creditos", "controls", "estadisticas", "skins"]:
                    # Renderizar overlay
                    self._draw_menu(dim_background=True)
                    # Mapear nombre del overlay para _draw_overlay
                    self.overlay_key = pantalla_mapeada
                    self.overlay_lines = ()
                    if pantalla_mapeada == "creditos" and hasattr(self, 'menu_cfg') and hasattr(self.menu_cfg, 'sections'):
                        self.overlay_lines = self.menu_cfg.sections.get("creditos", [])[1:] if self.menu_cfg.sections.get("creditos") else ()
                    elif pantalla_mapeada == "controls" and hasattr(self, 'menu_cfg') and hasattr(self.menu_cfg, 'sections'):
                        self.overlay_lines = self.menu_cfg.sections.get("controls", ())
                    elif pantalla_mapeada == "estadisticas":
                        self.overlay_lines = self._statistics_lines()
                    self._draw_overlay()

                else:  # "principal" o cualquier otra
                    # Renderizar menú principal
                    self._draw_menu()
            else:
                # Servidor o sin red: renderizar según overlay_key local
                if self.overlay_key == "lobby" and self.lobby:
                    self.lobby.render(self.screen)
                elif self.overlay_key:
                    self._draw_menu(dim_background=True)
                    if self.overlay_key == "skins":
                        self._draw_skins_overlay()
                    else:
                        self._draw_overlay()
                else:
                    self._draw_menu()

            pygame.display.flip()

        if self._start_requested:
            pygame.mixer.music.fadeout(500)
            return StartMenuResult(
                start_game=True,
                seed=self.selected_seed(),
                skin_path=self.selected_skin_path(),
                modo_coop=self.modo_coop_solicitado,
            )

        return StartMenuResult(start_game=False, seed=None, skin_path=None, modo_coop=False)
        # CONTINÚA DESPUÉS DE def run()...

    def _handle_menu_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._start_requested = False
                return False
            if event.key == pygame.K_RETURN:
                self._play_click()
                return self._mostrar_lobby()
            if event.key == pygame.K_BACKSPACE:
                self.seed_text = self.seed_text[:-1]
            else:
                if event.unicode and event.unicode.isdigit():
                    if len(self.seed_text) < 16:
                        self.seed_text += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._is_over_volume(event.pos):
                self.dragging_volume = True
                self._set_volume_from_mouse(event.pos[0])
                return True
            if self.seed_rect.collidepoint(event.pos):
                self.input_active = True
            else:
                self.input_active = False
                for action, rect in self.button_rects:
                    if rect.collidepoint(event.pos):
                        self._play_click()
                        return self._trigger_button(action)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_volume = False
        elif event.type == pygame.MOUSEMOTION and self.dragging_volume:
            self._set_volume_from_mouse(event.pos[0])
        return True

    def _handle_overlay_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_ESCAPE,
            pygame.K_RETURN,
            pygame.K_BACKSPACE,
        ):
            self.overlay_key = None
            # Notificar al cliente que volvemos al menú principal (servidor)
            if self.servidor_menu:
                self.servidor_menu.enviar_estado_menu("principal")
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.overlay_key = None
            # Notificar al cliente que volvemos al menú principal (servidor)
            if self.servidor_menu:
                self.servidor_menu.enviar_estado_menu("principal")
            return True
        if event.type == pygame.QUIT:
            self._start_requested = False
            return False
        return True

    def _handle_skins_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_ESCAPE,
            pygame.K_RETURN,
            pygame.K_BACKSPACE,
        ):
            self.overlay_key = None
            # Notificar al cliente que volvemos al menú principal (servidor)
            if self.servidor_menu:
                self.servidor_menu.enviar_estado_menu("principal")
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hasattr(self, 'confirm_button_rect') and self.confirm_button_rect.collidepoint(event.pos):
                self._play_click()
                self.overlay_key = None
                # Notificar al cliente que volvemos al menú principal (servidor)
                if self.servidor_menu:
                    self.servidor_menu.enviar_estado_menu("principal")
                return True

            if (
                self.skins_overlay_rect.width
                and self.skins_overlay_rect.height
                and not self.skins_overlay_rect.collidepoint(event.pos)
            ):
                self.overlay_key = None
                # Notificar al cliente que volvemos al menú principal (servidor)
                if self.servidor_menu:
                    self.servidor_menu.enviar_estado_menu("principal")
                return True
            for body, rect in self.body_cards:
                if rect.collidepoint(event.pos):
                    self._play_click()
                    self.selected_body = body
                    self._update_selected_skin()
                    return True
            for color, rect in self.color_rects:
                if rect.collidepoint(event.pos):
                    self._play_click()
                    self.selected_color = color
                    self._update_selected_skin()
                    return True
        if event.type == pygame.QUIT:
            self._start_requested = False
            return False
        return True

    def _trigger_button(self, action: str) -> bool:
        if action == "play":
            # En lugar de ir directo al juego, mostrar pantalla de lobby
            return self._mostrar_lobby()
        if action == "skins":
            self.overlay_key = action
            self.overlay_lines = ()
            # Notificar al cliente (servidor)
            if self.servidor_menu:
                self.servidor_menu.enviar_estado_menu("skins")
            return True
        if action == "credits" or action == "controls":
            if action in self.menu_cfg.sections:
                self.overlay_key = action
                section_lines = self.menu_cfg.sections[action]
                if action == "credits":
                    self.overlay_lines = section_lines[1:] if section_lines else ()
                else:
                    self.overlay_lines = section_lines
                # Notificar al cliente (servidor)
                if self.servidor_menu:
                    self.servidor_menu.enviar_estado_menu(action)
                return True
        if action == "statistics":
            self.overlay_key = action
            self.overlay_lines = self._statistics_lines()
            # Notificar al cliente (servidor)
            if self.servidor_menu:
                self.servidor_menu.enviar_estado_menu("estadisticas")
            return True
        if action in self.menu_cfg.sections:
            self.overlay_key = action
            self.overlay_lines = self.menu_cfg.sections[action]
            # Notificar al cliente (servidor)
            if self.servidor_menu:
                self.servidor_menu.enviar_estado_menu(action)
            return True
        if action == "quit":
            return False

        self.overlay_key = action
        self.overlay_lines = (
            f"Acción '{action}' sin comportamiento.",
            "Edita Config.START_MENU.",
        )
        return True

    def _commit_play(self) -> bool:
        self._start_requested = True
        self.overlay_key = None
        return False

    def set_net_manager(self, net_manager) -> None:
        """Establece el gestor de red para detectar clientes conectados."""
        self.net_manager = net_manager

    def set_servidor_menu(self, servidor_menu) -> None:
        """Establece el servidor del menú (modo SERVIDOR)."""
        self.servidor_menu = servidor_menu

    def set_cliente_menu(self, cliente_menu) -> None:
        """Establece el cliente del menú (modo CLIENTE)."""
        self.cliente_menu = cliente_menu

    def set_player_animation(self, player) -> None:
        """Almacena la referencia al jugador para obtener su animación idle."""
        self.player_ref = player

    def _es_cliente(self) -> bool:
        """Determina si este proceso es un cliente (no puede controlar el menú)."""
        # Verificar si hay cliente_menu conectado
        if self.cliente_menu and self.cliente_menu.conectado:
            return True
        # Verificar si hay net_manager en modo cliente
        if self.net_manager and hasattr(self.net_manager, '_modo'):
            if self.net_manager._modo == "cliente":
                return True
        return False

    def _mostrar_lobby(self) -> bool:
        """Crea y muestra la pantalla de lobby."""
        width, height = self.screen.get_size()

        # Obtener animación idle de P1
        anim_p1 = None
        if self.player_ref and hasattr(self.player_ref, "animations"):
            anim_p1 = self.player_ref.animations.get("idle")
            print(f"[LOBBY] Player ref encontrado, animación idle: {anim_p1}")
        else:
            print(f"[LOBBY] No hay player_ref o no tiene animations. player_ref={self.player_ref}")

        # Crear pantalla de lobby
        self.lobby = PantallaLobby(
            logical_w=width,
            logical_h=height,
            fondo_menu=self.background,
            btn_asset=self.btn_normal,
            anim_p1=anim_p1,
        )

        # Establecer estado inicial: verificar si hay cliente conectado
        if self.net_manager:
            p2_conectado = "aliado" in self.net_manager.roles_conectados()
            self.lobby.set_p2_conectado(p2_conectado)

        # Notificar al cliente que entramos al lobby (servidor)
        if self.servidor_menu:
            self.servidor_menu.enviar_estado_menu("lobby")

        self.overlay_key = "lobby"
        return True

    def selected_seed(self) -> Optional[int]:
        if not self.seed_text:
            return None
        try:
            return int(self.seed_text)
        except ValueError:
            return None

    def _draw_cyber_grid(self) -> None:
        """Dibuja una cuadrícula oscura con tinte rojo si no hay imagen de fondo."""
        self.screen.fill(self.COLOR_DARK_BG)
        width, height = self.screen.get_size()

        for x in range(0, width, 48):
            pygame.draw.line(self.screen, self.COLOR_GRID, (x, 0), (x, height), 1)
        for y in range(0, height, 48):
            pygame.draw.line(self.screen, self.COLOR_GRID, (0, y), (width, y), 1)

        # Viñeta: oscurecer bordes
        vignette = pygame.Surface((width, height), pygame.SRCALPHA)
        for i, alpha in enumerate([80, 50, 25, 10]):
            margin = i * 40
            pygame.draw.rect(vignette, (0, 0, 0, alpha),
                             pygame.Rect(margin, margin, width - margin * 2, height - margin * 2), 30)
        self.screen.blit(vignette, (0, 0))

    def _draw_connecting_overlay(self) -> None:
        """Renderiza overlay "Conectando al servidor..." para cliente."""
        width, height = self.screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        try:
            font = pygame.font.SysFont("monospace", 20)
            txt = font.render(
                "Conectando al servidor...",
                False, (150, 100, 200)
            )
            self.screen.blit(txt, (
                width // 2 - txt.get_width() // 2,
                height // 2
            ))

            if self.cliente_menu:
                font_small = pygame.font.SysFont("monospace", 14)
                txt_ip = font_small.render(
                    f"IP: {self.cliente_menu.ip_servidor}:{self.cliente_menu.PUERTO}",
                    False, (80, 60, 100)
                )
                self.screen.blit(txt_ip, (
                    width // 2 - txt_ip.get_width() // 2,
                    height // 2 + 40
                ))
        except Exception:
            pass

    def _draw_connection_error_overlay(self) -> None:
        """Renderiza overlay de error de conexión."""
        width, height = self.screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        try:
            font = pygame.font.SysFont("monospace", 20)
            font_small = pygame.font.SysFont("monospace", 14)

            txt = font.render(
                "No se pudo conectar al servidor",
                False, (200, 50, 50)
            )
            self.screen.blit(txt, (
                width // 2 - txt.get_width() // 2,
                height // 2 - 30
            ))

            txt2 = font_small.render(
                "Verifica que el servidor esté activo",
                False, (120, 80, 100)
            )
            self.screen.blit(txt2, (
                width // 2 - txt2.get_width() // 2,
                height // 2 + 20
            ))

            if self.cliente_menu:
                txt3 = font_small.render(
                    f"IP esperada: {self.cliente_menu.ip_servidor}",
                    False, (80, 60, 80)
                )
                self.screen.blit(txt3, (
                    width // 2 - txt3.get_width() // 2,
                    height // 2 + 50
                ))
        except Exception:
            pass

    def _draw_menu(self, *, dim_background: bool = False) -> None:
        width, height = self.screen.get_size()

        if self.background:
            background = pygame.transform.smoothscale(self.background, (width, height))
            self.screen.blit(background, (0, 0))
        else:
            self._draw_cyber_grid()

        if dim_background:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))

        # Cargar y mostrar logo PNG en lugar del texto
        logo_title = self._load_logo_title()
        if logo_title:
            # Escalar a 1/3 del tamaño original
            scaled_size = (logo_title.get_width() // 3, logo_title.get_height() // 3)
            logo_title_scaled = pygame.transform.smoothscale(logo_title, scaled_size)
            logo_title_rect = logo_title_scaled.get_rect(center=(width // 2, height // 5))
            self.screen.blit(logo_title_scaled, logo_title_rect)
        else:
            # Fallback a texto si no carga la imagen
            title_text = self.menu_cfg.title.upper()
            # Sombra exterior oscura
            shadow_surf = self.title_font.render(title_text, True, (60, 4, 8))
            shadow_rect = shadow_surf.get_rect(center=(width // 2 + 5, height // 4 + 5))
            self.screen.blit(shadow_surf, shadow_rect)
            # Segunda sombra más cerca
            shadow2_surf = self.title_font.render(title_text, True, (120, 14, 20))
            shadow2_rect = shadow2_surf.get_rect(center=(width // 2 + 2, height // 4 + 2))
            self.screen.blit(shadow2_surf, shadow2_rect)
            # Título principal en crimson
            title_surf = self.title_font.render(title_text, True, self.COLOR_CRIMSON)
            logo_title_rect = title_surf.get_rect(center=(width // 2, height // 4))
            self.screen.blit(title_surf, logo_title_rect)

        if self.menu_cfg.subtitle:
            subtitle_surf = self.subtitle_font.render(
                self.menu_cfg.subtitle, True, (185, 130, 130)
            )
            subtitle_rect = subtitle_surf.get_rect(
                center=(width // 2, logo_title_rect.bottom + 10)
            )
            self.screen.blit(subtitle_surf, subtitle_rect)

        if self.logo:
            logo_rect = self.logo.get_rect()
            logo_rect.center = (width // 2, logo_title_rect.bottom + 80)
            self.screen.blit(self.logo, logo_rect)

        mouse_pos = pygame.mouse.get_pos()

        for button, rect in self.button_rects:
            hovered = rect.collidepoint(mouse_pos)

            # ── SPRITE DEL BOTÓN ──
            sprite = self.btn_hover if hovered else self.btn_normal
            if sprite:
                scaled = pygame.transform.smoothscale(sprite, (rect.width, rect.height))
                self.screen.blit(scaled, rect.topleft)
            else:
                # Fallback si no carga la imagen
                pygame.draw.rect(self.screen, (22, 4, 4), rect)
                pygame.draw.rect(self.screen, self.COLOR_CRIMSON, rect, 1)

            # ── TEXTO centrado sobre el sprite ──
            label = next(
                (b.label for b in self.menu_cfg.buttons if b.action == button),
                button,
            ).upper()

            # Sombra del texto
            sh = self.button_font.render(label, True, (40, 4, 4))
            self.screen.blit(sh, sh.get_rect(center=(rect.centerx + 2, rect.centery + 2)))

            # Texto principal
            text_color = self.COLOR_HOVER_TEXT if hovered else self.COLOR_TEXT_WHITE
            ls = self.button_font.render(label, True, text_color)
            self.screen.blit(ls, ls.get_rect(center=rect.center))

        self._draw_seed_input()
        self._draw_volume_slider()

    def _draw_seed_input(self) -> None:
        border_color = self.COLOR_EMBER if self.input_active else (70, 25, 25)

        pygame.draw.rect(self.screen, (14, 6, 6), self.seed_rect)
        pygame.draw.rect(self.screen, border_color, self.seed_rect, 2)

        seed_display = self.seed_text or "SEED  (VACIO = ALEATORIO)"
        text_color = self.COLOR_CRIMSON if self.seed_text else (90, 55, 55)

        text_surf = self.small_font.render(seed_display, True, text_color)
        text_rect = text_surf.get_rect(midleft=(self.seed_rect.left + 12, self.seed_rect.centery))
        self.screen.blit(text_surf, text_rect)

        hint_surf = self.small_font.render("ENTER PARA JUGAR", True, (110, 60, 60))
        hint_rect = hint_surf.get_rect(
            center=(self.screen.get_width() // 2, self.seed_rect.bottom + 22)
        )
        self.screen.blit(hint_surf, hint_rect)

    def _statistics_lines(self) -> tuple[str, ...]:
        if self.stats_manager is None:
            return ("ESTADISTICAS", "", "No disponibles :: ERROR 404")
        return self.stats_manager.summary_lines()

    def _draw_volume_slider(self) -> None:
        label_surf = self.small_font.render("VOLUMEN", True, self.COLOR_TEXT_WHITE)
        label_rect = label_surf.get_rect(
            center=(self.volume_bar_rect.centerx, self.volume_bar_rect.top - 16)
        )
        self.screen.blit(label_surf, label_rect)

        track_rect = self.volume_bar_rect
        pygame.draw.rect(self.screen, (30, 10, 10), track_rect, border_radius=4)
        fill_width = int(track_rect.width * max(0.0, min(1.0, self.volume)))
        if fill_width > 0:
            fill_rect = pygame.Rect(track_rect.left, track_rect.top, fill_width, track_rect.height)
            pygame.draw.rect(self.screen, self.COLOR_CRIMSON, fill_rect, border_radius=4)

        handle_rect = self.volume_handle_rect
        handle_surface = pygame.Surface(handle_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            handle_surface,
            self.COLOR_NEON_PINK if self.dragging_volume else self.COLOR_NEON_BLUE,
            handle_surface.get_rect(),
            border_radius=6,
        )
        pygame.draw.rect(handle_surface, (0, 0, 0), handle_surface.get_rect(), 2, border_radius=6)
        self.screen.blit(handle_surface, handle_rect)

        percent = int(self.volume * 100)
        percent_surf = self.small_font.render(f"{percent}%", True, (180, 180, 180))
        percent_rect = percent_surf.get_rect(
            center=(self.volume_bar_rect.centerx, self.volume_bar_rect.bottom + 16)
        )
        self.screen.blit(percent_surf, percent_rect)

    def _is_over_volume(self, pos: tuple[int, int]) -> bool:
        expanded = self.volume_bar_rect.inflate(0, 16)
        expanded.union_ip(self.volume_handle_rect)
        return expanded.collidepoint(pos)

    def _set_volume_from_mouse(self, mouse_x: int) -> None:
        relative = (mouse_x - self.volume_bar_rect.left) / self.volume_bar_rect.width
        self.volume = max(0.0, min(1.0, relative))
        self._update_volume_handle_pos()
        self._apply_volume()
        # Notificar al cliente sobre cambio de volumen (servidor)
        if self.servidor_menu:
            volumen_int = int(self.volume * 100)
            self.servidor_menu.enviar_config(volumen_int)

    def _apply_volume(self) -> None:
        if not pygame.mixer.get_init():
            return
        pygame.mixer.music.set_volume(self.volume)
        if self.click_sound:
            self.click_sound.set_volume(self.volume)
        channel_count = pygame.mixer.get_num_channels()
        for channel_index in range(channel_count):
            pygame.mixer.Channel(channel_index).set_volume(self.volume)

    def _draw_skins_overlay(self) -> None:
        width, height = self.screen.get_size()
        
        # 1. REDUCCIÓN DEL CUADRADO AZUL
        # Antes: width * 0.85, height * 0.88
        # Ahora: width * 0.70, height * 0.82 (Más pequeño y centrado)
        overlay_rect = pygame.Rect(0, 0, int(width * 0.70), int(height * 0.82))
        overlay_rect.center = (width // 2, height // 2)
        self.skins_overlay_rect = overlay_rect

        # Fondo y Borde
        pygame.draw.rect(self.screen, (10, 10, 20), overlay_rect)
        pygame.draw.rect(self.screen, self.COLOR_NEON_BLUE, overlay_rect, 2)

        # Título (Ajustado un poco más arriba)
        title_surf = self.button_font.render("SELECCIONA TU SKIN", True, self.COLOR_TEXT_WHITE)
        title_rect = title_surf.get_rect(center=(width // 2, overlay_rect.top + 45))
        self.screen.blit(title_surf, title_rect)

        mouse_pos = pygame.mouse.get_pos()
        self.body_cards = []
        self.color_rects = []

        # Configuración de cartas (Personajes)
        card_width = int(overlay_rect.width * 0.38)
        card_height = 300  # Reducido de 340 a 300 para ganar espacio vertical
        
        # Inicio vertical de las cartas
        start_y = overlay_rect.top + 90 
        
        for idx, body in enumerate(("flaco", "gordo")):
            if idx == 0:
                x_pos = overlay_rect.left + overlay_rect.width // 4
            else:
                x_pos = overlay_rect.left + 3 * overlay_rect.width // 4
            
            rect = pygame.Rect(0, 0, card_width, card_height)
            rect.centerx = x_pos
            rect.y = start_y
            self.body_cards.append((body, rect))

            hovered = rect.collidepoint(mouse_pos)
            selected = body == self.selected_body
            base_color = pygame.Color(20, 20, 30)
            if selected:
                base_color = pygame.Color(40, 20, 50)
            if hovered:
                base_color += pygame.Color(15, 15, 15)

            border_color = self.COLOR_NEON_PINK if selected else self.COLOR_NEON_BLUE
            border_width = 3 if selected else 2
            pygame.draw.rect(self.screen, base_color, rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, rect, border_width, border_radius=8)

            label = "CYBER-067" if body == "flaco" else "CYBER-021"
            label_surf = self.button_font.render(label, True, self.COLOR_TEXT_WHITE)
            label_rect = label_surf.get_rect(center=(rect.centerx, rect.top + 30))
            self.screen.blit(label_surf, label_rect)

            preview_rect = pygame.Rect(0, 0, rect.width - 40, rect.height - 80)
            preview_rect.center = (rect.centerx, rect.centery + 25)
            self._draw_skin_preview(body, preview_rect)

        # 2. SEPARACIÓN Y BAJADA DE COLORES
        colors = [
            ("grey", (140, 140, 140)),
            ("red", (200, 60, 80)),
            ("blue", (60, 120, 255)),
            ("green", (60, 190, 100)),
        ]
        swatch_size = 60 # Reducido de 70 a 60
        swatch_gap = 24
        total_width = len(colors) * swatch_size + (len(colors) - 1) * swatch_gap
        start_x = overlay_rect.centerx - total_width // 2
        
        # AQUÍ ESTÁ EL CAMBIO CLAVE:
        # start_y + card_height + 80 (Antes era + 50).
        # Esto empuja los colores 30 pixeles más abajo, separándolos de las cartas.
        swatch_y = start_y + card_height + 140

        for idx, (color_id, rgb) in enumerate(colors):
            rect = pygame.Rect(start_x + idx * (swatch_size + swatch_gap), swatch_y, swatch_size, swatch_size)
            self.color_rects.append((color_id, rect))

            hovered = rect.collidepoint(mouse_pos)
            selected = color_id == self.selected_color
            border_color = self.COLOR_NEON_PINK if selected else self.COLOR_NEON_BLUE
            border_width = 3 if selected else 2
            shade = pygame.Color(*rgb)
            if hovered:
                shade = pygame.Color(min(255, shade.r + 20), min(255, shade.g + 20), min(255, shade.b + 20))

            pygame.draw.rect(self.screen, shade, rect, border_radius=4)
            pygame.draw.rect(self.screen, border_color, rect, border_width, border_radius=6)

        # Botón Confirmar
        button_width = 240
        button_height = 50
        self.confirm_button_rect = pygame.Rect(0, 0, button_width, button_height)
        # Posicionado relativo al fondo del cuadro reducido
        self.confirm_button_rect.center = (width // 2, overlay_rect.bottom - 70)
        
        button_hovered = self.confirm_button_rect.collidepoint(mouse_pos)
        button_bg = (40, 40, 60, 200) if button_hovered else (0, 0, 0, 180)
        button_border = self.COLOR_NEON_PINK if button_hovered else self.COLOR_NEON_BLUE
        
        btn_surf = pygame.Surface((button_width, button_height), pygame.SRCALPHA)
        pygame.draw.rect(btn_surf, button_bg, btn_surf.get_rect(), border_radius=4)
        pygame.draw.rect(btn_surf, button_border, btn_surf.get_rect(), 2, border_radius=4)
        self.screen.blit(btn_surf, self.confirm_button_rect)
        
        confirm_text = "CONFIRMAR"
        confirm_color = self.COLOR_NEON_BLUE if button_hovered else self.COLOR_TEXT_WHITE
        confirm_surf = self.button_font.render(confirm_text, True, confirm_color)
        confirm_rect = confirm_surf.get_rect(center=self.confirm_button_rect.center)
        self.screen.blit(confirm_surf, confirm_rect)

        # Texto de Ayuda (Ajustado para no cortarse)
        hint_text = "Elige cuerpo y color (ESC para cancelar)"
        hint_surf = self.small_font.render(hint_text.upper(), True, (150, 150, 150))
        # Subido un poco respecto al borde inferior (-25 en lugar de -30 o más abajo)
        hint_rect = hint_surf.get_rect(center=(width // 2, overlay_rect.bottom - 25))
        self.screen.blit(hint_surf, hint_rect)
        
    def _draw_skin_preview(self, body: str, rect: pygame.Rect) -> None:
        frames = self._load_preview_animation(body, self.selected_color)
        if not frames:
            pygame.draw.rect(self.screen, (30, 30, 40), rect, border_radius=6)
            pygame.draw.rect(self.screen, self.COLOR_NEON_BLUE, rect, 2, border_radius=6)
            missing_surf = self.small_font.render("Sin sprites", True, self.COLOR_TEXT_WHITE)
            missing_rect = missing_surf.get_rect(center=rect.center)
            self.screen.blit(missing_surf, missing_rect)
            return

        frame_time = 0.12
        frame_idx = int(self.preview_anim_time / frame_time) % len(frames)
        frame = frames[frame_idx]
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((10, 10, 20, 200))
        pygame.draw.rect(bg, (0, 0, 0, 120), bg.get_rect(), border_radius=8)
        self.screen.blit(bg, rect)

        frame_rect = frame.get_rect()
        scale = min((rect.width - 16) / frame_rect.width, (rect.height - 16) / frame_rect.height, 4.5)
        scaled = pygame.transform.smoothscale(frame, (int(frame_rect.width * scale), int(frame_rect.height * scale)))
        scaled_rect = scaled.get_rect(center=rect.center)
        self.screen.blit(scaled, scaled_rect)

    def _load_preview_animation(self, body: str, color: str) -> list[pygame.Surface]:
        key = (body, color)
        if key in self.preview_cache:
            return self.preview_cache[key]

        sprite_dir = Path("assets") / "player" / f"{color}_{body}"
        frames: list[pygame.Surface] = []
        for i in range(4):
            path = sprite_dir / f"player_run_{i}.png"
            try:
                frame = pygame.image.load(path.as_posix()).convert_alpha()
            except (FileNotFoundError, pygame.error):
                frames = []
                break
            frames.append(frame)

        self.preview_cache[key] = frames
        return frames

    def _draw_overlay(self) -> None:
        width, height = self.screen.get_size()

        # Manejo de imágenes (créditos y controles)
        image_to_display = None
        if self.overlay_key == "credits" and self.credits_image:
            image_to_display = self.credits_image
        elif self.overlay_key == "controls" and self.controls_image:
            image_to_display = self.controls_image

        if image_to_display:
            img_w, img_h = image_to_display.get_size()
            max_w = width * 0.92
            max_h = height * 0.92
            scale = min(max_w / img_w, max_h / img_h, 1.0)
            if scale < 1.0:
                display_image = pygame.transform.smoothscale(
                    image_to_display, (int(img_w * scale), int(img_h * scale))
                )
            else:
                display_image = image_to_display

            scaled_w, scaled_h = display_image.get_size()
            padding = 44
            overlay_rect = pygame.Rect(
                0,
                0,
                min(int(width * 0.96), scaled_w + padding * 2),
                min(int(height * 0.96), scaled_h + padding * 2),
            )
            overlay_rect.center = (width // 2, height // 2)

            overlay_surface = pygame.Surface(overlay_rect.size, pygame.SRCALPHA)
            overlay_surface.fill((10, 10, 20, 230))

            inset_margin = max(24, padding - 12)
            inset_rect = overlay_surface.get_rect().inflate(-inset_margin * 2, -inset_margin * 2)
            image_rect = display_image.get_rect(center=inset_rect.center)
            overlay_surface.blit(display_image, image_rect)
        else:
            overlay_rect = pygame.Rect(0, 0, width * 0.8, height * 0.8)
            overlay_rect.center = (width // 2, height // 2)

            overlay_surface = pygame.Surface(overlay_rect.size, pygame.SRCALPHA)

            # ── CAPA 1: FONDO (IMAGEN O COLOR SÓLIDO) ──
            # Para estadísticas, cargar panel_estadisticas.png si existe
            stats_bg_image = None
            if self.overlay_key == "statistics":
                stats_bg_image = self._load_image("panel_estadisticas.png")

            if stats_bg_image:
                # Escalar imagen al tamaño del overlay
                scaled_bg = pygame.transform.smoothscale(stats_bg_image, overlay_rect.size)
                scaled_bg.set_alpha(255)  # Completamente opaco
                overlay_surface.blit(scaled_bg, (0, 0))
            else:
                # Fallback: color sólido si no carga la imagen
                overlay_surface.fill((10, 10, 20, 230))

            # ── CAPA 2: TEXTO CON SOMBRAS ──
            text_start = 60
            lines = self.overlay_lines or ("",)
            for i, line in enumerate(lines):
                # Primera línea: título (más grande y rojo)
                if i == 0:
                    font = self.title_font
                    text_color = self.COLOR_CRIMSON
                    line_y = text_start - 20
                    line_spacing = 80
                else:
                    font = self.button_font
                    text_color = self.COLOR_TEXT_WHITE
                    line_y = text_start + (i - 1) * 40 + 50
                    line_spacing = 40

                # Sombra oscura para mejor legibilidad
                shadow_surf = font.render(line, True, (20, 10, 15))
                shadow_rect = shadow_surf.get_rect(
                    center=(overlay_rect.width // 2 + 2, line_y + 2)
                )
                overlay_surface.blit(shadow_surf, shadow_rect)

                # Texto principal
                surf = font.render(line, True, text_color)
                rect = surf.get_rect(
                    center=(overlay_rect.width // 2, line_y)
                )
                overlay_surface.blit(surf, rect)

        self.screen.blit(overlay_surface, overlay_rect)
        pygame.draw.rect(self.screen, self.COLOR_NEON_BLUE, overlay_rect, 2)

        exit_hint = self.small_font.render(
            "[ CLICK / ESC ] PARA VOLVER", True, self.COLOR_NEON_PINK
        )
        hint_rect = exit_hint.get_rect(center=(width // 2, overlay_rect.bottom - 40))
        self.screen.blit(exit_hint, hint_rect)