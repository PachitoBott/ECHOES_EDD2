# CODIGO/Game.py
import math
import random
import sys
import time
from collections.abc import Callable
from time import perf_counter
from pathlib import Path

import pygame

from Config import Config
from ui.StartMenu import StartMenu
from core.Tileset import Tileset
from entities.Player import Player
from world.Dungeon import Dungeon
from ui.Minimap import Minimap
from core.Projectile import ProjectileGroup
from ui.Shop import Shop
from ui.Shopkeeper import Shopkeeper
from ui.HudPanels import HudPanels
from ui.PauseMenu import PauseMenu, PauseMenuButton
from ui.GameOverScreen import GameOverScreen
from Statistics import StatisticsManager
from entities.Pickup import Pickup
from core.asset_paths import WEAPON_SPRITE_FILENAMES, assets_dir, weapon_sprite_path

# --- Narrativa (Fase 4-5) ---
from narrative.cinematics import CinematicSystem
from narrative.dialogue_system import DialogueSystem
from accessibility.subtitles import SubtitleSystem

# --- Networking (Fase 3) ---
from network import NetworkManager, EventoRed
from dev.logger import log_net

# --- Herramientas de desarrollo ---
from dev.logger import log_game, log_asset, log_room, log_player
from dev.hot_reload import AssetWatcher
from dev.debug_console import DebugConsole


class Game:
    COIN_SPRITE_NAME = "moneda.png"
    COIN_ICON_DEFAULT_SCALE = 1.5
    COIN_PICKUP_SIZE = (12, 12)

    def __init__(
        self,
        cfg: Config,
        *,
        debug_mode: bool = False,
        mode: str = "offline",
        port: int = 5555,
        host: str = "127.0.0.1",
        role: str = "victim",
    ) -> None:
        pygame.init()
        self.cfg = cfg
        self._debug_mode = debug_mode
        self._net_mode = mode
        self._net_port = port
        self._net_host = host
        self._net_role = role

        # ---------- Ventana ----------
        self.screen = pygame.display.set_mode(
            (cfg.SCREEN_W * cfg.SCREEN_SCALE, cfg.SCREEN_H * cfg.SCREEN_SCALE)
        )
        pygame.display.set_caption("Echoes")
        log_game.info("Ventana inicializada (%dx%d, escala %dx)",
                      cfg.SCREEN_W, cfg.SCREEN_H, cfg.SCREEN_SCALE)
        self.clock = pygame.time.Clock()
        self.world = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H))
        pygame.mouse.set_visible(False)
        self._cursor_surface = self._create_cursor_surface()

        # ---------- UI ----------
        self.ui_font = pygame.font.SysFont(None, 18)
        icon_source, pickup_sprite = self._create_coin_sprites()
        self._coin_icon_source = icon_source
        self._coin_pickup_sprite = pickup_sprite
        self.coin_icon_scale = self.COIN_ICON_DEFAULT_SCALE * 0.8
        
        # Usa los métodos set_coin_icon_scale/offset/value_offset para ajustar
        # manualmente la presentación del icono dentro del HUD.
        self._coin_icon = self._scale_coin_icon(self.coin_icon_scale)
        self._battery_states = self._load_battery_states()
        self._life_battery_highlight = pygame.Color(110, 200, 255)
        # Ajusta este offset para reposicionar las vidas en el HUD.
        # Incrementa la componente X para mover las barras hacia la derecha
        # (disminúyela para moverlas a la izquierda) y modifica Y para
        # desplazarlas verticalmente.
        self._life_battery_offset = pygame.Vector2(-455, 35)
        # --- Configuración del HUD de armas ---
        self.weapon_icon_offset = pygame.Vector2(60, 50)
        self.weapon_icon_scale = 1.0
        self.weapon_text_margin = 18
        self._weapon_icons = self._load_weapon_icons()
        self._weapon_icon_cache: dict[tuple[str, float], pygame.Surface] = {}
        self.current_seed: int | None = None
        self.coin_icon_offset = pygame.Vector2(193, 42)
        self.coin_value_offset = pygame.Vector2(0, -100)
        self.coin_value_color = pygame.Color(255, 240, 180)

        # --- Tienda ---
        self.shop = Shop(font=self.ui_font, on_gold_spent=self._register_gold_spent)

        # --- HUD ---
        self.hud_panels = HudPanels()
        # Ajusta posiciones/escala desde fuera, por ejemplo:
        # self.hud_panels.inventory_panel_position.update(nuevo_x, nuevo_y)
        if hasattr(self.hud_panels, "set_minimap_anchor"):
            # Centra el minimapa dentro del panel de esquina para que quede cubierto.
            self.hud_panels.set_minimap_anchor("top-right",  margin=(80, 140))

        # ---------- Recursos ----------
        self.tileset = Tileset()
        self.minimap = Minimap(cell=16, padding=8)

        # ---------- Estado runtime ----------
        self.projectiles = ProjectileGroup()          # balas del jugador
        self.enemy_projectiles = ProjectileGroup()    # balas de enemigos
        self.remote_projectiles = []                  # balas disparadas por otros jugadores
        self.door_cooldown = 0.0
        self.running = True
        self.debug_draw_doors = cfg.DEBUG_DRAW_DOOR_TRIGGERS
        self._skip_frame = False


        # --- Menú de pausa ---
        self.pause_menu_buttons: list[PauseMenuButton] = [
            PauseMenuButton("Reanudar", "resume"),
            PauseMenuButton("Menú principal", "main_menu"),
            PauseMenuButton("Salir del juego", "quit"),
        ]
        self.pause_menu_handlers: dict[str, Callable[[], bool | None]] = {}

        # ---------- Estadísticas ----------
        self.stats_manager = StatisticsManager()
        self._run_start_time: float | None = None
        self._stats_pending_reason: str | None = None
        self._run_gold_spent: int = 0
        self._run_kills: int = 0

        # ---------- Narrativa (cinemáticas y diálogos) ----------
        self.cinematics = CinematicSystem(cfg.SCREEN_W, cfg.SCREEN_H, font_size=22)
        try:
            self.cinematics.cargar_json("narrative/cutscenes.json")
            log_game.info(f"[OK] Cinematicas cargadas: {self.cinematics.ids_disponibles()}")
        except Exception as e:
            log_game.error(f"Error cargando cinematicas: {e}")

        self.dialogue = DialogueSystem(cfg.SCREEN_W, cfg.SCREEN_H, font_size=14)

        # Cargar diálogos de Mara
        try:
            self.dialogue.cargar_json("narrative/mara_dialogues.json", "mara")
        except Exception as e:
            log_game.warning(f"No se pudieron cargar diálogos de Mara: {e}")

        # Estado del juego compartido con el sistema de diálogos
        self._estado_juego: dict = {"apoyo": 0}

        # Sistema de notificaciones en pantalla
        self.subtitulos = SubtitleSystem(cfg.SCREEN_W, cfg.SCREEN_H, font_size=20)

        # Control de estado narrativo
        self._current_zone: int = 1
        self._intro_played: bool = False
        self._mara_cutscene_played: bool = False  # Cinemática de Mara: se dispara solo una vez

        # ---------- Networking (Fase 3) ----------
        self.net: NetworkManager | None = None
        self.remote_players: dict = {}  # Almacena estado de jugadores remotos
        self._send_state_interval = 0.1  # Enviar estado cada 100ms (~10 Hz)
        self._last_state_send = 0.0
        if self._net_mode == "server":
            self.net = NetworkManager.como_servidor(port=self._net_port, seed=None)
            if not self.net.iniciar():
                log_game.error("❌ No se pudo iniciar servidor de red")
                self.running = False
            else:
                log_game.info(f"✅ Servidor escuchando en puerto {self._net_port}")
        elif self._net_mode == "client":
            self.net = NetworkManager.como_cliente(
                host=self._net_host,
                port=self._net_port,
                rol=self._net_role,
            )
            if not self.net.iniciar():
                log_game.error(f"❌ No se pudo conectar a {self._net_host}:{self._net_port}")
                self.running = False
            else:
                log_game.info(f"✅ Conectado al servidor como {self._net_role}")

        # ---------- Herramientas de desarrollo ----------
        # Consola de debug (F1): siempre creada, solo visible en debug_mode
        self.debug_console = DebugConsole(self)

        # Hot-reload: monitorea assets para recargar sin reiniciar
        self.asset_watcher = AssetWatcher(check_interval=0.5)
        self._register_asset_watchers()

        if self._debug_mode:
            log_game.info("Modo debug activo — F1 abre la consola de debug")

    # ------------------------------------------------------------------ #
    # Hot-reload de assets
    # ------------------------------------------------------------------ #

    def _register_asset_watchers(self) -> None:
        """
        Registra los archivos de assets a vigilar para hot-reload.

        Al cambiar cualquier PNG en 'weapons/' se recargan los iconos
        de armas. Al cambiar sprites de UI se recarga el icono de moneda.
        """
        weapons_dir = assets_dir("weapons")
        ui_dir      = assets_dir("ui")

        count = self.asset_watcher.watch_dir(
            weapons_dir, "*.png", self._on_weapon_sprite_changed
        )
        log_asset.debug(f"Vigilando {count} sprites de armas")

        count = self.asset_watcher.watch_dir(
            ui_dir, "*.png", self._on_ui_sprite_changed
        )
        log_asset.debug(f"Vigilando {count} sprites de UI")

    def _on_weapon_sprite_changed(self, path: Path) -> None:
        """Callback: recarga el sprite del arma que cambió."""
        filename  = path.name
        weapon_id = next(
            (wid for wid, fn in WEAPON_SPRITE_FILENAMES.items() if fn == filename),
            None,
        )
        if weapon_id is None:
            return   # no es un sprite de arma conocido

        try:
            surface = pygame.image.load(path.as_posix()).convert_alpha()
            self._weapon_icons[weapon_id] = surface
            # Limpiar entradas de caché para este weapon_id
            stale = [k for k in self._weapon_icon_cache if k[0] == weapon_id]
            for k in stale:
                del self._weapon_icon_cache[k]
            log_asset.info(f"Sprite de arma recargado: {weapon_id}")
        except Exception as exc:
            log_asset.error(f"Error recargando sprite de arma '{path.name}': {exc}")

    def _on_ui_sprite_changed(self, path: Path) -> None:
        """Callback: recarga elementos de UI cuando cambia un sprite."""
        if path.name == self.COIN_SPRITE_NAME:
            try:
                icon_source, pickup_sprite = self._create_coin_sprites()
                self._coin_icon_source = icon_source
                self._coin_pickup_sprite    = pickup_sprite
                self._coin_icon = self._scale_coin_icon(self.coin_icon_scale)
                log_asset.info("Icono de moneda recargado")
            except Exception as exc:
                log_asset.error(f"Error recargando icono de moneda: {exc}")

    # ------------------------------------------------------------------ #
    # Inicio rápido (sin menú) — para flags CLI y tests
    # ------------------------------------------------------------------ #

    def quick_start(
        self,
        seed: int | None = None,
        start_room: tuple[int, int] | None = None,
    ) -> None:
        """
        Inicia el juego directamente sin pasar por el menú de inicio.

        Parámetros
        ----------
        seed:
            Seed para la generación del dungeon (None = aleatoria).
        start_room:
            Tupla (i, j) para teletransportar al jugador a una sala
            concreta después de crear el dungeon.
        """
        self.start_new_run(seed=seed)

        if start_room is not None:
            dungeon = self.dungeon
            if start_room in dungeon.rooms:
                dungeon.i, dungeon.j = start_room
                dungeon.explored.add(start_room)
                room   = dungeon.current_room
                cx, cy = room.center_px()
                self.player.x = float(cx) - self.player.w / 2.0
                self.player.y = float(cy) - self.player.h / 2.0
                log_game.info(f"Jugador ubicado en sala {start_room}")
            else:
                log_game.warning(
                    f"Sala {start_room} no existe en el dungeon generado "
                    f"(seed={self.current_seed}). Se inicia en la sala por defecto."
                )

        self._frame_counter = 0
        self._run_quick_loop()

    def _run_quick_loop(self) -> None:
        """Bucle principal compartido con run() cuando se salta el menú."""
        while self.running:
            dt = self.clock.tick(self.cfg.FPS) / 1000.0
            self.door_cooldown = max(0.0, self.door_cooldown - dt)

            events = self._handle_events()
            if self._skip_frame:
                self._skip_frame = False
                continue

            self._update_fps_counter()
            self._update(dt, events)
            self._render()

        pygame.mouse.set_visible(True)
        self._finalize_run_statistics("shutdown")
        if self.net:
            self.net.detener()
        pygame.quit()
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # Nueva partida / regenerar dungeon (misma o nueva seed)
    # ------------------------------------------------------------------ #
    def start_new_run(self, seed: int | None = None, dungeon_params: dict | None = None) -> None:
        """
        Crea una nueva dungeon con la seed dada (o aleatoria si None),
        reubica al jugador y resetea estado de runtime.
        """
        finalize_reason = self._stats_pending_reason or "restart"
        self._finalize_run_statistics(finalize_reason)
        self._stats_pending_reason = None

        params = self.cfg.dungeon_params()
        if dungeon_params:
            params = {**params, **dungeon_params}

        self.dungeon = Dungeon(**params, seed=seed)
        self.current_seed = self.dungeon.seed
        pygame.display.set_caption(f"Echoes — Seed {self.current_seed}")
        log_game.info(f"Nueva partida — seed={self.current_seed}  salas={len(self.dungeon.rooms)}")

        # Actualizar seed del servidor (para que la comunique a los clientes)
        if self.net and self.net.es_servidor and hasattr(self.net, '_servidor'):
            self.net._servidor.seed = self.current_seed
            log_game.info(f"✅ Seed compartida con clientes: {self.current_seed}")

        # preparar inventario de la tienda para esta seed
        if hasattr(self, "shop"):
            self.shop.close()
            self.shop.configure_for_seed(self.current_seed)

        # marcar room inicial como explorado
        self.dungeon.explored = set()
        self.dungeon.explored.add((self.dungeon.i, self.dungeon.j))

        # Jugador (crear o reubicar al centro del cuarto actual)
        room = self.dungeon.current_room
        px, py = room.center_px()
        spawn_x = px - Player.HITBOX_SIZE[0] / 2
        spawn_y = py - Player.HITBOX_SIZE[1] / 2
        if not hasattr(self, "player"):
            self.player = Player(spawn_x, spawn_y)
        else:
            self.player.x, self.player.y = spawn_x, spawn_y
        if hasattr(self.player, "reset_loadout"):
            self.player.reset_loadout()
        setattr(self.player, "gold", 0)

        # Set up shooting callback for network synchronization
        if self.net:
            self.player.on_shoot = self._on_player_shoot

        # Reset de runtime
        self._reset_runtime_state()

        # ✅ Entrar “formalmente” a la sala inicial (dispara on_enter/Shop si aplica)
        if hasattr(self.dungeon, "enter_initial_room"):
            self.dungeon.enter_initial_room(self.player, self.cfg, ShopkeeperCls=Shopkeeper)

        self._run_start_time = perf_counter()

        # Trigger narrativa: marcar para reproducir intro en el primer frame
        self._intro_played = False
        self._current_zone = 1

    def _reset_runtime_state(self) -> None:
        self.projectiles.clear()
        self.enemy_projectiles.clear()
        self.door_cooldown = 0.0
        self.locked = False
        self.cleared = False
        self._run_gold_spent = 0
        self._run_kills = 0
        self._estado_juego["apoyo"] = 0

    def _register_gold_spent(self, amount: int) -> None:
        if amount <= 0:
            return
        self._run_gold_spent = max(0, self._run_gold_spent) + int(amount)

    def _finalize_run_statistics(self, reason: str | None = None) -> None:
        if self._run_start_time is None:
            return

        duration = max(0.0, perf_counter() - self._run_start_time)
        rooms_explored = 0
        dungeon = getattr(self, "dungeon", None)
        if dungeon is not None and hasattr(dungeon, "explored"):
            try:
                rooms_explored = len(dungeon.explored)
            except TypeError:
                rooms_explored = 0
        gold = 0
        player = getattr(self, "player", None)
        if player is not None:
            gold = int(getattr(player, "gold", 0))
        gold_spent = max(0, int(self._run_gold_spent))
        gold_obtained = max(0, gold) + gold_spent

        try:
            self.stats_manager.record_run(
                duration_seconds=duration,
                rooms_explored=rooms_explored,
                gold_obtained=gold_obtained,
                gold_spent=gold_spent,
            )
        except Exception as exc:  # pragma: no cover - logging best effort
            log_game.warning(f"No se pudo guardar la estadística: {exc}")

        self._run_start_time = None
        self._stats_pending_reason = None
        self._run_gold_spent = 0

    # ------------------------------------------------------------------ #
    # Bucle principal
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        if not self._open_start_menu():
            pygame.mouse.set_visible(True)
            if self.net:
                self.net.detener()
            pygame.quit()
            sys.exit(0)

        self._frame_counter = 0
        while self.running:
            dt = self.clock.tick(self.cfg.FPS) / 1000.0
            self.door_cooldown = max(0.0, self.door_cooldown - dt)

            events = self._handle_events()
            if self._skip_frame:
                self._skip_frame = False
                continue
            self._update_fps_counter()
            self._update(dt, events)
            self._render()

        pygame.mouse.set_visible(True)
        self._finalize_run_statistics("shutdown")
        if self.net:
            self.net.detener()
        pygame.quit()
        sys.exit(0)

    def _handle_events(self) -> list:
        events = pygame.event.get()
        remaining: list = []

        for e in events:
            if e.type == pygame.QUIT:
                self._finalize_run_statistics("quit")
                self.running = False
                continue

            # F1: alternar consola de debug (disponible siempre, útil en modo debug)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F1:
                self.debug_console.toggle()
                continue

            # Si la consola está abierta, ella consume todos los eventos de teclado
            if self.debug_console.handle_event(e):
                continue

            # Resto del manejo de teclas del juego
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    # Si la tienda del Profesor Ibarra está abierta, el ESC
                    # cierra la tienda (no abre pausa). Dejar pasar el evento.
                    _ibarra_tienda_activa = False
                    try:
                        _room = self.dungeon.current_room
                        if getattr(_room, "type", "") == "profesor_ibarra":
                            _prof = getattr(_room, "profesor_ibarra", None)
                            if _prof is not None and _prof.estado == _prof.TIENDA:
                                _ibarra_tienda_activa = True
                    except Exception:
                        pass
                    if not _ibarra_tienda_activa:
                        self._show_pause_menu()
                        return []
                elif e.key == pygame.K_q:
                    self._use_ibarra_item("emp")
                elif e.key == pygame.K_r:
                    self._use_ibarra_item("modo_privado")
                elif e.key == pygame.K_m:
                    self._stats_pending_reason = "manual_same_seed"
                    self.start_new_run(seed=self.current_seed)
                elif e.key == pygame.K_n:
                    self._stats_pending_reason = "manual_new_seed"
                    self.start_new_run(seed=None)

            remaining.append(e)

        return remaining

    def _open_start_menu(self) -> bool:
        pygame.mouse.set_visible(True)
        start_menu = StartMenu(self.screen, self.cfg, stats_manager=self.stats_manager)
        menu_result = start_menu.run()
        if not menu_result.start_game:
            if self._run_start_time is not None:
                reason = self._stats_pending_reason or "menu_exit"
                self._finalize_run_statistics(reason)
                self._stats_pending_reason = None
            self.running = False
            return False
        pygame.mouse.set_visible(False)
        self.start_new_run(seed=menu_result.seed)
        self._skip_frame = True
        return True

    def _procesar_evento_red(self, ev: EventoRed) -> None:
        """
        Procesa eventos de red que llegan del NetworkManager.

        Por ahora solo loguea eventos (el gameplay no cambia).
        Después se agregará sincronización de jugadores, enemigos, etc.
        """
        log_net.info(f"[NET] Evento: {ev.tipo} desde {ev.origen}")

        if ev.tipo == "jugador_unido":
            rol = ev.datos.get("rol")
            log_net.info(f"✅ Jugador {rol} se unió a la sesión")

        elif ev.tipo == "jugador_desconectado":
            rol = ev.datos.get("rol")
            motivo = ev.datos.get("motivo", "desconocido")
            log_net.info(f"❌ Jugador {rol} desconectado ({motivo})")
            # Limpiar datos del jugador desconectado
            if rol in self.remote_players:
                del self.remote_players[rol]

        elif ev.tipo == "estado":
            # Estado remoto del otro jugador — guardar para renderizar
            origen = ev.origen
            if origen and origen != self.net.rol:  # No guardar nuestro propio estado
                self.remote_players[origen] = ev.datos
                # No loguear estado (demasiados logs por segundo)

        elif ev.tipo == "enemigo_muerto":
            # Enemigo fue eliminado por otro jugador
            self._handle_remote_enemy_death(ev)

        elif ev.tipo == "proyectil_disparado":
            # Otro jugador disparó un proyectil
            self._handle_remote_projectile(ev)

        elif ev.tipo == "enemigo_danado":
            # Enemigo recibió daño de otro jugador
            self._handle_remote_damage(ev)

        elif ev.tipo == "apoyo_recibido":
            # Aliado envió un apoyo (curación, monedas, escudo, etc.)
            tipo_apoyo = ev.datos.get("apoyo")
            valor = ev.datos.get("valor")
            log_net.info(f"🔵 Apoyo recibido: {tipo_apoyo} ({valor})")

        elif ev.tipo == "error_red":
            descripcion = ev.datos.get("descripcion", "error desconocido")
            log_game.warning(f"⚠️ Error de red: {descripcion}")

        else:
            log_net.debug(f"Evento de red no manejado: {ev.tipo}")

    def _handle_remote_enemy_death(self, ev: EventoRed) -> None:
        """
        Procesa la muerte de un enemigo reportada por otro jugador.

        Busca el enemigo en la sala actual por posición y tipo, y lo elimina.
        """
        datos = ev.datos
        sala_remota_raw = datos.get("sala")
        # Convert to tuple (JSON deserializes tuples as lists)
        sala_remota = tuple(sala_remota_raw) if isinstance(sala_remota_raw, (list, tuple)) else (0, 0)
        pos_x = datos.get("pos_x")
        pos_y = datos.get("pos_y")
        enemy_type = datos.get("enemy_type")

        # Solo procesar si el enemigo murió en la sala actual
        sala_actual = (self.dungeon.i, self.dungeon.j)
        if sala_remota != sala_actual:
            log_net.debug(f"Enemigo muerto en otra sala {sala_remota}, ignorando")
            return

        # Validate that room exists (dungeon may have different sizes between clients)
        try:
            room = self.dungeon.rooms[sala_remota[0]][sala_remota[1]]
        except (KeyError, IndexError, TypeError) as e:
            log_net.warning(f"Sala {sala_remota} no existe en este dungeon: {e}")
            return
        except Exception as e:
            log_net.error(f"ERROR accediendo a rooms[{sala_remota}]: {e}", exc_info=True)
            return

        try:
            # Buscar enemigo que coincida con posición y tipo
            # Usar tolerancia para diferencias por interpolación cliente
            tolerance = 5.0  # píxeles

            for i, enemy in enumerate(room.enemies):
                dist = ((enemy.x - pos_x) ** 2 + (enemy.y - pos_y) ** 2) ** 0.5
                if dist <= tolerance and enemy.__class__.__name__ == enemy_type:
                    # Encontrado enemigo que coincide — removerlo
                    log_net.info(f"🗑️ Removiendo {enemy_type} en posición ({pos_x}, {pos_y})")
                    room.enemies.pop(i)
                    break
            else:
                log_net.debug(
                    f"No encontré {enemy_type} en ({pos_x}, {pos_y}) sala {sala_remota}"
                )
        except Exception as e:
            log_net.error(f"ERROR buscando/removiendo enemigo: {e}", exc_info=True)

    def _handle_remote_projectile(self, ev: EventoRed) -> None:
        """
        Recibe un proyectil disparado por otro jugador y lo crea localmente.
        """
        datos = ev.datos
        sala_remota_raw = datos.get("sala")
        # Convert to tuple (JSON deserializes tuples as lists)
        sala_remota = tuple(sala_remota_raw) if isinstance(sala_remota_raw, (list, tuple)) else (0, 0)

        # Solo procesar si está en sala actual
        sala_actual = (self.dungeon.i, self.dungeon.j)
        if sala_remota != sala_actual:
            return

        # Crear proyectil local
        from core.Projectile import Projectile

        proj = Projectile(
            x=datos.get("pos_x", 0),
            y=datos.get("pos_y", 0),
            dx=datos.get("dir_x", 0),
            dy=datos.get("dir_y", 0),
            speed=320.0,
            radius=4,
            color=(255, 230, 140),
            owner_id=ev.origen,
        )

        # Agregar a proyectiles remotos
        self.remote_projectiles.append(proj)
        log_net.debug(f"Proyectil remoto de {ev.origen}")

    def _handle_remote_damage(self, ev: EventoRed) -> None:
        """
        Aplica daño a un enemigo reportado por otro jugador.
        """
        datos = ev.datos
        sala_remota_raw = datos.get("sala")
        # Convert to tuple (JSON deserializes tuples as lists)
        sala_remota = tuple(sala_remota_raw) if isinstance(sala_remota_raw, (list, tuple)) else (0, 0)

        sala_actual = (self.dungeon.i, self.dungeon.j)
        if sala_remota != sala_actual:
            return 

        pos_x = datos.get("pos_x")
        pos_y = datos.get("pos_y")
        damage = datos.get("damage", 1)
        enemy_type = datos.get("enemy_type")

        # Validate that room exists
        try:
            room = self.dungeon.rooms[sala_remota[0]][sala_remota[1]]
        except (KeyError, IndexError, TypeError) as e:
            log_net.warning(f"Sala {sala_remota} no existe en este dungeon: {e}")
            return
        except Exception as e:
            log_net.error(f"ERROR accediendo a rooms[{sala_remota}]: {e}", exc_info=True)
            return

        try:
            tolerance = 5.0

            for enemy in room.enemies:
                dist = ((enemy.x - pos_x) ** 2 + (enemy.y - pos_y) ** 2) ** 0.5
                if dist <= tolerance and enemy.__class__.__name__ == enemy_type:
                    # Aplica el daño PERO sin enviar otro evento (para evitar loops infinitos)
                    if hasattr(enemy, "take_damage"):
                        enemy.take_damage(damage, None)
                    else:
                        enemy.hp -= damage
                    break
        except Exception as e:
            log_net.error(f"ERROR aplicando daño remoto: {e}", exc_info=True)

    def _on_player_shoot(self, pos: tuple[float, float], direction: tuple[float, float]) -> None:
        """Callback when player fires - send network event."""
        if not self.net:
            return

        from network.protocol import msg_proyectil_disparado

        weapon_id = getattr(self.player.weapon, "weapon_id", "default") if self.player.weapon else "default"
        sala_actual = (self.dungeon.i, self.dungeon.j)

        evento = msg_proyectil_disparado(
            pos_x=pos[0],
            pos_y=pos[1],
            dir_x=direction[0],
            dir_y=direction[1],
            weapon_id=weapon_id,
            sala=sala_actual,
        )

        self.net.enviar(evento)

    def add_pause_menu_button(
        self,
        button: PauseMenuButton,
        *,
        handler: Callable[[], bool | None] | None = None,
    ) -> None:
        """Permite añadir botones adicionales al menú de pausa."""

        self.pause_menu_buttons.append(button)
        if handler is not None:
            self.pause_menu_handlers[button.action] = handler

    def _show_pause_menu(self) -> None:
        pygame.mouse.set_visible(True)
        background = self.screen.copy()
        pause_menu = PauseMenu(self.screen, buttons=self.pause_menu_buttons)
        action = pause_menu.run(background=background)
        keep_playing = self._handle_pause_action(action)
        if keep_playing and self.running:
            pygame.mouse.set_visible(False)
        self.clock.tick(self.cfg.FPS)
        self._skip_frame = True

    def _handle_pause_action(self, action: str) -> bool:
        if action == "resume":
            return True
        if action == "main_menu":
            self._stats_pending_reason = "menu_restart"
            return self._open_start_menu()
        if action == "quit":
            self._finalize_run_statistics("quit")
            self.running = False
            return False

        handler = self.pause_menu_handlers.get(action)
        if handler is not None:
            result = handler()
            if result is False:
                self._finalize_run_statistics(f"handler:{action}")
                self.running = False
                return False
            return True

        return True

    def _update_fps_counter(self) -> None:
        self._frame_counter += 1
        if self._frame_counter % 90 == 0:
            debug_tag = " [DEBUG]" if self._debug_mode else ""
            pygame.display.set_caption(
                f"Echoes — Seed {self.current_seed} — FPS {self.clock.get_fps():.1f}{debug_tag}"
            )

    def _update(self, dt: float, events: list) -> None:
        # --- Networking: procesar eventos de red y enviar estado ---
        if self.net:
            # Preparar estado local (ambos roles envían para sincronización)
            estado_local = None
            ahora = time.time()
            if ahora - self._last_state_send >= self._send_state_interval:
                estado_local = {
                    "pos_x": self.player.x,
                    "pos_y": self.player.y,
                    "sala": (self.dungeon.i, self.dungeon.j),
                    "hp": int(self.player.hp),
                    "vidas": int(getattr(self.player, "lives", 0)),
                    "apoyo": int(getattr(self.player, "gold", 0)),
                }
                self._last_state_send = ahora

            # Procesar red y enviar estado
            net_eventos = self.net.tick(estado_local=estado_local)
            for ev in net_eventos:
                self._procesar_evento_red(ev)

        # Subtítulos: expirar entradas en cada frame independientemente del estado
        self.subtitulos.tick(dt)

        # --- Cinematicas ---
        # Si una cinemática está activa, procesar input y no actualizar el juego
        if self.cinematics.activo:
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # ESC: salta la cinemática completa
                        self.cinematics.saltar()
                    elif event.key == pygame.K_RETURN:
                        # Enter: salta la cinemática completa
                        self.cinematics.saltar()
                    elif event.key == pygame.K_SPACE:
                        # Espacio: avanza panel / completa texto
                        self.cinematics.siguiente_panel()
            self.cinematics.tick(dt)
            return

        # --- Diálogos ---
        # Si un diálogo está activo, procesar eventos y actualizar
        if self.dialogue.activo:
            for ev in events:
                self.dialogue.handle_event(ev)
            self.dialogue.tick(dt)
            return

        # Hot-reload: verificar si algún asset cambió en disco
        self.asset_watcher.tick()

        # --- Trigger intro cinemática en primer frame ---
        if not self._intro_played:
            self._intro_played = True
            self.cinematics.reproducir("intro")
            return

        room = self.dungeon.current_room

        # --- Profesor Ibarra: bloquear gameplay durante la pregunta o tienda ---
        if getattr(room, "type", "") == "profesor_ibarra":
            prof = getattr(room, "profesor_ibarra", None)
            if prof is not None and prof.estado in (prof.PREGUNTA, prof.FEEDBACK, prof.TIENDA):
                room.handle_events(
                    events, self.player, self.shop,
                    self.world, self.ui_font, self.cfg.SCREEN_SCALE,
                )
                # Consumir efectos pendientes del profesor
                self._apply_ibarra_pending_effects(prof, room)
                return

        self._update_player(dt, room)
        self._spawn_room_enemies(room)
        self._update_enemies(dt, room)
        self._update_projectiles(dt, room)
        player_died = self._handle_collisions(room)
        if player_died:
            return
        self._update_pickups(dt, room)
        self._handle_room_transition(room)
        self._update_shop(events)

        # --- Trigger entrada a sala de Mara (cinemática única) ---
        self._check_mara_room_entry(room)

        # --- Trigger transiciones de zona ---
        self._check_zone_transitions()

        # --- Trigger diálogos con Mara ---
        self._check_mara_dialogue_request(room, events)

    def _update_player(self, dt: float, room) -> None:
        # Modo dios: mantener el timer de invulnerabilidad alto
        if getattr(self.player, "_debug_god_mode", False):
            self.player.invulnerable_timer = 9999.0

        self.player.update(dt, room, self.projectiles)

    def _spawn_room_enemies(self, room) -> None:
        if getattr(room, "no_spawn", False):
            return

        # Salas especiales sin enemigos
        if getattr(room, "type", "normal") in ("safe_mara", "profesor_ibarra"):
            return  # Salas especiales sin combate

        cx, cy = self.dungeon.grid_w // 2, self.dungeon.grid_h // 2
        is_start = (self.dungeon.i, self.dungeon.j) == getattr(self.dungeon, "start", (cx, cy))
        if is_start:
            return
        if hasattr(room, "ensure_spawn"):
            pos = (self.dungeon.i, self.dungeon.j)
            depth = 0
            if hasattr(self.dungeon, "room_depth"):
                depth = self.dungeon.room_depth(pos)
            branch_factor = max(0, sum(1 for open_ in getattr(room, "doors", {}).values() if open_) - 2)
            on_main_path = 0
            if hasattr(self.dungeon, "main_path"):
                on_main_path = 1 if pos in self.dungeon.main_path else 0
            difficulty = 1 + depth + branch_factor + (depth // 3) + on_main_path
            room.ensure_spawn(difficulty=difficulty)

    def _get_closest_player_for_enemy(self, enemy) -> object:
        """
        Retorna el jugador (local o remoto) más cercano al enemigo.

        Esto permite que los enemigos ataquen al jugador más cercano
        en modo multijugador cooperativo.
        """
        import math

        ex, ey = enemy._center()

        # Distancia al jugador local
        local_x = self.player.x + self.player.w / 2
        local_y = self.player.y + self.player.h / 2
        local_dist = math.hypot(local_x - ex, local_y - ey)

        # Distancia al jugador remoto (si existe)
        remote_dist = float('inf')
        remote_pos = None

        if self.remote_players:
            for rol, datos in self.remote_players.items():
                sala_list = datos.get("sala", [0, 0])
                sala_remota = (
                    (sala_list[0], sala_list[1])
                    if isinstance(sala_list, (list, tuple))
                    else (0, 0)
                )

                # Solo considerar si está en la misma sala
                if sala_remota == (self.dungeon.i, self.dungeon.j):
                    remote_x = datos.get("pos_x", 0)
                    remote_y = datos.get("pos_y", 0)
                    remote_dist = math.hypot(
                        (remote_x + 9) - ex,
                        (remote_y + 12) - ey
                    )
                    remote_pos = (remote_x, remote_y)
                    break

        # Retornar el jugador más cercano
        if remote_dist < local_dist and remote_pos:
            # Crear un objeto "jugador fantasma" con posición remota
            class RemotePlayer:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y
                    self.w = 18
                    self.h = 24

            return RemotePlayer(remote_pos[0], remote_pos[1])
        else:
            return self.player

    def _update_enemies(self, dt: float, room) -> None:
        if not hasattr(room, "enemies"):
            return
        for enemy in room.enemies:
            # Obtener el jugador más cercano (local o remoto)
            closest_player = self._get_closest_player_for_enemy(enemy)
            enemy.update(dt, closest_player, room)
        notify = getattr(self.player, "notify_enemy_shot", None)
        for enemy in room.enemies:
            # Obtener el jugador más cercano para disparo también
            closest_player = self._get_closest_player_for_enemy(enemy)
            fired = enemy.maybe_shoot(dt, closest_player, room, self.enemy_projectiles)
            if fired and callable(notify):
                notify()

    def _update_projectiles(self, dt: float, room) -> None:
        self.projectiles.update(dt, room)
        self.enemy_projectiles.update(dt, room)

        # NEW: Update remote projectiles
        if self.remote_projectiles:
            for proj in self.remote_projectiles[:]:
                proj.update(dt, room)
                if not proj.alive:
                    self.remote_projectiles.remove(proj)

    def _handle_collisions(self, room) -> bool:
        if not hasattr(room, "enemies"):
            return False
        initial_enemy_count = len(getattr(room, "enemies", ()))
        for projectile in self.projectiles:
            if not projectile.alive:
                continue
            r_proj = projectile.rect()
            for enemy in room.enemies:
                if r_proj.colliderect(enemy.rect()):
                    if hasattr(enemy, "take_damage"):
                        enemy.take_damage(1, (projectile.dx, projectile.dy))
                    else:
                        enemy.hp -= 1
                    self._apply_projectile_effects(projectile, enemy)
                    projectile.alive = False
                    break

        # Remote projectiles from other players also hit enemies
        for projectile in self.remote_projectiles[:]:
            if not projectile.alive:
                continue
            r_proj = projectile.rect()
            for enemy in room.enemies:
                if r_proj.colliderect(enemy.rect()):
                    if hasattr(enemy, "take_damage"):
                        enemy.take_damage(1, (projectile.dx, projectile.dy))
                    else:
                        enemy.hp -= 1
                    self._apply_projectile_effects(projectile, enemy)
                    projectile.alive = False
                    break

        player_rect = self.player.rect()
        player_invulnerable = getattr(self.player, "is_invulnerable", lambda: False)()
        phase_active = getattr(self.player, "is_phase_active", None)
        phase_through = phase_active() if callable(phase_active) else False
        for enemy in room.enemies:
            if not player_rect.colliderect(enemy.rect()):
                continue
            if phase_through:
                continue
            self._separate_player_enemy(enemy, room)
            if hasattr(enemy, "trigger_attack_animation"):
                ex = enemy.x + enemy.w/2
                px = self.player.x + self.player.w/2
                enemy.trigger_attack_animation(px - ex)
            contact_damage = getattr(enemy, "contact_damage", 0)
            if contact_damage <= 0:
                continue
            if player_invulnerable:
                continue
            took_hit = False
            if hasattr(self.player, "take_damage"):
                took_hit = bool(self.player.take_damage(contact_damage))
            if took_hit:
                player_invulnerable = getattr(self.player, "is_invulnerable", lambda: False)()
        for projectile in self.enemy_projectiles:
            if not projectile.alive:
                continue
            if projectile.ignore_player_timer > 0.0:
                continue
            if not projectile.rect().colliderect(player_rect):
                continue
            if player_invulnerable:
                remaining_iframes = getattr(self.player, "invulnerable_timer", 0.0)
                projectile.ignore_player_timer = max(
                    projectile.ignore_player_timer,
                    remaining_iframes + 0.05,
                )
                continue
            took_hit = False
            if hasattr(self.player, "take_damage"):
                took_hit = bool(self.player.take_damage(1))
            if took_hit:
                projectile.alive = False
                player_invulnerable = getattr(self.player, "is_invulnerable", lambda: False)()
            else:
                projectile.alive = False

        survivors = []
        for enemy in room.enemies:
            ready_fn = getattr(enemy, "is_ready_to_remove", None)
            dying_fn = getattr(enemy, "is_dying", None)
            if callable(ready_fn) and ready_fn():
                self._drop_enemy_coins(enemy, room)

                # Notify other players that this enemy died
                if self.net:
                    from network.protocol import msg_enemigo_muerto
                    enemy_type = enemy.__class__.__name__
                    sala = (self.dungeon.i, self.dungeon.j)
                    event_msg = msg_enemigo_muerto(
                        pos_x=enemy.x,
                        pos_y=enemy.y,
                        tipo=enemy_type,
                        sala=sala
                    )
                    self.net.enviar(event_msg)

                continue
            if callable(dying_fn) and dying_fn():
                survivors.append(enemy)
                continue
            if getattr(enemy, "hp", 1) > 0:
                survivors.append(enemy)
            else:
                self._drop_enemy_coins(enemy, room)
        defeated_enemies = max(0, initial_enemy_count - len(survivors))
        if defeated_enemies:
            self._run_kills = max(0, self._run_kills) + defeated_enemies
            try:
                self.stats_manager.record_kill(defeated_enemies)
            except Exception as exc:  # pragma: no cover - registro best effort
                log_game.warning(f"No se pudo guardar kills: {exc}")
        room.enemies = survivors
        self.projectiles.prune()
        self.enemy_projectiles.prune()
        if hasattr(room, "refresh_lock_state"):
            room.refresh_lock_state()
        self._update_room_lock(room)
        if getattr(self.player, "hp", 1) <= 0:
            self._handle_player_death(room)
            return True
        return False

    def _drop_enemy_coins(self, enemy, room) -> None:
        total_value = int(getattr(enemy, "gold_reward", 0))
        if total_value <= 0:
            return
        if not hasattr(room, "pickups"):
            room.pickups = []

        min_count, max_count = self._coin_count_for_reward(total_value)
        max_count = max(1, min(total_value, max_count))
        min_count = max(1, min(min_count, max_count))
        count = random.randint(min_count, max_count)
        count = max(1, min(count, total_value))

        base_value, remainder = divmod(total_value, count)
        values = [base_value] * count
        if remainder:
            for idx in random.sample(range(count), remainder):
                values[idx] += 1

        sprite_w = self._coin_pickup_sprite.get_width()
        sprite_h = self._coin_pickup_sprite.get_height()
        center_x = enemy.x + enemy.w / 2.0
        center_y = enemy.y + enemy.h / 2.0

        for value in values:
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(70.0, 130.0)
            jitter_x = math.cos(angle) * 4.0
            jitter_y = math.sin(angle) * 4.0
            pickup = Pickup(
                center_x - sprite_w / 2.0 + jitter_x,
                center_y - sprite_h / 2.0 + jitter_y,
                value,
                self._coin_pickup_sprite,
                angle=angle,
                speed=speed,
            )
            room.pickups.append(pickup)

    def _coin_count_for_reward(self, total_value: int) -> tuple[int, int]:
        if total_value <= 5:
            return (1, 2)
        if total_value <= 9:
            return (2, 3)
        return (3, 4)

    def _update_pickups(self, dt: float, room) -> None:
        pickups = getattr(room, "pickups", None)
        if pickups is None or not pickups:
            if pickups is None:
                room.pickups = []
            return

        player_rect = self.player.rect()
        collected_total = 0
        survivors: list[Pickup] = []
        for pickup in pickups:
            pickup.update(dt, room)
            if pickup.collected:
                continue
            if player_rect.colliderect(pickup.rect()):
                pickup.collect()
                collected_total += pickup.value
            else:
                survivors.append(pickup)
        room.pickups = survivors
        if collected_total:
            self._add_player_gold(collected_total)

    def _add_player_gold(self, amount: int) -> None:
        amount = int(amount)
        if amount <= 0:
            return
        current_gold = getattr(self.player, "gold", 0)
        setattr(self.player, "gold", current_gold + amount)

    def _apply_projectile_effects(self, projectile, enemy) -> None:
        effects = getattr(projectile, "effects", ())
        if not effects:
            return
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            etype = effect.get("type")
            if etype == "shock":
                slow = float(effect.get("slow", 0.2))
                duration = float(effect.get("duration", 0.6))
                applier = getattr(enemy, "apply_slow", None)
                if callable(applier):
                    applier(slow, duration)

    def _separate_player_enemy(self, enemy, room) -> None:
        player_rect = self.player.rect()
        if not player_rect.colliderect(enemy.rect()):
            return

        enemy_rect = enemy.rect()
        px, py = player_rect.center
        ex, ey = enemy_rect.center
        primary_axis = 'x' if abs(ex - px) >= abs(ey - py) else 'y'

        for axis in (primary_axis, 'y' if primary_axis == 'x' else 'x'):
            original_pos = enemy.x if axis == 'x' else enemy.y
            direction = 1 if ((ex - px) if axis == 'x' else (ey - py)) >= 0 else -1
            moved = False
            limit = max(enemy.w, enemy.h) + 2
            for _ in range(limit):
                if axis == 'x':
                    enemy.x += direction
                else:
                    enemy.y += direction
                if enemy._collides(room):
                    if axis == 'x':
                        enemy.x -= direction
                    else:
                        enemy.y -= direction
                    break
                if not player_rect.colliderect(enemy.rect()):
                    moved = True
                    break
            if moved:
                push_dir = (
                    enemy.rect().centerx - player_rect.centerx,
                    enemy.rect().centery - player_rect.centery,
                )
                if hasattr(enemy, "take_damage"):
                    enemy.take_damage(0, push_dir, stun_duration=0.0, knockback_strength=120.0)
                return
            if axis == 'x':
                enemy.x = original_pos
            else:
                enemy.y = original_pos

        # Último recurso: reposicionar a borde del jugador
        enemy_rect = enemy.rect()
        ex, ey = enemy_rect.center
        if abs(ex - px) >= abs(ey - py):
            if ex >= px:
                enemy.x = player_rect.right
            else:
                enemy.x = player_rect.left - enemy.w
        else:
            if ey >= py:
                enemy.y = player_rect.bottom
            else:
                enemy.y = player_rect.top - enemy.h

    def _handle_player_death(self, room) -> None:
        log_player.warning("Jugador murió — lives=%s", getattr(self.player, "lives", "?"))
        can_continue = False
        if hasattr(self.player, "lose_life"):
            try:
                can_continue = bool(self.player.lose_life())
            except TypeError:
                can_continue = False

        if can_continue:
            if hasattr(self.player, "respawn"):
                self.player.respawn()
            else:
                max_hp = getattr(self.player, "max_hp", 1)
                self.player.hp = max_hp
                invuln = getattr(self.player, "post_hit_invulnerability", 0.0)
                self.player.invulnerable_timer = max(
                    getattr(self.player, "invulnerable_timer", 0.0), invuln
                )

            if hasattr(room, "center_px"):
                px, py = room.center_px()
                self.player.x = px - self.player.w / 2
                self.player.y = py - self.player.h / 2

            self.projectiles.clear()
            self.enemy_projectiles.clear()
            self.door_cooldown = 0.25
            return

        summary = self._collect_run_summary()
        self._record_stats_death()
        self._finalize_run_statistics("player_death")

        action = self._show_game_over_screen(summary)

        if action == "quit":
            self.running = False
            return

        if action == "main_menu":
            if not self._open_start_menu():
                self.running = False
            return

        # Cualquier otra acción reinicia la partida con nueva seed.
        self.start_new_run(seed=None)

    def _record_stats_death(self) -> None:
        try:
            self.stats_manager.record_death()
        except Exception as exc:  # pragma: no cover - registro best effort
            log_game.warning(f"No se pudo guardar muerte: {exc}")

    def _collect_run_summary(self) -> dict[str, int]:
        rooms_explored = 0
        dungeon = getattr(self, "dungeon", None)
        if dungeon is not None and hasattr(dungeon, "explored"):
            try:
                rooms_explored = len(dungeon.explored)
            except TypeError:
                rooms_explored = 0

        gold = 0
        player = getattr(self, "player", None)
        if player is not None:
            try:
                gold = int(getattr(player, "gold", 0))
            except (TypeError, ValueError):
                gold = 0

        gold_spent = max(0, int(self._run_gold_spent))
        coins_obtained = max(0, gold) + gold_spent

        return {
            "coins": coins_obtained,
            "kills": max(0, int(self._run_kills)),
            "rooms": max(0, rooms_explored),
        }

    def _show_game_over_screen(self, summary: dict[str, int]) -> str:
        pygame.mouse.set_visible(True)
        background = self.screen.copy()
        game_over = GameOverScreen(self.screen)
        action = game_over.run(summary, background=background)

        if action not in ("main_menu", "quit"):
            pygame.mouse.set_visible(False)

        self.clock.tick(self.cfg.FPS)
        self._skip_frame = True
        return action

    def _handle_room_transition(self, room) -> None:
        if not hasattr(room, "check_exit"):
            return
        if getattr(room, "locked", False):
            return
        if self.door_cooldown > 0.0:
            return

        direction = room.check_exit(self.player)
        if not direction or not self.dungeon.can_move(direction):
            return

        if hasattr(self.dungeon, "move_and_enter"):
            moved = self.dungeon.move_and_enter(direction, self.player, self.cfg, ShopkeeperCls=Shopkeeper)
        else:
            self.dungeon.move(direction)
            moved = True
        if not moved:
            return

        self.player.x, self.player.y = self.dungeon.entry_position(
            direction, self.player.w, self.player.h
        )
        self.dungeon.explored.add((self.dungeon.i, self.dungeon.j))
        self.door_cooldown = 0.25
        self.projectiles.clear()
        self.enemy_projectiles.clear()

        new_room = self.dungeon.current_room
        depth = self.dungeon.depth_map.get((self.dungeon.i, self.dungeon.j), -1)
        log_room.room_enter((self.dungeon.i, self.dungeon.j), depth)
        self._spawn_room_enemies(new_room)
        self._update_room_lock(new_room)

    def _update_room_lock(self, room) -> None:
        if not hasattr(room, "enemies") or not hasattr(room, "cleared"):
            return
        cx, cy = self.dungeon.grid_w // 2, self.dungeon.grid_h // 2
        is_start = (self.dungeon.i, self.dungeon.j) == getattr(self.dungeon, "start", (cx, cy))
        room.locked = (not is_start) and (len(room.enemies) > 0) and (not room.cleared)

    def _use_ibarra_item(self, iid: str) -> None:
        """Activa un ítem guardado del Profesor Ibarra (EMP con Q, Modo Privado con R)."""
        if iid == "emp":
            if not getattr(self.player, "_ibarra_emp", False):
                return
            self.player._ibarra_emp = False
            room = self.dungeon.current_room
            count = 0
            for enemy in getattr(room, "enemies", []):
                try:
                    enemy.stun_timer = max(getattr(enemy, "stun_timer", 0.0), 4.0)
                    count += 1
                except Exception:
                    pass
            if hasattr(self, "subtitulos"):
                self.subtitulos.agregar(f"[EMP] {count} enemigos congelados!", duracion=2.5, tipo="apoyo")
            log_game.info("EMP usado: %d enemigos congelados", count)

        elif iid == "modo_privado":
            if not getattr(self.player, "_ibarra_modo_privado", False):
                return
            self.player._ibarra_modo_privado = False
            current = getattr(self.player, "invulnerable_timer", 0.0)
            self.player.invulnerable_timer = max(current, 5.0)
            if hasattr(self, "subtitulos"):
                self.subtitulos.agregar("[Modo Privado] Invulnerable 5s!", duracion=2.5, tipo="apoyo")
            log_game.info("Modo Privado usado: invulnerable 5s")

    def _draw_ibarra_item_hud(self, surface: pygame.Surface) -> None:
        """Dibuja iconos HUD en la esquina inferior derecha para EMP (Q) y Modo Privado (R)."""
        has_emp  = getattr(self.player, "_ibarra_emp", False)
        has_modo = getattr(self.player, "_ibarra_modo_privado", False)

        if not has_emp and not has_modo:
            return

        icon_size = 44
        padding   = 8
        margin_r  = 16   # margen desde el borde derecho
        margin_b  = 16   # margen desde el borde inferior
        sw, sh    = surface.get_size()

        items_to_draw = []
        if has_emp:
            items_to_draw.append({"color": (220, 190, 40), "char": "~", "key": "Q",  "name": "EMP"})
        if has_modo:
            items_to_draw.append({"color": (60, 140, 230), "char": "M", "key": "R",  "name": "Modo P."})

        font = self.ui_font

        # Calcular posición inicial (derecha → izquierda)
        total_w = len(items_to_draw) * icon_size + (len(items_to_draw) - 1) * padding
        x_start = sw - margin_r - total_w
        y       = sh - margin_b - icon_size - font.get_height() - 4

        for i, item in enumerate(items_to_draw):
            ix = x_start + i * (icon_size + padding)

            # Fondo sólido del icono (sin SRCALPHA para máxima compatibilidad)
            bg = pygame.Surface((icon_size, icon_size))
            bg.fill((20, 20, 30))
            pygame.draw.rect(bg, item["color"], (2, 2, icon_size - 4, icon_size - 4))
            pygame.draw.rect(bg, (255, 255, 255), (0, 0, icon_size, icon_size), 2)

            # Carácter grande en el centro
            ch = font.render(item["char"], True, (255, 255, 255))
            bg.blit(ch, (icon_size // 2 - ch.get_width() // 2,
                         icon_size // 2 - ch.get_height() // 2 - 3))

            # Etiqueta de tecla abajo del icono
            key_lbl = font.render(f"[{item['key']}]", True, (200, 200, 200))
            surface.blit(bg, (ix, y))
            surface.blit(key_lbl, (ix + icon_size // 2 - key_lbl.get_width() // 2,
                                    y + icon_size + 2))

    def _update_shop(self, events: list) -> None:
        current_room = self.dungeon.current_room
        if hasattr(current_room, "handle_events"):
            current_room.handle_events(
                events,
                self.player,
                self.shop,
                self.world,
                self.ui_font,
                self.cfg.SCREEN_SCALE,
            )

    def _apply_ibarra_pending_effects(self, prof, room) -> None:
        """
        Consume efectos pendientes inmediatos del Profesor Ibarra.

        - map_reveal_pending: agrega todas las salas del dungeon al set explored.
        (EMP y Modo Privado se usan con Q/R, no son pendientes inmediatos)
        """
        if prof.map_reveal_pending:
            prof.map_reveal_pending = False
            dungeon = self.dungeon
            if hasattr(dungeon, "rooms") and hasattr(dungeon, "explored"):
                try:
                    for pos in dungeon.rooms:
                        dungeon.explored.add(pos)
                    log_game.info("Ibarra Evidencia Guardada: mapa revelado (%d salas)", len(dungeon.rooms))
                except Exception as exc:
                    log_game.warning("map_reveal_pending error: %s", exc)
            if hasattr(self, "subtitulos"):
                self.subtitulos.agregar("[Mapa revelado]", duracion=2.5, tipo="apoyo")

    def _check_mara_room_entry(self, room) -> None:
        """
        Verifica si el jugador entró a la sala segura de Mara (type='safe_mara').

        Si es la primera vez que entra, dispara la cinemática 'mara_encounter' una sola vez.
        Las entradas posteriores no disparan cinemática.
        """
        # Verificar que ya se marcó la sala de Mara en el dungeon
        if not hasattr(self.dungeon, "mara_pos"):
            return

        current_pos = (self.dungeon.i, self.dungeon.j)

        # ¿Estamos en la sala de Mara?
        if current_pos != self.dungeon.mara_pos:
            return

        # ¿Ya se disparó la cinemática en esta partida?
        if self._mara_cutscene_played:
            log_game.debug(f"Mara room entrada ignorada (ya se reprodujo cinemática)")
            return

        # ¿La cinemática ya está en reproducción? (evitar restart múltiples)
        if self.cinematics.activo:
            log_game.debug(f"Mara cinematic already playing, skipping restart")
            return

        # Primera entrada: disparar cinemática y marcar como reproducida
        log_game.info(f"[CINEMATIC] Primera entrada a sala de Mara - reproduciendo cinematica mara_encounter")
        result = self.cinematics.reproducir("mara_encounter")
        if result:
            self._mara_cutscene_played = True
            log_game.debug(f"Flag _mara_cutscene_played = {self._mara_cutscene_played}")
        else:
            log_game.warning(f"Failed to play mara_encounter cinematic")

    def _check_zone_transitions(self) -> None:
        """
        Verifica si el jugador ha entrado en una nueva zona y dispara la cinemática
        de transición correspondiente.

        Las zonas se asignan por profundidad BFS en el dungeon:
        - Zona 1: depth 0-3
        - Zona 2: depth 4+ (incluye el final del juego)

        NOTA: La cinemática de Mara (mara_encounter) se dispara en _check_mara_room_entry(),
        no aquí. Solo las transiciones de zona general se disparan aquí.
        """
        if not hasattr(self.dungeon, "room_zone"):
            return

        current_pos = (self.dungeon.i, self.dungeon.j)
        new_zone = self.dungeon.room_zone(current_pos)

        if new_zone is None:
            return

        # Si la zona cambió, disparar cinemática de transición (excepto si es Zona 2 con Mara especial)
        if new_zone != self._current_zone:
            old_zone = self._current_zone
            self._current_zone = new_zone

            # Determinar qué cinemática reproducir según la transición
            # Nota: Zona 2 Ya no dispara cinemática aquí - se maneja en _check_mara_room_entry()
            cinematic_id = f"zone_transition_{new_zone}"
            self.cinematics.reproducir(cinematic_id)

    def _on_mara_dialogue_finished(self) -> None:
        """
        Callback ejecutado cuando termina el diálogo con Mara.
        Detecta si el jugador eligió una opción compasiva y otorga fragmento de empatía.
        """
        # Obtener el nodo actual (la opción elegida por el jugador)
        nodo = self.dialogue.obtener_nodo_actual()
        if nodo is None:
            return

        # Verificar si la opción fue compasiva (meta tiene es_empatia=true)
        meta = nodo.meta or {}
        es_empatia = meta.get("es_empatia", False)

        if es_empatia:
            # Otorgar fragmento de empatía
            self.player.empathy_fragments += 1
            log_game.info(f"✨ +1 Fragmento de Empatía - Total: {self.player.empathy_fragments}")

    def _check_mara_dialogue_request(self, room, events) -> None:
        """
        Verifica si el jugador ha solicitado un diálogo con Mara.

        El diálogo se inicia cuando:
        1. Estamos en la sala de Mara (type='safe_mara')
        2. El jugador presionó E cerca de ella
        """
        if not hasattr(room, "_mara_dialogue_requested"):
            return

        if not getattr(room, "_mara_dialogue_requested", False):
            return

        # Limpiar el flag
        room._mara_dialogue_requested = False

        # Snapshot del apoyo antes del diálogo para calcular la ganancia al terminar
        apoyo_antes = self._estado_juego.get("apoyo", 0)

        def _on_fin_mara():
            ganado = self._estado_juego.get("apoyo", 0) - apoyo_antes
            if ganado > 0:
                self.subtitulos.agregar(
                    f"[FRAGMENTO DE EMPATÍA +{ganado}]",
                    duracion=3.5,
                    tipo="apoyo",
                )
                log_game.info("Fragmento de empatía ganado al hablar con Mara: +%d", ganado)

        # Iniciar diálogo con Mara, conectado al estado del juego
        self.dialogue.iniciar(
            "mara",
            estado_juego=self._estado_juego,
            callback_fin=_on_fin_mara,
        )

    def _render(self) -> None:
        self._render_world()
        self._render_ui()

    def _render_world(self) -> None:
        self.world.fill(self.cfg.COLOR_BG)
        room = self.dungeon.current_room
        room.draw(self.world, self.tileset)

        if hasattr(room, "enemies"):
            for enemy in room.enemies:
                enemy.draw(self.world)

        for pickup in getattr(room, "pickups", ()): 
            pickup.draw(self.world)

        self.player.draw(self.world)

        # --- Dibujar jugadores remotos (cubo negro) ---
        for rol, datos in self.remote_players.items():
            # Extraer posición: el protocolo usa "pos": [x, y]
            pos = datos.get("pos")
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                x, y = float(pos[0]), float(pos[1])
            else:
                x = float(datos.get("pos_x", 0))
                y = float(datos.get("pos_y", 0))

            # Extraer sala: el protocolo usa "sala": [i, j]
            sala_list = datos.get("sala")
            if isinstance(sala_list, (list, tuple)) and len(sala_list) >= 2:
                sala_remota = (int(sala_list[0]), int(sala_list[1]))
            else:
                sala_remota = (0, 0)

            sala_actual = (self.dungeon.i, self.dungeon.j)
            if sala_remota == sala_actual:
                # Cubo negro 32x32 (tamaño del sprite)
                pygame.draw.rect(self.world, (0, 0, 0), (int(x), int(y), 32, 32), 2)

        self.projectiles.draw(self.world)
        self.enemy_projectiles.draw(self.world)

        # Draw remote projectiles from other players
        for proj in self.remote_projectiles:
            proj.draw(self.world)

        self._draw_debug_door_triggers(room)

        if hasattr(room, "draw_overlay"):
            room.draw_overlay(self.world, self.ui_font, self.player, self.shop)
        self.shop.draw(self.world)

    def _draw_debug_door_triggers(self, room) -> None:
        # Solo dibuja los triggers si el flag de debug está activo
        if not (self.debug_draw_doors or self._debug_mode):
            return
        for rect in room._door_trigger_rects().values():
            pygame.draw.rect(self.world, (0, 255, 0), rect, 1)

    def _render_ui(self) -> None:
        scaled = pygame.transform.scale(
            self.world,
            (self.cfg.SCREEN_W * self.cfg.SCREEN_SCALE,
             self.cfg.SCREEN_H * self.cfg.SCREEN_SCALE)
        )
        self.screen.blit(scaled, (0, 0))

        # --- Dibujar cinemáticas si están activas ---
        if self.cinematics.activo:
            # Llenar pantalla de negro para ocultar el juego de fondo
            self.screen.fill((0, 0, 0))

            self.cinematics.draw(self.screen, screen_scale=self.cfg.SCREEN_SCALE)
            # Dibujar el cursor encima
            mx, my = pygame.mouse.get_pos()
            cursor_rect = self._cursor_surface.get_rect(center=(mx, my))
            self.screen.blit(self._cursor_surface, cursor_rect.topleft)
            # Consola de debug encima de todo
            self.debug_console.draw(self.screen)
            pygame.display.flip()
            return

        # --- Dibujar diálogos si están activos ---
        if self.dialogue.activo:
            self.dialogue.draw(self.screen, screen_scale=self.cfg.SCREEN_SCALE)
            # Dibujar el cursor encima
            mx, my = pygame.mouse.get_pos()
            cursor_rect = self._cursor_surface.get_rect(center=(mx, my))
            self.screen.blit(self._cursor_surface, cursor_rect.topleft)
            # Consola de debug encima de todo
            self.debug_console.draw(self.screen)
            pygame.display.flip()
            return

        inventory_rect = self.hud_panels.blit_inventory_panel(self.screen)
        weapon_rect = self._draw_weapon_hud(inventory_rect)

        gold_amount = getattr(self.player, "gold", 0)
        microchip_rect = self._draw_coin_counter(inventory_rect, weapon_rect, gold_amount)

        seed_text = self.ui_font.render(f"Seed: {self.current_seed}", True, (230, 230, 230))

        text_x, text_y = self.hud_panels.inventory_content_anchor()
        if weapon_rect.width:
            text_x = max(text_x, weapon_rect.right + int(self.weapon_text_margin))
        if microchip_rect.width:
            text_x = max(text_x, microchip_rect.right + int(self.weapon_text_margin))
        line_gap = 6

        header_rect = pygame.Rect(0, 0, 0, 0)
        if weapon_rect.width and weapon_rect.height:
            header_rect = weapon_rect.copy()
        if microchip_rect.width and microchip_rect.height:
            header_rect = (
                header_rect.union(microchip_rect)
                if header_rect.width or header_rect.height
                else microchip_rect
            )
        if header_rect.height:
            text_y = max(text_y, header_rect.bottom + line_gap)

        battery_origin = (
            text_x + int(self._life_battery_offset.x),
            text_y + int(self._life_battery_offset.y),
        )
        batteries_rect = self._blit_life_batteries(self.screen, battery_origin)
        if batteries_rect.height:
            text_y = batteries_rect.bottom + line_gap

        seed_position = (20, 100)
        self.screen.blit(seed_text, seed_position)

        minimap_surface = self.minimap.render(self.dungeon)
        minimap_position = self.hud_panels.compute_minimap_position(self.screen, minimap_surface)
        self.hud_panels.blit_minimap_panel(self.screen, minimap_surface, minimap_position)

        self.hud_panels.blit_corner_panel(self.screen)

        # Contador de fragmentos de empatía
        self._draw_empathy_counter()

        # Iconos de ítems guardados del Profesor Ibarra (EMP / Modo Privado)
        self._draw_ibarra_item_hud(self.screen)

        # Notificaciones de subtítulos (fragmentos ganados, apoyos, etc.)
        self.subtitulos.draw(self.screen, screen_scale=self.cfg.SCREEN_SCALE)

        mx, my = pygame.mouse.get_pos()
        cursor_rect = self._cursor_surface.get_rect(center=(mx, my))
        self.screen.blit(self._cursor_surface, cursor_rect.topleft)

        # Consola de debug: se dibuja encima de todo, incluyendo el cursor
        self.debug_console.draw(self.screen)

        pygame.display.flip()

    def set_coin_icon_scale(self, scale: float) -> None:
        scale = max(0.1, float(scale))
        if math.isclose(scale, self.coin_icon_scale, rel_tol=1e-4, abs_tol=1e-4):
            return
        self.coin_icon_scale = scale
        self._coin_icon = self._scale_coin_icon(scale)

    def set_coin_icon_offset(
        self, offset: tuple[float, float] | pygame.Vector2
    ) -> None:
        if isinstance(offset, pygame.Vector2):
            self.coin_icon_offset.update(offset)
        else:
            ox, oy = offset
            self.coin_icon_offset.update(ox, oy)

    def set_coin_value_offset(
        self, offset: tuple[float, float] | pygame.Vector2
    ) -> None:
        if isinstance(offset, pygame.Vector2):
            self.coin_value_offset.update(offset)
        else:
            ox, oy = offset
            self.coin_value_offset.update(ox, oy)

    def _draw_coin_counter(
        self,
        inventory_rect: pygame.Rect,
        weapon_rect: pygame.Rect,
        amount: int,
    ) -> pygame.Rect:
        icon_surface = getattr(self, "_coin_icon", None)
        if icon_surface is None:
            return pygame.Rect(0, 0, 0, 0)

        if weapon_rect.width and weapon_rect.height:
            anchor_x, anchor_y = weapon_rect.topright
        else:
            anchor_x = inventory_rect.left + int(self.weapon_icon_offset.x)
            anchor_y = inventory_rect.top + int(self.weapon_icon_offset.y)

        icon_position = (
            int(anchor_x + self.coin_icon_offset.x),
            int(anchor_y + self.coin_icon_offset.y),
        )
        icon_rect = icon_surface.get_rect(topleft=icon_position)
        self.screen.blit(icon_surface, icon_rect.topleft)

        value_surface = self.ui_font.render(str(int(amount)), True, self.coin_value_color)
        value_rect = value_surface.get_rect()
        value_rect.midtop = (
            icon_rect.centerx + int(self.coin_value_offset.x),
            icon_rect.bottom + int(self.coin_value_offset.y),
        )
        self.screen.blit(value_surface, value_rect.topleft)

        return icon_rect.union(value_rect)

    def _draw_empathy_counter(self) -> None:
        apoyo = self._estado_juego.get("apoyo", 0)
        color = pygame.Color(100, 220, 255)
        label = f"[Empatia: {apoyo}]"
        surf = self.ui_font.render(label, True, color)
        # Debajo del seed text (seed esta en y=100), garantizado visible
        x = 20
        y = 120
        bg = pygame.Surface((surf.get_width() + 6, surf.get_height() + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        self.screen.blit(bg, (x - 3, y - 2))
        self.screen.blit(surf, (x, y))

    def _scale_coin_icon(self, scale: float) -> pygame.Surface:
        source = getattr(self, "_coin_icon_source", None)
        if source is None:
            source, _ = self._create_procedural_coin()
            self._coin_icon_source = source

        width = max(1, int(source.get_width() * scale))
        height = max(1, int(source.get_height() * scale))
        return pygame.transform.smoothscale(source, (width, height))

    def _create_coin_sprites(self) -> tuple[pygame.Surface, pygame.Surface]:
        procedural_icon, pickup_sprite = self._create_procedural_coin()
        sprite_path = assets_dir("ui", self.COIN_SPRITE_NAME)
        sprite = self._load_surface(sprite_path)
        icon_source = sprite if sprite is not None else procedural_icon
        return icon_source, pickup_sprite

    def _load_surface(self, path: Path) -> pygame.Surface | None:
        try:
            surface = pygame.image.load(path.as_posix()).convert_alpha()
            log_asset.asset_loaded(path.name)
            return surface
        except FileNotFoundError:
            log_asset.asset_missing(str(path))
        except pygame.error as exc:  # pragma: no cover - depende de SDL
            log_asset.asset_error(str(path), exc)
        return None

    def _create_procedural_coin(self) -> tuple[pygame.Surface, pygame.Surface]:
        base_size = 32
        chip = pygame.Surface((base_size, base_size), pygame.SRCALPHA)
        chip.fill((0, 0, 0, 0))

        body_rect = chip.get_rect().inflate(-8, -8)
        frame_color = pygame.Color(120, 20, 80)
        frame_shadow = pygame.Color(70, 10, 48)
        pygame.draw.rect(chip, frame_shadow, body_rect, border_radius=6)
        pygame.draw.rect(chip, frame_color, body_rect.inflate(-2, -2), border_radius=6)

        core_rect = body_rect.inflate(-8, -8)
        core_color = pygame.Color(28, 94, 116)
        core_dark = pygame.Color(12, 48, 64)
        pygame.draw.rect(chip, core_color, core_rect, border_radius=5)
        pygame.draw.rect(chip, core_dark, core_rect, width=2, border_radius=5)

        highlight = pygame.Surface(core_rect.size, pygame.SRCALPHA)
        light_a = pygame.Color(136, 236, 238, 190)
        light_b = pygame.Color(94, 204, 220, 140)
        start_y = core_rect.height // 3
        pygame.draw.line(highlight, light_a, (3, start_y), (core_rect.width - 4, start_y - 3), 3)
        pygame.draw.line(highlight, light_b, (3, start_y + 4), (core_rect.width - 6, start_y + 1), 2)
        chip.blit(highlight, core_rect.topleft)

        pin_color = pygame.Color(230, 176, 70)
        pin_shadow = pygame.Color(156, 116, 46)
        pin_w, pin_h = 5, 6
        slots = 4
        slot_spacing = (body_rect.height - 12) / max(1, slots - 1)
        for i in range(slots):
            offset = int(body_rect.top + 6 + i * slot_spacing)
            left_pin = pygame.Rect(0, 0, pin_w, pin_h)
            left_pin.midright = (body_rect.left - 1, offset)
            right_pin = pygame.Rect(0, 0, pin_w, pin_h)
            right_pin.midleft = (body_rect.right + 1, offset)
            pygame.draw.rect(chip, pin_color, left_pin)
            pygame.draw.rect(chip, pin_shadow, left_pin, 1)
            pygame.draw.rect(chip, pin_color, right_pin)
            pygame.draw.rect(chip, pin_shadow, right_pin, 1)

        slot_spacing = (body_rect.width - 12) / max(1, slots - 1)
        for i in range(slots):
            offset = int(body_rect.left + 6 + i * slot_spacing)
            top_pin = pygame.Rect(0, 0, pin_h, pin_w)
            top_pin.midbottom = (offset, body_rect.top - 1)
            bottom_pin = pygame.Rect(0, 0, pin_h, pin_w)
            bottom_pin.midtop = (offset, body_rect.bottom + 1)
            pygame.draw.rect(chip, pin_color, top_pin)
            pygame.draw.rect(chip, pin_shadow, top_pin, 1)
            pygame.draw.rect(chip, pin_color, bottom_pin)
            pygame.draw.rect(chip, pin_shadow, bottom_pin, 1)

        pickup = pygame.transform.smoothscale(chip, self.COIN_PICKUP_SIZE)
        return chip, pickup

    def _load_weapon_icons(self) -> dict[str, pygame.Surface]:
        icons: dict[str, pygame.Surface] = {}
        for weapon_id in WEAPON_SPRITE_FILENAMES:
            path = weapon_sprite_path(weapon_id)
            try:
                surface = pygame.image.load(path.as_posix()).convert_alpha()
                log_asset.asset_loaded(path.name)
            except FileNotFoundError:
                log_asset.asset_missing(str(path))
                surface = self._create_weapon_placeholder_icon(weapon_id)
            except pygame.error as exc:  # pragma: no cover - depende de SDL
                log_asset.asset_error(str(path), exc)
                surface = self._create_weapon_placeholder_icon(weapon_id)
            icons[weapon_id] = surface

        if "__missing__" not in icons:
            icons["__missing__"] = self._create_weapon_placeholder_icon(None)
        return icons

    def _create_weapon_placeholder_icon(self, weapon_id: str | None) -> pygame.Surface:
        size = 128
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))
        rect = surface.get_rect()
        base_color = pygame.Color(40, 44, 52, 200)
        frame_color = pygame.Color(120, 130, 150)
        pygame.draw.rect(surface, base_color, rect.inflate(-8, -8), border_radius=16)
        pygame.draw.rect(surface, frame_color, rect.inflate(-10, -10), width=3, border_radius=16)

        label = "???" if not weapon_id else weapon_id.replace("_", " ")
        label_surface = self.ui_font.render(label.upper(), True, (220, 220, 220))
        label_rect = label_surface.get_rect(center=rect.center)
        surface.blit(label_surface, label_rect.topleft)
        return surface

    def _get_scaled_weapon_icon(self, weapon_id: str, scale: float) -> pygame.Surface | None:
        base_id = weapon_id if weapon_id in self._weapon_icons else "__missing__"
        base_surface = self._weapon_icons.get(base_id)
        if base_surface is None:
            return None

        scale = max(0.05, float(scale))
        cache_key = (base_id, round(scale, 4))
        cached = self._weapon_icon_cache.get(cache_key)
        if cached is not None:
            return cached

        width = max(1, int(base_surface.get_width() * scale))
        height = max(1, int(base_surface.get_height() * scale))
        scaled = pygame.transform.smoothscale(base_surface, (width, height))
        self._weapon_icon_cache[cache_key] = scaled
        return scaled

    def _draw_weapon_hud(self, inventory_rect: pygame.Rect) -> pygame.Rect:
        player = getattr(self, "player", None)
        weapon = getattr(player, "weapon", None) if player is not None else None
        weapon_id = getattr(player, "weapon_id", None) if player is not None else None
        if weapon is None or weapon_id is None:
            return pygame.Rect(0, 0, 0, 0)

        icon_surface = self._get_scaled_weapon_icon(weapon_id, self.weapon_icon_scale)
        if icon_surface is None:
            return pygame.Rect(0, 0, 0, 0)

        base_x = inventory_rect.left + int(self.weapon_icon_offset.x)
        base_y = inventory_rect.top + int(self.weapon_icon_offset.y)
        icon_rect = icon_surface.get_rect(topleft=(base_x, base_y))
        self.screen.blit(icon_surface, icon_rect.topleft)

        # Munición eliminada: el jugador dispara infinitamente con cadencia fija
        return icon_rect

    def _create_cursor_surface(self) -> pygame.Surface:
        cursor_path = Path(__file__).resolve().parent.parent / "assets/ui/cursor2.png"
        try:
            surface = pygame.image.load(cursor_path.as_posix()).convert_alpha()
        except pygame.error as exc:  # pragma: no cover - carga de recursos
            raise FileNotFoundError(
                f"No se pudo cargar la imagen del cursor en {cursor_path}"
            ) from exc
        return surface

    def _load_battery_states(self) -> list[pygame.Surface]:
        sprite_path = Path(__file__).resolve().parent.parent / "assets/ui/Baterias_Vida.png"
        try:
            sheet = pygame.image.load(sprite_path.as_posix()).convert_alpha()
        except pygame.error as exc:  # pragma: no cover - carga de recursos
            raise FileNotFoundError(f"No se pudo cargar el sprite de baterías en {sprite_path}") from exc

        columns = 4
        frame_width = sheet.get_width() // columns
        frame_height = sheet.get_height()
        frames: list[pygame.Surface] = []
        for index in range(columns):
            frame = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), pygame.Rect(index * frame_width, 0, frame_width, frame_height))
            frames.append(frame)

        if not frames:
            raise ValueError("El sprite de baterías no contiene frames válidos")

        if len(frames) >= 4:
            empty_frame = frames[-1]
            filled_frames = frames[:-1]
        else:
            empty_frame = frames[0].copy()
            darken = pygame.Surface(empty_frame.get_size(), pygame.SRCALPHA)
            darken.fill((60, 60, 60, 255))
            empty_frame.blit(darken, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            filled_frames = frames

        return [empty_frame] + filled_frames

    def _player_hits_remaining(self) -> int:
        hits_remaining_life_fn = getattr(self.player, "hits_remaining_this_life", None)
        if callable(hits_remaining_life_fn):
            try:
                return int(hits_remaining_life_fn())
            except (TypeError, ValueError):
                pass
        return max(0, int(getattr(self.player, "hp", 0)))

    def _battery_surface(self, max_hp: int, hp: int) -> pygame.Surface:
        if not self._battery_states:
            return pygame.Surface((0, 0), pygame.SRCALPHA)

        if max_hp <= 0:
            return self._battery_states[0]

        hp_clamped = max(0, min(max_hp, hp))
        if hp_clamped <= 0:
            return self._battery_states[0]

        tiers = len(self._battery_states) - 1
        ratio = hp_clamped / max_hp
        frame_index = max(1, min(tiers, math.ceil(ratio * tiers)))
        return self._battery_states[frame_index]

    def _blit_life_batteries(self, surface: pygame.Surface, origin: tuple[int, int]) -> pygame.Rect:
        if not hasattr(self, "player"):
            return pygame.Rect(origin, (0, 0))

        max_lives = max(0, int(getattr(self.player, "max_lives", 0)))
        if max_lives <= 0:
            return pygame.Rect(origin, (0, 0))

        lives_remaining = max(0, int(getattr(self.player, "lives", 0)))
        max_hp = max(1, int(getattr(self.player, "max_hp", 1)))
        hits_remaining = max(0, min(max_hp, self._player_hits_remaining()))

        lost_lives = max(0, min(max_lives, max_lives - lives_remaining))
        icons: list[pygame.Surface] = []
        for index in range(max_lives):
            if index < lost_lives or lives_remaining <= 0:
                hp_value = 0
            elif index == lost_lives:
                hp_value = hits_remaining
            else:
                hp_value = max_hp

            icon = self._battery_surface(max_hp, hp_value).copy()
            if index == lost_lives and lives_remaining > 0:
                pygame.draw.rect(
                    icon,
                    self._life_battery_highlight,
                    icon.get_rect(),
                    3,
                    border_radius=6,
                )
            icons.append(icon)

        if not icons:
            return pygame.Rect(origin, (0, 0))

        icon_w, icon_h = icons[0].get_size()
        columns = 2
        max_rows = 5
        spacing_x = 6
        spacing_y = 6
        rows = min(max_rows, math.ceil(len(icons) / columns))

        ox, oy = origin
        max_icons = min(len(icons), columns * rows)
        for idx, icon_surface in enumerate(icons[:max_icons]):
            col = idx % columns
            row = idx // columns
            x = ox + col * (icon_w + spacing_x)
            y = oy + row * (icon_h + spacing_y)
            surface.blit(icon_surface, (x, y))

        used_columns = columns if max_icons >= columns else max_icons
        width = used_columns * icon_w + max(0, used_columns - 1) * spacing_x
        height = rows * icon_h + max(0, rows - 1) * spacing_y

        last_row_count = max_icons % columns or min(max_icons, columns)
        if max_icons >= columns:
            width_columns = columns
        else:
            width_columns = last_row_count
        width = width_columns * icon_w + max(0, width_columns - 1) * spacing_x
        height = rows * icon_h + max(0, rows - 1) * spacing_y

        return pygame.Rect(ox, oy, width, height) 
