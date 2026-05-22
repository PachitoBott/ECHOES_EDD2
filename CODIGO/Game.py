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
from core.TilesetManager import TilesetManager
from entities.Player import Player
from entities.Enemy import (
    IDLE as ENEMY_IDLE,
    FastChaserEnemy, ShooterEnemy, BasicEnemy, TankEnemy,
    FakerEnemy, TelefonoEnemy, EmojiEnemy
)
from world.Dungeon import Dungeon
from world.background import MatrixBackground
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

# --- Sistemas de efectos ---
from systems.death_effect import DeathEffectManager
from systems.power_effects import power_effect_manager
from systems.minigame_papers import MinijuegoPapers
# from systems.player_spawn_effect import SpawnEffectManager  # Ahora manejado internamente en Player


class RemoteProjectile:
    """Representación simple de un proyectil sincronizado del servidor."""

    def __init__(self, remote_id: int, x: float, y: float, dx: float = 0, dy: float = 0, owner_id: str | None = None):
        self._remote_id = remote_id
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.alive = True
        self.radius = 4
        self.color = (255, 230, 140)  # Color de bala de enemigo
        self.owner_id = owner_id  # [FIX] Para prevenir que un enemigo se dañe a sí mismo con sus propios proyectiles

    def rect(self):
        r = self.radius
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)

    def draw(self, surf: pygame.Surface):
        """Renderiza el proyectil."""
        if not self.alive:
            return
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)

    def update(self, dt: float, room):
        """Los proyectiles remotos son actualizados por sincronización, no localmente."""
        pass


class RemoteEnemy:
    """
    Representación de un enemigo remoto sincronizado del servidor.
    Solo renderiza — sin lógica de actualización local.

    Carga sprites y renderiza el enemigo remoto en pantalla.
    """

    def __init__(self, enemy_id: str, enemy_type: str, x: float, y: float):
        self.enemy_id = enemy_id
        self.tipo = enemy_type
        self.x = x
        self.y = y
        self.health = 1
        self.vivo = True
        self.w = 48
        self.h = 48
        self.animator_state = "idle"
        self.facing_right = True
        self.frame_index = 0
        self.frame_timer = 0.0
        self.frame_speed = 0.1  # Segundos por frame

        # Cargar sprites del enemigo
        self._cargar_sprites()

    def _cargar_sprites(self):
        """Carga los sprites del enemigo según su tipo."""
        try:
            from entities.enemy_sprites import load_enemy_animation_set
            self.animations = load_enemy_animation_set(self.tipo)
            log_game.debug(f"[REMOTE_ENEMY] {self.enemy_id} cargó sprites para tipo '{self.tipo}'")
        except Exception as e:
            log_game.warning(f"[REMOTE_ENEMY] Error cargando sprites para {self.tipo}: {e}")
            # Crear animaciones placeholder
            placeholder = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            pygame.draw.rect(placeholder, (255, 100, 100), (0, 0, self.w, self.h))
            pygame.draw.line(placeholder, (255, 255, 255), (0, 0), (self.w, self.h), 2)
            self.animations = {
                "idle": [placeholder],
                "run": [placeholder],
                "shoot": [placeholder],
                "attack": [placeholder],
                "death": [placeholder],
            }

    def actualizar_desde_red(self, data: dict):
        """Actualiza posición, estado y animación desde el servidor."""
        self.x = data.get("x", self.x)
        self.y = data.get("y", self.y)
        self.health = data.get("health", self.health)
        self.vivo = data.get("vivo", True)

        # Sincronizar estado de animación
        nuevo_state = data.get("animator_state", "idle")
        if nuevo_state != self.animator_state:
            self.animator_state = nuevo_state
            self.frame_index = 0
            self.frame_timer = 0.0

        # Sincronizar dirección
        self.facing_right = data.get("facing_right", True)

    def update(self, dt: float):
        """Actualiza la animación del enemigo remoto."""
        if not self.vivo:
            self.animator_state = "death"

        # Avanzar frame
        self.frame_timer += dt
        # EnemyAnimationSet.get() toma solo un argumento (el estado)
        state_frames = self.animations.get(self.animator_state)

        if state_frames and len(state_frames) > 0:
            if self.frame_timer >= self.frame_speed:
                self.frame_timer = 0.0
                self.frame_index = (self.frame_index + 1) % len(state_frames)

    def draw(self, surf: pygame.Surface):
        """Renderiza el enemigo remoto en pantalla."""
        if not self.vivo:
            return

        try:
            # Obtener frame actual
            # EnemyAnimationSet.get() toma solo un argumento
            state_frames = self.animations.get(self.animator_state)
            if not state_frames or len(state_frames) == 0:
                state_frames = self.animations.get("idle")

            if not state_frames:
                log_game.warning(f"[REMOTE_ENEMY] {self.enemy_id} sin frames para estado '{self.animator_state}'")
                return

            # Obtener frame actual de forma segura
            idx = min(self.frame_index, len(state_frames) - 1)
            frame = state_frames[idx]

            if frame is None or frame.get_size() == (0, 0):
                log_game.warning(f"[REMOTE_ENEMY] {self.enemy_id} frame inválido para estado '{self.animator_state}'")
                return

            # Voltear si es necesario
            if not self.facing_right:
                frame = pygame.transform.flip(frame, True, False)

            # Renderizar
            rect = frame.get_rect(topleft=(int(self.x), int(self.y)))
            surf.blit(frame, rect)

        except Exception as e:
            log_game.error(f"[REMOTE_ENEMY] Error renderizando {self.enemy_id}: {e}")

    def rect(self):
        """Retorna un rect para colisiones o renderizado."""
        return pygame.Rect(self.x, self.y, self.w, self.h)

    def _center(self):
        """Centro del enemigo."""
        return (self.x + self.w / 2, self.y + self.h / 2)


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
        pygame.mouse.set_visible(True)  # Mostrar cursor normal del sistema

        # ---------- UI ----------
        self.ui_font = pygame.font.SysFont(None, 18)
        icon_source, pickup_sprite = self._create_coin_sprites()
        self._coin_icon_source = icon_source
        self._coin_pickup_sprite = pickup_sprite
        self.coin_icon_scale = self.COIN_ICON_DEFAULT_SCALE * 0.8
        
        # Usa los métodos set_coin_icon_scale/offset/value_offset para ajustar
        # manualmente la presentación del icono dentro del HUD.
        self._coin_icon = self._scale_coin_icon(self.coin_icon_scale)
        # NOTA: Sistema de baterías removido - reemplazado con sistema de corazones en HUDPanel
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

        # --- Paneles de jugadores (P1 bottom-left, P2 bottom-right) ---
        from ui.HudPanels import HUDPanel
        # P1: bottom-left (497x221)
        self.hud_panel_p1 = HUDPanel(
            player_id=1,
            anchor="top_left",
            panel_image_path="assets/ui/panel_jugador1.png",
            screen_width=cfg.SCREEN_W,
            screen_height=cfg.SCREEN_H,
            custom_y=895,  # Same as P2 (bottom)
            custom_width=497,
            custom_height=221
        )
        # P2: bottom-right (450x200) - positioned very far right
        # custom_x = 1194 + 200 = 1394
        self.hud_panel_p2 = HUDPanel(
            player_id=2,
            anchor="top_left",
            panel_image_path="assets/ui/panel_jugador2.png",
            screen_width=cfg.SCREEN_W,
            screen_height=cfg.SCREEN_H,
            custom_x=1394,  # 900px total further right
            custom_y=895   # Same height as P1
        )

        # ---------- Recursos ----------
        self.tileset_manager = TilesetManager()
        self.tileset_manager.set_zone(1)  # Inicializar con Zona 1
        self.minimap = Minimap(cell=16, padding=8)

        # ---------- Efectos visuales ----------
        self.death_effect_manager = DeathEffectManager()
        # Asignar el gestor de efectos de muerte a la clase Enemy para que todos los enemigos lo usen
        from entities.Enemy import Enemy
        Enemy._death_effect_manager_global = self.death_effect_manager

        # Gestor de efectos de spawn del jugador (ahora manejado internamente en Player)
        # self.spawn_effect_manager = SpawnEffectManager()

        # ---------- Fondo matrix ----------
        self.matrix_bg = MatrixBackground(cfg.SCREEN_W, cfg.SCREEN_H)

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

        # Estado del juego compartido con el sistema de diálogos
        self._estado_juego: dict = {}

        # Sistema de notificaciones en pantalla
        self.subtitulos = SubtitleSystem(cfg.SCREEN_W, cfg.SCREEN_H, font_size=20)

        # Control de estado narrativo
        self._current_zone: int = 1
        self._intro_played: bool = False
        self._zones_cinematics_shown: set = set()  # zonas cuya cinemática ya se mostró esta run

        # Banner de zona (estilo Binding of Isaac)
        self._zone_banner_text: str = ""
        self._zone_banner_sub: str = ""
        self._zone_banner_timer: float = 0.0
        self._ZONE_BANNER_DURATION: float = 2.8   # segundos totales
        self._ZONE_BANNER_FADE: float = 0.4        # segundos de fade in/out
        self._boss_banner_shown: bool = False      # banner de boss: solo una vez por run

        # Minijuego Papers (antes del boss)
        self.minijuego_papers: MinijuegoPapers | None = None
        self.ultima_sala_fue_boss: bool = False

        # ---------- Networking (Fase 3) ----------
        self.net: NetworkManager | None = None
        self.remote_players: dict = {}  # Almacena estado de jugadores remotos
        self.remote_enemies: dict = {}  # Almacena enemigos remotos sincronizados del servidor
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

        # Debug: saltar directamente a la boss room al iniciar
        if self.cfg.DEBUG_START_IN_BOSS_ROOM and hasattr(self.dungeon, "boss_pos"):
            self.dungeon.i, self.dungeon.j = self.dungeon.boss_pos

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
        setattr(self.player, "gold", 999)

        # Set up shooting callback for network synchronization
        if self.net:
            self.player.on_shoot = self._on_player_shoot

        # Reset de runtime (proyectiles, contadores, etc)
        self._reset_runtime_state()

        # Reset de poderes comprados en la tienda del Profesor Ibarra
        self._reset_player_powers(self.player)

        # Reset de zona y tileset a inicio (zona 1)
        self._reset_zone_and_tileset()

        # Reset del progreso del Profesor Ibarra (preguntas/respuestas)
        from ui.ProfesorIbarra import progreso_ibarra
        progreso_ibarra.reset()

        # Entrar "formalmente" a la sala inicial (dispara on_enter/Shop si aplica)
        if hasattr(self.dungeon, "enter_initial_room"):
            self.dungeon.enter_initial_room(self.player, self.cfg, ShopkeeperCls=Shopkeeper)

        self._run_start_time = perf_counter()

        # Trigger narrativa: marcar para reproducir intro en el primer frame
        self._intro_played = False
        self._current_zone = 1
        self._zones_cinematics_shown = set()
        self._zone_banner_text = ""
        self._zone_banner_sub = ""
        self._zone_banner_timer = 0.0
        self._boss_banner_shown = False

    def _reset_runtime_state(self) -> None:
        self.projectiles.clear()
        self.enemy_projectiles.clear()
        self.door_cooldown = 0.0
        self.locked = False
        self.cleared = False
        self._run_gold_spent = 0
        self._run_kills = 0

    def _reset_player_powers(self, player) -> None:
        """
        Resetea todos los poderes comprados del jugador.
        Se llama al reiniciar el run para limpiar los items de Ibarra.
        """
        # Resetear todos los atributos de poderes de Ibarra
        atributos_poderes = [
            '_ibarra_red_apoyo',      # Contador de curaciones
            '_ibarra_modo_privado',   # Invulnerabilidad temporal
            '_ibarra_emp',            # Congelamiento de enemigos
            '_ibarra_double_shot',    # Disparo doble
        ]

        for attr in atributos_poderes:
            if hasattr(player, attr):
                # Resetear a 0 o False según el tipo
                if attr == '_ibarra_red_apoyo':
                    setattr(player, attr, 0)  # Contador
                else:
                    setattr(player, attr, False)  # Booleanos

        # Resetear efectos activos de poderes
        if hasattr(player, 'invulnerable_timer'):
            player.invulnerable_timer = 0.0
        if hasattr(player, 'stun_timer'):
            player.stun_timer = 0.0

        log_game.info("✅ Poderes del jugador reseteados")

    def _reset_zone_and_tileset(self) -> None:
        """
        Resetea la zona a 1 y fuerza el tileset y paleta de colores a zona 1.
        Necesario para que al reiniciar desde zona 2+ no quede el color/tileset anterior.
        """
        # Resetear variable de zona actual
        self._current_zone = 1
        self._zones_cinematics_shown = set()

        # Forzar el fondo matrix a zona 1
        if self.matrix_bg:
            self.matrix_bg.set_zona(1)
            log_game.debug("✅ Fondo matrix reseteado a zona 1")

        # Resetear tileset a zona 1
        if hasattr(self, 'tileset_manager') and self.tileset_manager:
            self.tileset_manager.set_zone(1)
            log_game.debug("✅ Tileset reseteado a zona 1")

        # Limpiar efectos de poderes
        power_effect_manager.limpiar()

        log_game.info("✅ Zona y tileset reseteados a inicio")

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
                elif e.key == pygame.K_z:
                    self._use_ibarra_item("red_apoyo")
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

        if ev.tipo == "aceptado":
            # Cliente: recibió confirmación de conexión con seed del servidor
            seed = ev.datos.get("seed")
            if seed is not None and self.current_seed is None:
                # Usar la seed del servidor
                log_net.info(f"✅ Usando seed del servidor: {seed}")
                self.start_new_run(seed=seed)

        elif ev.tipo == "jugador_unido":
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
                # [DEBUG] Log para ver qué sala tiene el jugador remoto
                sala_remota = ev.datos.get("sala", [0, 0])
                log_game.debug(f"[ESTADO_REMOTO] {origen} está en sala {sala_remota}, pos=({ev.datos.get('pos_x')}, {ev.datos.get('pos_y')})")

        elif ev.tipo == "enemigo_muerto":
            # Enemigo fue eliminado por otro jugador
            self._handle_remote_enemy_death(ev)

        elif ev.tipo == "proyectil_disparado":
            # Otro jugador disparó un proyectil
            self._handle_remote_projectile(ev)

        elif ev.tipo == "enemigo_danado":
            # Enemigo recibió daño de otro jugador
            self._handle_remote_damage(ev)

        elif ev.tipo == "enemies_state":
            # Sincronización de estado de todos los enemigos desde el servidor
            self._handle_enemies_state(ev)

        elif ev.tipo == "enemy_projectiles_state":
            # Sincronización de balas de enemigos desde el servidor
            self._handle_enemy_projectiles_state(ev)

        elif ev.tipo == "bullet_fired_by_client":
            # Servidor procesa disparo del cliente
            if self.net and self.net.es_servidor:
                self._process_client_bullet(ev)

        elif ev.tipo == "room_clear":
            # Sala se completó (todos los enemigos muertos)
            room_id_raw = ev.datos.get("room_id")
            room_id = tuple(room_id_raw) if isinstance(room_id_raw, (list, tuple)) else (0, 0)
            if room_id == (self.dungeon.i, self.dungeon.j):
                room = self.dungeon.current_room
                if hasattr(room, "refresh_lock_state"):
                    room.refresh_lock_state()

        elif ev.tipo == "apoyo_recibido":
            # Aliado envió un apoyo (curación, monedas, escudo, etc.)
            tipo_apoyo = ev.datos.get("apoyo")
            valor = ev.datos.get("valor")
            log_net.info(f"🔵 Apoyo recibido: {tipo_apoyo} ({valor})")

        elif ev.tipo == "error_red":
            descripcion = ev.datos.get("descripcion", "error desconocido")
            log_game.warning(f"⚠️ Error de red: {descripcion}")

        elif ev.tipo == "accion_recibida":
            # Acción enviada por el cliente (ej: solicitud de transición)
            if self.net and self.net.es_servidor:
                self._procesar_accion(ev)

        elif ev.tipo == "transicion_completada":
            # Notificación del servidor de que la transición se completó
            if self.net and not self.net.es_servidor:
                self._handle_transicion_completada(ev)

        else:
            log_net.debug(f"Evento de red no manejado: {ev.tipo}")

    def _procesar_accion(self, ev: EventoRed) -> None:
        """
        Procesa acciones enviadas por el cliente al servidor.

        Ejemplos: solicitud de transición de sala, etc.
        """
        accion = ev.datos.get("accion")
        origen = ev.origen

        if accion == "transicion":
            # Cliente solicita transición en dirección
            direccion = ev.datos.get("direccion")
            if direccion:
                log_game.info(f"[TRANSICION] Servidor procesando transición de {origen} en dirección {direccion}")
                room = self.dungeon.current_room
                if not getattr(room, "locked", False):
                    self._procesar_transicion(direccion, room)

    def _handle_transicion_completada(self, ev: EventoRed) -> None:
        """
        Recibe notificación de transición completada desde el servidor (cliente solo).

        El servidor notifica que la transición se ejecutó y ambos jugadores están
        en la nueva sala.
        """
        sala_nueva_raw = ev.datos.get("sala_nueva", [0, 0])
        pos_aliado_raw = ev.datos.get("pos_aliado", [0, 0])

        sala_nueva = tuple(sala_nueva_raw) if isinstance(sala_nueva_raw, (list, tuple)) else (0, 0)
        pos_aliado = tuple(pos_aliado_raw) if isinstance(pos_aliado_raw, (list, tuple)) else (0.0, 0.0)

        log_game.info(f"[TRANSICION] Cliente recibió transición completada a sala {sala_nueva}, pos={pos_aliado}")

        # Mover a la nueva sala
        self.dungeon.i, self.dungeon.j = sala_nueva

        # Posicionar al jugador local (ALIADO)
        self.player.x, self.player.y = pos_aliado

        # Limpiar y actualizar
        self.projectiles.clear()
        self.enemy_projectiles.clear()
        self.remote_enemies.clear()  # Limpiar enemigos remotos de la sala anterior
        self.door_cooldown = 0.25

        room = self.dungeon.current_room
        depth = self.dungeon.depth_map.get((self.dungeon.i, self.dungeon.j), -1)
        log_room.room_enter((self.dungeon.i, self.dungeon.j), depth)
        # [FIX SYNC] Cliente NO crea enemigos — los recibe del servidor
        if self.net is None or self.net.es_servidor:
            self._spawn_room_enemies(room)
        self._update_room_lock(room)

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
            room = self.dungeon.rooms[sala_remota]
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

            # [DIAGNÓSTICO] Registrar búsqueda
            log_game.info(f"[DEATH] Buscando {enemy_type} en ({pos_x:.1f}, {pos_y:.1f}) — {len(room.enemies)} enemigos en sala")

            found = False
            for i, enemy in enumerate(room.enemies):
                dist = ((enemy.x - pos_x) ** 2 + (enemy.y - pos_y) ** 2) ** 0.5
                is_type_match = enemy.__class__.__name__ == enemy_type
                is_pos_match = dist <= tolerance

                log_game.debug(f"[DEATH]   Enemigo {i}: {enemy.__class__.__name__} en ({enemy.x:.1f}, {enemy.y:.1f}) dist={dist:.1f} type_ok={is_type_match} pos_ok={is_pos_match}")

                if is_pos_match and is_type_match:
                    # Encontrado enemigo que coincide — removerlo
                    log_game.info(f"[DEATH] ✓ Removiendo {enemy_type} en posición ({pos_x:.1f}, {pos_y:.1f})")
                    room.enemies.pop(i)
                    found = True
                    break

            if not found:
                log_game.warning(
                    f"[DEATH] ✗ No encontré {enemy_type} en ({pos_x:.1f}, {pos_y:.1f}) sala {sala_remota} — {len(room.enemies)} enemigos"
                )
        except Exception as e:
            log_game.error(f"ERROR buscando/removiendo enemigo: {e}", exc_info=True)

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
            room = self.dungeon.rooms[sala_remota]
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

    def _create_enemy_from_server_type(self, enemy_type: str, x: float, y: float, enemy_id: str | None = None):
        """
        [FIX SYNC] Crea un Enemy real basado en el tipo enviado por el servidor.
        Se usa cuando el cliente recibe un enemigo nuevo del servidor.
        """
        enemies_map = {
            "FastChaserEnemy": FastChaserEnemy,
            "ShooterEnemy": ShooterEnemy,
            "BasicEnemy": BasicEnemy,
            "TankEnemy": TankEnemy,
            "FakerEnemy": FakerEnemy,
            "TelefonoEnemy": TelefonoEnemy,
            "EmojiEnemy": EmojiEnemy,
        }

        try:
            enemy_class = enemies_map.get(enemy_type)
            if not enemy_class:
                log_game.warning(f"[SYNC] Tipo desconocido de enemigo: {enemy_type}")
                return None

            enemy = enemy_class(x, y)

            # [FIX SYNC] Si el servidor proporcionó un ID, reemplazar el ID generado localmente
            if enemy_id:
                enemy.enemy_id = enemy_id
                log_game.debug(f"[SYNC] Creado {enemy_type} con ID servidor {enemy_id}")
            else:
                log_game.debug(f"[SYNC] Creado {enemy_type} con ID local {enemy.enemy_id}")

            return enemy
        except Exception as e:
            log_game.error(f"[SYNC] Error creando enemigo {enemy_type}: {e}")
            return None

    def _handle_enemies_state(self, ev: EventoRed) -> None:
        """
        Sincroniza el estado de todos los enemigos desde el servidor.
        [FIX SYNC] Reconcilia la lista completa basándose en datos del servidor.

        El servidor es la única fuente de verdad. El cliente:
        1. Elimina enemigos que NO envía el servidor
        2. Crea enemigos que envía el servidor pero el cliente no tiene
        3. Actualiza enemigos existentes
        """
        datos = ev.datos
        enemies_list = datos.get("enemies", [])
        room_id_raw = datos.get("room_id")
        room_id = tuple(room_id_raw) if isinstance(room_id_raw, (list, tuple)) else (0, 0)

        # Solo actualizar si estamos en la misma sala
        if room_id != (self.dungeon.i, self.dungeon.j):
            return

        room = self.dungeon.current_room
        if not hasattr(room, "enemies"):
            return

        # PASO 1: Crear mapa de IDs de enemigos del servidor
        server_enemies_by_id = {e.get("id"): e for e in enemies_list}

        # PASO 2: Recolectar TODOS los IDs a eliminar (fantasmas + muertos)
        ids_a_eliminar = []
        ids_muertos = set()  # [FIX SYNC] Rastrear enemigos que el servidor envía como muertos

        log_game.debug(f"[ENEMIES_STATE] PASO 2: Verificando {len(room.enemies)} enemigos locales vs {len(server_enemies_by_id)} del servidor")

        for i, enemy in enumerate(room.enemies):
            enemy_id = getattr(enemy, "enemy_id", None)
            if not enemy_id:
                continue

            # ¿El enemigo está en la lista del servidor?
            if enemy_id not in server_enemies_by_id:
                # [FANTASMA] No está en servidor → eliminar
                ids_a_eliminar.append(i)
                log_game.info(f"[ENEMIES_STATE] FANTASMA: {enemy_id} no está en servidor")
            else:
                # [FIX SYNC] ¿El servidor dice que está muerto?
                server_vivo = server_enemies_by_id[enemy_id].get("vivo", True)
                if not server_vivo:
                    # [MUERTO] Servidor envía vivo=False → eliminar INMEDIATAMENTE
                    ids_a_eliminar.append(i)
                    ids_muertos.add(enemy_id)
                    log_game.warning(f"[ENEMIES_STATE] MUERTO (vivo=False): {enemy_id} será eliminado")

        # Eliminar en orden inverso para mantener índices
        log_game.debug(f"[ENEMIES_STATE] Eliminando {len(ids_a_eliminar)} enemigos (fantasmas={len(ids_a_eliminar)-len(ids_muertos)}, muertos={len(ids_muertos)})")
        for i in sorted(ids_a_eliminar, reverse=True):
            removed_id = getattr(room.enemies[i], "enemy_id", "unknown")
            log_game.debug(f"[ENEMIES_STATE] Eliminando índice {i}: {removed_id}")
            room.enemies.pop(i)

        # PASO 3: Actualizar/crear enemigos del servidor
        client_enemy_ids_por_id = {
            getattr(e, "enemy_id", None): e
            for e in room.enemies
            if getattr(e, "enemy_id", None)
        }

        # [DIAG] Verificar qué recibe del servidor
        muertos_recibidos = sum(1 for e in enemies_list if not e.get("vivo", True))
        log_game.info(f"[ENEMIES_STATE] Cliente recibió: {len(enemies_list)} enemigos, {muertos_recibidos} muertos, sala {room_id}")
        if muertos_recibidos > 0:
            for e in enemies_list:
                if not e.get("vivo", True):
                    log_game.warning(f"[ENEMIES_STATE] → Enemigo MUERTO en servidor: {e.get('id')} en ({e.get('x', 0):.1f}, {e.get('y', 0):.1f})")

        for server_id, server_data in server_enemies_by_id.items():
            # [FIX SYNC] Saltar enemigos que ya fueron eliminados por estar muertos
            if server_id in ids_muertos:
                continue

            if server_id in client_enemy_ids_por_id:
                # Actualizar enemigo existente
                enemy = client_enemy_ids_por_id[server_id]
                server_vivo = server_data.get("vivo", True)

                # [FIX SYNC] Este bloque ahora NO debería ejecutarse porque los muertos
                # ya fueron eliminados en PASO 2, pero lo mantenemos como respaldo defensivo
                if not server_vivo:
                    # Enemigo marcado como muerto por servidor
                    if not getattr(enemy, "_is_dying", False):
                        enemy._is_dying = True
                        enemy._ready_to_remove = True
                        log_game.warning(f"[SYNC] RESPALDO: {server_id} marcado como muerto (ya debería estar eliminado)")
                else:
                    # Limpiar banderas de muerte si el servidor dice que está vivo
                    if getattr(enemy, "_is_dying", False):
                        log_game.debug(f"[SYNC] {server_id} resincronizado vivo desde servidor")
                        enemy._is_dying = False
                        enemy._ready_to_remove = False
                        if enemy.hp <= 0:
                            enemy.hp = max(1, server_data.get("health", 1))

                # Sincronizar posición, salud
                enemy.x = server_data.get("x", enemy.x)
                enemy.y = server_data.get("y", enemy.y)
                enemy.hp = server_data.get("health", enemy.hp)

                # Sincronizar animación
                animator_state = server_data.get("animator_state", "idle")
                if not server_vivo:
                    animator_state = "death"

                if hasattr(enemy, "animator"):
                    if animator_state == "shoot":
                        if hasattr(enemy.animator, "trigger_shoot"):
                            enemy.animator.trigger_shoot()
                    elif animator_state == "attack":
                        if hasattr(enemy.animator, "trigger_attack"):
                            enemy.animator.trigger_attack()
                    else:
                        if hasattr(enemy.animator, "set_base_state"):
                            enemy.animator.set_base_state(animator_state)

                # Sincronizar dirección
                enemy._facing_right = server_data.get("facing_right", True)

            else:
                # Crear nuevo enemigo basado en datos del servidor
                enemy_type = server_data.get("tipo", "BasicEnemy")
                enemy = self._create_enemy_from_server_type(
                    enemy_type,
                    server_data.get("x", 0),
                    server_data.get("y", 0),
                    server_id
                )

                if enemy:
                    # Actualizar estado inicial del enemigo
                    enemy.hp = server_data.get("health", enemy.hp)
                    enemy._facing_right = server_data.get("facing_right", True)

                    # Si está muerto, marcar inmediatamente
                    if not server_data.get("vivo", True):
                        enemy._is_dying = True
                        enemy._ready_to_remove = True

                    room.enemies.append(enemy)
                    log_game.info(f"[SYNC] Creado nuevo enemigo {server_id} ({enemy_type})")
                else:
                    log_game.error(f"[SYNC] No se pudo crear enemigo {server_id}")

        # [DIAGNOSTICO]
        client_ids = [getattr(e, "enemy_id", "?") for e in room.enemies]
        server_ids = list(server_enemies_by_id.keys())
        log_game.debug(
            f"[SYNC] Reconciliación completada: cliente={len(client_ids)} enemigos, "
            f"servidor={len(server_ids)}, muertos_eliminados={len(ids_muertos)}"
        )

    def _handle_enemy_projectiles_state(self, ev: EventoRed) -> None:
        """
        Sincroniza balas de enemigos desde el servidor.
        En el cliente: crea/actualiza proyectiles remotos para renderizar.
        """
        try:
            datos = ev.datos
            projectiles_list = datos.get("projectiles", [])
            room_id_raw = datos.get("room_id")
            room_id = tuple(room_id_raw) if isinstance(room_id_raw, (list, tuple)) else (0, 0)

            # Solo actualizar si estamos en la misma sala
            if room_id != (self.dungeon.i, self.dungeon.j):
                return

            # Crear mapa de IDs de proyectiles del servidor
            server_proj_by_id = {p.get("id"): p for p in projectiles_list}

            # Crear o actualizar proyectiles remotos
            for proj_id, proj_data in server_proj_by_id.items():
                # Buscar si ya existe
                found = False
                for proj in self.remote_projectiles:
                    if hasattr(proj, "_remote_id") and proj._remote_id == proj_id:
                        # Actualizar posición
                        proj.x = proj_data.get("x", proj.x)
                        proj.y = proj_data.get("y", proj.y)
                        proj.dx = proj_data.get("dx", proj.dx)
                        proj.dy = proj_data.get("dy", proj.dy)
                        proj.alive = proj_data.get("vivo", True)
                        found = True
                        break

                if not found:
                    # Crear nuevo proyectil remoto
                    remote_proj = RemoteProjectile(
                        proj_id,
                        proj_data.get("x", 0),
                        proj_data.get("y", 0),
                        proj_data.get("dx", 0),
                        proj_data.get("dy", 0),
                        owner_id=proj_data.get("owner_id"),  # [FIX] Pasar el owner_id para proteger enemigos
                    )
                    self.remote_projectiles.append(remote_proj)

            # Limpiar proyectiles que ya no existen en el servidor
            self.remote_projectiles = [
                p for p in self.remote_projectiles
                if not hasattr(p, "_remote_id") or p._remote_id in server_proj_by_id
            ]

        except Exception as e:
            log_net.error(f"Error en _handle_enemy_projectiles_state: {e}", exc_info=True)

    def _process_client_bullet(self, ev: EventoRed) -> None:
        """
        El servidor procesa un disparo enviado por el cliente.
        Detecta si impacta un enemigo y envía el evento correspondiente.
        """
        if not self.net or not self.net.es_servidor:
            return

        datos = ev.datos
        x = datos.get("x", 0)
        y = datos.get("y", 0)
        dir_x = datos.get("dir_x", 0)
        dir_y = datos.get("dir_y", 1)
        damage = datos.get("damage", 1)

        room = self.dungeon.current_room
        if not hasattr(room, "enemies"):
            return

        # Buscar colisión simple en posición inicial
        # (En una versión más sofisticada, simularíamos la trayectoria)
        bullet_rect = pygame.Rect(x, y, 2, 2)
        for enemy in room.enemies:
            enemy_rect = enemy.rect()
            if bullet_rect.colliderect(enemy_rect):
                # Enemigo golpeado - aplicar daño
                if hasattr(enemy, "take_damage"):
                    enemy.take_damage(damage, (dir_x, dir_y))
                else:
                    enemy.hp -= damage

                # Si el enemigo muere, enviar evento
                if enemy.hp <= 0:
                    from network.protocol import msg_enemigo_muerto
                    evento_muerte = msg_enemigo_muerto(
                        enemy.x, enemy.y,
                        enemy.__class__.__name__,
                        (self.dungeon.i, self.dungeon.j)
                    )
                    log_game.info(f"[DEATH_BULLET] Enviando muerte desde _process_client_bullet: {enemy.enemy_id} en ({enemy.x:.1f}, {enemy.y:.1f}) _is_dying={getattr(enemy, '_is_dying', False)}")
                    self.net.enviar(evento_muerte)
                break

    def _on_player_shoot(self, pos: tuple[float, float], direction: tuple[float, float]) -> None:
        """Callback when player fires - send network event."""
        if not self.net:
            return

        from network.protocol import msg_proyectil_disparado, msg_bullet_fired_by_client

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

        # Si es cliente: también enviar evento para que el servidor procese colisiones
        if not self.net.es_servidor:
            damage = getattr(self.player.weapon, "damage", 1) if self.player.weapon else 1
            evento_colisiones = msg_bullet_fired_by_client(
                player_id=2,  # Cliente es siempre el jugador 2 (ALIADO)
                x=pos[0],
                y=pos[1],
                dir_x=direction[0],
                dir_y=direction[1],
                damage=damage,
            )
            self.net.enviar(evento_colisiones)

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
        # Guardar dt para acceso en métodos de sincronización
        self.dt = dt

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

        # --- Actualizar animaciones de paneles HUD ---
        self.hud_panel_p1.update(dt)
        self.hud_panel_p2.update(dt)

        # --- Actualizar fondo matrix ---
        self.matrix_bg.update(dt)

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

        # --- Minijuego Papers: bloquear gameplay antes del boss ---
        # Detectar entrada a sala del boss y activar minijuego
        if getattr(room, "type", "") == "boss" and not self.ultima_sala_fue_boss:
            # Primera vez que entra a la sala del boss
            if self.minijuego_papers is None:
                self.minijuego_papers = MinijuegoPapers(self.cfg.SCREEN_W, self.cfg.SCREEN_H)

            self.minijuego_papers.update(dt)

            # Procesar eventos del minijuego
            for event in events:
                self.minijuego_papers.handle_event(event)

            # Verificar si completó el minijuego
            if self.minijuego_papers.terminado:
                if self.minijuego_papers.aprobado:
                    # Aprobó - desactivar minijuego y continuar en la sala del boss
                    self.minijuego_papers = None
                    self.ultima_sala_fue_boss = True
                else:
                    # Falló - reiniciar el minijuego
                    self.minijuego_papers = MinijuegoPapers(self.cfg.SCREEN_W, self.cfg.SCREEN_H)

            return  # Bloquear actualización de gameplay mientras juega

        # Marcar que salimos de sala del boss (para que vuelva a mostrar minijuego si reentras)
        if getattr(room, "type", "") != "boss":
            self.ultima_sala_fue_boss = False

        # --- Trigger transiciones de zona (PRIMERO, antes de spawnar enemigos) ---
        self._check_zone_transitions()

        self._update_player(dt, room)
        # [FIX SYNC] Cliente NO crea enemigos — los recibe del servidor
        # Solo el servidor debe llamar a _spawn_room_enemies
        if self.net is None or self.net.es_servidor:
            self._spawn_room_enemies(room)
        self._update_enemies(dt, room)

        # En modo servidor: actualizar también enemigos en salas con jugadores remotos
        if self.net and self.net.es_servidor:
            self._update_remote_player_rooms(dt)

        # Actualizar enemigos remotos (animaciones y sincronización)
        self._update_remote_enemies(dt)

        self._sync_enemies_to_client(room)  # Sincronizar enemigos con cliente remoto
        self._sync_enemy_projectiles_to_client(room)  # Sincronizar balas de enemigos
        self._update_projectiles(dt, room)
        self.death_effect_manager.update(dt)
        power_effect_manager.update(dt)  # Actualizar efectos de poderes (EMP, invulnerabilidad, cura)
        room.update_obstacles(dt)  # Actualizar animaciones de obstáculos
        player_died = self._handle_collisions(room)
        if player_died:
            return
        self._update_pickups(dt, room)
        self._handle_room_transition(room)
        self._update_shop(events)

        # --- Trigger entrada a sala del boss (banner temporal) ---
        self._check_boss_room_entry(room)

        # --- Tick del banner de zona ---
        if self._zone_banner_timer > 0:
            self._zone_banner_timer -= dt


    def _update_player(self, dt: float, room) -> None:
        # Modo dios: mantener el timer de invulnerabilidad alto
        if getattr(self.player, "_debug_god_mode", False):
            self.player.invulnerable_timer = 9999.0

        self.player.update(dt, room, self.projectiles)

    def _spawn_room_enemies(self, room) -> None:
        if getattr(room, "no_spawn", False):
            return

        # Salas especiales sin enemigos
        if getattr(room, "type", "normal") in ("profesor_ibarra",):
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
            room.ensure_spawn(difficulty=difficulty, zone=self._current_zone, dungeon=self.dungeon)

    def _get_closest_player_for_enemy(self, enemy, room_pos=None) -> object:
        """
        Retorna el jugador (local o remoto) más cercano al enemigo.

        Esto permite que los enemigos ataquen al jugador más cercano
        en modo multijugador cooperativo.

        Args:
            enemy: El enemigo a considerar
            room_pos: Tupla (i, j) de la sala donde está el enemigo (opcional)
                     Si no se proporciona, usa la sala actual del servidor
        """
        import math

        # Si no se proporciona room_pos, usar la sala actual del servidor
        if room_pos is None:
            room_pos = (self.dungeon.i, self.dungeon.j)

        # Validar que self.player existe
        if not hasattr(self, "player") or self.player is None:
            log_game.warning("Player no inicializado en _get_closest_player_for_enemy")
            return None

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

                # Solo considerar si está en la misma sala que el ENEMIGO (no del servidor)
                if sala_remota == room_pos:
                    # El formato correcto es "pos": [x, y], pero también soportar "pos_x"/"pos_y"
                    pos_array = datos.get("pos", None)
                    if pos_array and isinstance(pos_array, (list, tuple)) and len(pos_array) >= 2:
                        remote_x = float(pos_array[0])
                        remote_y = float(pos_array[1])
                    else:
                        # Fallback al formato antiguo
                        remote_x = float(datos.get("pos_x", 0))
                        remote_y = float(datos.get("pos_y", 0))

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

            # [DEBUG] Log de targeting
            log_game.debug(f"[TARGETING] {enemy.enemy_id} local_dist={local_dist:.1f} remote_dist={remote_dist:.1f} REMOTE ({remote_pos[0]:.0f},{remote_pos[1]:.0f}) en sala {room_pos}")
            return RemotePlayer(remote_pos[0], remote_pos[1])
        else:
            # [DEBUG] Log de targeting
            if hasattr(self, 'remote_players') and self.remote_players:
                log_game.debug(f"[TARGETING] {enemy.enemy_id} local_dist={local_dist:.1f} remote_players={len(self.remote_players)} pero no en sala {room_pos}")
            return self.player

    def _update_enemies(self, dt: float, room) -> None:
        if not hasattr(room, "enemies"):
            return

        # En modo cliente: las posiciones vienen de la red, pero actualizar FSM y animaciones
        if self.net and not self.net.es_servidor:
            # Actualizar lógica de estado SIN mover (la posición viene de la red)
            for enemy in room.enemies:
                try:
                    # Actualizar timers básicos
                    if hasattr(enemy, "hit_flash_timer"):
                        enemy.hit_flash_timer = max(0.0, enemy.hit_flash_timer - dt)
                    if hasattr(enemy, "alert_timer"):
                        enemy.alert_timer = max(0.0, enemy.alert_timer - dt)
                    if hasattr(enemy, "_los_timer"):
                        enemy._los_timer = max(0.0, enemy._los_timer - dt)
                    if hasattr(enemy, "_movement_lock_timer"):
                        enemy._movement_lock_timer = max(0.0, enemy._movement_lock_timer - dt)
                    if hasattr(enemy, "stun_timer"):
                        enemy.stun_timer = max(0.0, enemy.stun_timer - dt)

                    # IMPORTANTE: Actualizar FSM (cambios de estado IDLE/WANDER/CHASE)
                    # Esto permite que los enemigos persigan al jugador sin moverse
                    if hasattr(enemy, "state") and hasattr(enemy, "_center"):
                        if not self.player:
                            log_game.debug(f"[CLIENTE] WARNING: self.player es None o no existe")
                        else:
                            ex, ey = enemy._center()
                            px, py = self.player.x + self.player.w/2, self.player.y + self.player.h/2
                            dx, dy = (px - ex), (py - ey)
                            dist = math.hypot(dx, dy)
                            has_los = room.has_line_of_sight(ex, ey, px, py)

                            # Debug: ver si detect_radius existe
                            detect_rad = getattr(enemy, "detect_radius", 150)
                            lose_rad = getattr(enemy, "lose_radius", 200)

                            # Cambios de estado IDLE ↔ WANDER ↔ CHASE (copiar lógica del update original)
                            from entities.Enemy import IDLE, WANDER, CHASE

                            if enemy.state != CHASE:
                                if dist <= detect_rad and has_los:
                                    log_game.debug(f"[CLIENTE] Enemy {enemy.enemy_id} detectó jugador: dist={dist:.1f}, detect_rad={detect_rad}, los={has_los}")
                                    enemy.state = CHASE
                                    enemy._los_timer = getattr(enemy, "_los_grace", 0.35)
                            else:
                                if has_los:
                                    enemy._los_timer = getattr(enemy, "_los_grace", 0.35)
                                else:
                                    enemy._los_timer = max(0.0, enemy._los_timer - dt)
                                if dist >= lose_rad or enemy._los_timer <= 0.0:
                                    if hasattr(enemy, "_pick_wander"):
                                        enemy._pick_wander()
                                    enemy.state = WANDER

                    # IMPORTANTE: Actualizar la animación para que los frames avancen
                    # El animator protege los estados oneshot (shoot, attack) automáticamente
                    # en set_base_state(), así que no interfiere con la sincronización del servidor
                    if hasattr(enemy, "_update_animation"):
                        enemy._update_animation(dt)

                except Exception as e:
                    log_game.error(f"Error actualizando enemy en cliente: {e}", exc_info=True)
                    continue
            # No llamar a enemy.update() porque eso modifica posición
            return

        # En modo servidor o modo offline: simular enemigos normalmente
        for enemy in room.enemies:
            # Obtener el jugador más cercano (local o remoto)
            closest_player = self._get_closest_player_for_enemy(enemy)
            enemy.update(dt, closest_player, room)
            # [DEBUG] Log de actualización
            if closest_player:
                dist_to_player = math.hypot(closest_player.x - enemy.x, closest_player.y - enemy.y)
                log_game.debug(f"[ENEMY_UPDATE] {enemy.enemy_id} pos=({enemy.x:.1f},{enemy.y:.1f}) state={getattr(enemy, 'state', 'N/A')} dist_to_player={dist_to_player:.1f}")

        notify = getattr(self.player, "notify_enemy_shot", None)
        for enemy in room.enemies:
            # Obtener el jugador más cercano para disparo también
            closest_player = self._get_closest_player_for_enemy(enemy)
            fired = enemy.maybe_shoot(dt, closest_player, room, self.enemy_projectiles)
            if fired and callable(notify):
                notify()

        # Actualizar boss si existe en la sala
        if hasattr(room, "boss") and room.boss:
            room.boss.update(dt)

    def _update_remote_enemies(self, dt: float) -> None:
        """
        Actualiza los enemigos remotos (animaciones, timers, sincronización).

        Los enemigos remotos ya tienen su posición actualizada por mensajes de red.
        Esta función avanza sus animaciones y mantiene sus timers al día.
        """
        if not self.remote_enemies:
            return

        for remote_enemy in self.remote_enemies.values():
            try:
                # Actualizar la animación (avanza frames)
                remote_enemy.update(dt)
            except Exception as e:
                log_game.error(f"Error actualizando remote_enemy {remote_enemy.enemy_id}: {e}")

    def _update_remote_player_rooms(self, dt: float) -> None:
        """
        En modo servidor: actualizar enemigos en salas donde hay jugadores remotos.

        Esto es necesario cuando PC2 entra a una sala diferente a la de PC1.
        PC1 (servidor) debe simular enemigos en esa sala aunque no esté allí.
        """
        if not self.net or not self.net.es_servidor:
            return

        if not self.remote_players:
            return

        # Recopilar todas las salas donde hay jugadores remotos
        remote_rooms = set()
        for rol, datos in self.remote_players.items():
            sala_list = datos.get("sala", [0, 0])
            sala_remota = (
                (sala_list[0], sala_list[1])
                if isinstance(sala_list, (list, tuple))
                else (0, 0)
            )
            # No procesar salas donde ya estamos (las procesa _update_enemies normal)
            if sala_remota != (self.dungeon.i, self.dungeon.j):
                remote_rooms.add(sala_remota)

        # Actualizar enemigos en cada sala remota
        for room_pos in remote_rooms:
            try:
                # self.dungeon.rooms es un diccionario con claves de tupla, no lista de listas
                room = self.dungeon.rooms.get(room_pos)
                if room is None:
                    log_game.debug(f"[SERVIDOR] Sala remota {room_pos} no existe en dungeon")
                    continue

                if not hasattr(room, "enemies"):
                    continue

                # IMPORTANTE: Si la sala remota no tiene enemigos aún, spawnearlos
                # (porque el servidor nunca entró a esa sala)
                if not room.enemies and hasattr(room, "ensure_spawn"):
                    # Calcular dificultad igual que en _spawn_room_enemies()
                    pos = room_pos
                    depth = 0
                    if hasattr(self.dungeon, "room_depth"):
                        depth = self.dungeon.room_depth(pos)
                    branch_factor = max(0, sum(1 for open_ in getattr(room, "doors", {}).values() if open_) - 2)
                    on_main_path = 0
                    if hasattr(self.dungeon, "main_path"):
                        on_main_path = 1 if pos in self.dungeon.main_path else 0
                    difficulty = 1 + depth + branch_factor + (depth // 3) + on_main_path

                    room.ensure_spawn(difficulty=difficulty, zone=self._current_zone, dungeon=self.dungeon)
                    log_game.debug(f"[SERVIDOR] Sala remota {room_pos} spawned enemigos (difficulty={difficulty})")

                # Simular enemigos en esta sala (pasar room_pos para targeting correcto)
                for enemy in room.enemies:
                    closest_player = self._get_closest_player_for_enemy(enemy, room_pos=room_pos)
                    if closest_player is not None:
                        enemy.update(dt, closest_player, room)

                # Procesar disparos de enemigos en sala remota
                for enemy in room.enemies:
                    closest_player = self._get_closest_player_for_enemy(enemy, room_pos=room_pos)
                    if closest_player is not None:
                        enemy.maybe_shoot(dt, closest_player, room, self.enemy_projectiles)

                # Sincronizar enemigos de esta sala remota
                self._sync_enemies_to_client_room(room, room_pos)
                log_game.debug(f"[SERVIDOR] Sala remota {room_pos} sincronizada ({len(room.enemies)} enemigos)")

            except Exception as e:
                log_game.debug(f"[SERVIDOR] Sala remota {room_pos} error: {type(e).__name__}: {e}")
                continue

    def _sync_enemies_to_client(self, room) -> None:
        """
        Sincroniza el estado de todos los enemigos al cliente remoto.
        Solo ejecuta si hay un cliente conectado (es decir, si estamos en modo servidor).
        """
        if not self.net or not hasattr(room, "enemies") or not room.enemies:
            return

        # Solo sincronizar si es el servidor (VICTIMA)
        if not self.net.es_servidor:
            return

        # Sincronizar cada 50ms (20 veces por segundo) para no sobrecargar la red
        ahora = time.time()
        if not hasattr(self, '_last_enemy_sync'):
            self._last_enemy_sync = 0.0

        if ahora - self._last_enemy_sync < 0.05:
            return

        self._last_enemy_sync = ahora

        # Preparar lista de enemigos
        enemies_list = []
        muertos_en_servidor = 0  # [DIAG] Contar enemigos muertos
        for enemy in room.enemies:
            # Obtener estado del animator
            animator_state = "idle"
            if hasattr(enemy, "animator"):
                animator_state = getattr(enemy.animator, "state", "idle")

                # [FIX] Si está en muerte o muriendo, SIEMPRE enviar "death"
                # Previene que trigger_shoot() sea rechazado mientras el enemigo muere
                if animator_state in ("shoot", "attack") and getattr(enemy, "_is_dying", False):
                    animator_state = "death"

            vivo = not getattr(enemy, "_is_dying", False)
            if not vivo:
                muertos_en_servidor += 1
                log_game.warning(f"[DIAG_SERVIDOR] Enviando MUERTO: {enemy.enemy_id} (_is_dying={getattr(enemy, '_is_dying', False)})")

            enemies_list.append({
                "id": enemy.enemy_id,
                "tipo": enemy.__class__.__name__,
                "x": round(enemy.x, 1),
                "y": round(enemy.y, 1),
                "health": enemy.hp,
                "vivo": vivo,
                "animator_state": animator_state,
                "facing_right": getattr(enemy, "_facing_right", True),
            })

        # Enviar sincronización
        if enemies_list or len(room.enemies) == 0:
            from network.protocol import msg_enemies_state
            msg = msg_enemies_state(enemies_list, (self.dungeon.i, self.dungeon.j))
            self.net.enviar(msg)
            log_game.debug(f"[DIAG_SERVIDOR] Sync: {len(enemies_list)} enemigos, {muertos_en_servidor} muertos")

    def _sync_enemies_to_client_room(self, room, room_pos: tuple) -> None:
        """
        Sincroniza enemigos de una sala específica al cliente.
        Similar a _sync_enemies_to_client pero para salas remotas donde hay jugadores.
        """
        if not self.net or not hasattr(room, "enemies"):
            return

        if not self.net.es_servidor:
            return

        # Sincronizar cada 50ms
        ahora = time.time()
        if not hasattr(self, '_last_remote_enemy_sync'):
            self._last_remote_enemy_sync = {}

        room_key = str(room_pos)
        if room_key in self._last_remote_enemy_sync:
            if ahora - self._last_remote_enemy_sync[room_key] < 0.05:
                return

        self._last_remote_enemy_sync[room_key] = ahora

        # Preparar lista de enemigos
        enemies_list = []
        for enemy in room.enemies:
            # Obtener estado del animator
            animator_state = "idle"
            if hasattr(enemy, "animator"):
                animator_state = getattr(enemy.animator, "state", "idle")

                # [FIX] Si está en muerte o muriendo, SIEMPRE enviar "death"
                # Previene que trigger_shoot() sea rechazado mientras el enemigo muere
                if animator_state in ("shoot", "attack") and getattr(enemy, "_is_dying", False):
                    animator_state = "death"

            enemies_list.append({
                "id": enemy.enemy_id,
                "tipo": enemy.__class__.__name__,
                "x": round(enemy.x, 1),
                "y": round(enemy.y, 1),
                "health": enemy.hp,
                "vivo": not getattr(enemy, "_is_dying", False),
                "animator_state": animator_state,
                "facing_right": getattr(enemy, "_facing_right", True),
            })

        # Enviar sincronización con la sala_pos correcta
        if enemies_list or len(room.enemies) == 0:
            from network.protocol import msg_enemies_state
            msg = msg_enemies_state(enemies_list, room_pos)
            self.net.enviar(msg)

    def _sync_enemy_projectiles_to_client(self, room) -> None:
        """
        Sincroniza el estado de todas las balas de enemigos al cliente.
        Solo ejecuta si es servidor y hay cliente conectado.
        """
        if not self.net or not self.net.es_servidor:
            return

        if not self.enemy_projectiles or len(self.enemy_projectiles) == 0:
            return

        # Sincronizar cada 50ms (igual que enemigos)
        ahora = time.time()
        if not hasattr(self, '_last_projectile_sync'):
            self._last_projectile_sync = 0.0

        if ahora - self._last_projectile_sync < 0.05:
            return

        self._last_projectile_sync = ahora

        # Preparar lista de balas (usar iterador de ProjectileGroup)
        projectiles_list = []
        for proj in self.enemy_projectiles:
            if proj.alive:
                projectiles_list.append({
                    "id": id(proj),  # ID único del objeto Python
                    "x": round(proj.x, 1),
                    "y": round(proj.y, 1),
                    "dx": round(proj.dx, 2),
                    "dy": round(proj.dy, 2),
                    "vivo": True,
                    "owner_id": getattr(proj, "owner_id", None),  # [FIX] Incluir owner_id para prevenir daño a enemigo propio
                })

        # Enviar sincronización (solo si hay balas)
        if projectiles_list:
            from network.protocol import msg_enemy_projectiles_state
            msg = msg_enemy_projectiles_state(projectiles_list, (self.dungeon.i, self.dungeon.j))
            self.net.enviar(msg)

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

        # Cliente: NO procesa colisiones de sus propios proyectiles contra enemigos
        # (El servidor procesará las colisiones y enviará eventos)
        if not (self.net and not self.net.es_servidor):
            # Servidor u offline: procesar colisiones de proyectiles locales
            for projectile in self.projectiles:
                if not projectile.alive:
                    continue
                r_proj = projectile.rect()
                for enemy in room.enemies:
                    if r_proj.colliderect(enemy.rect()):
                        # [FIX] No permitir que un enemigo se dañe con sus propios proyectiles
                        enemy_id = getattr(enemy, "enemy_id", None)
                        projectile_owner = getattr(projectile, "owner_id", None)

                        # [DIAG] Log de colisión
                        log_game.info(f"[COLLISION] Proj owner={projectile_owner}, Enemy={enemy_id}, Type={type(enemy).__name__}")

                        if projectile_owner and enemy_id == projectile_owner:
                            # Este es el enemigo que disparó el proyectil — ignorar
                            log_game.warning(f"[COLLISION] BLOCKED: {enemy_id} hit by own projectile")
                            continue

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
                    # [FIX] No permitir que un enemigo se dañe con sus propios proyectiles (incluso remotos)
                    enemy_id = getattr(enemy, "enemy_id", None)
                    projectile_owner = getattr(projectile, "owner_id", None)

                    if projectile_owner and enemy_id == projectile_owner:
                        # Este es el enemigo que disparó el proyectil — ignorar
                        continue
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
                    log_game.info(f"[DEATH_READY] Enviando muerte desde update (ready_to_remove): {enemy.enemy_id} en ({enemy.x:.1f}, {enemy.y:.1f})")
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
            was_cleared_before = room.cleared
            room.refresh_lock_state()
            # Si la sala se acaba de limpiar, notificar al cliente remoto
            if not was_cleared_before and room.cleared and self.net and self.net.es_servidor:
                from network.protocol import msg_evento
                evento = msg_evento(
                    "room_clear",
                    room_id=(self.dungeon.i, self.dungeon.j)
                )
                self.net.enviar(evento)
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
        should_do_respawn = False

        if hasattr(self.player, "lose_life"):
            try:
                can_continue = bool(self.player.lose_life())
            except TypeError:
                can_continue = False

        if can_continue:
            # Check if a complete corazón was lost (should_respawn)
            if hasattr(self.player, "should_respawn"):
                should_do_respawn = bool(self.player.should_respawn())

            # ONLY respawn and reset position if a complete corazón was lost
            if should_do_respawn:
                if hasattr(self.player, "respawn"):
                    self.player.respawn()
                else:
                    max_hp = getattr(self.player, "max_hp", 1)
                    self.player.hp = max_hp
                    invuln = getattr(self.player, "respawn_invulnerability", 2.0)
                    self.player.invulnerable_timer = max(
                        getattr(self.player, "invulnerable_timer", 0.0), invuln
                    )

                # Reset position to room center ONLY when complete corazón lost
                if hasattr(room, "center_px"):
                    px, py = room.center_px()
                    self.player.x = px - self.player.w / 2
                    self.player.y = py - self.player.h / 2

                # Efecto de spawn manejado internamente en Player._iniciar_revival()
                self.projectiles.clear()
                self.enemy_projectiles.clear()
                self.door_cooldown = 0.25
            else:
                # Solo recuperar HP cuando se pierde una vida (no un corazón completo)
                max_hp = getattr(self.player, "max_hp", 1)
                self.player.hp = max_hp
                invuln = getattr(self.player, "post_hit_invulnerability", 0.45)
                self.player.invulnerable_timer = max(
                    getattr(self.player, "invulnerable_timer", 0.0), invuln
                )
                self.projectiles.clear()
                self.enemy_projectiles.clear()
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

        # EN MODO CLIENTE: Notificar al servidor, NO procesar localmente
        if self.net and not self.net.es_servidor:
            log_game.info(f"[TRANSICION] Cliente detectó puerta en dirección {direction}")
            from network.protocol import msg_accion
            msg = msg_accion("transicion", direccion=direction)
            self.net.enviar(msg)
            self.door_cooldown = 0.25
            return

        # EN MODO SERVIDOR O OFFLINE: Procesar transición
        self._procesar_transicion(direction, room)

    def _procesar_transicion(self, direction: str, room) -> None:
        """Procesa la transición y teletransporta a ambos jugadores (si está en servidor)."""
        if hasattr(self.dungeon, "move_and_enter"):
            moved = self.dungeon.move_and_enter(direction, self.player, self.cfg, ShopkeeperCls=Shopkeeper)
        else:
            self.dungeon.move(direction)
            moved = True
        if not moved:
            return

        # Posicionar al jugador local
        victima_pos = self.dungeon.entry_position(
            direction, self.player.w, self.player.h
        )
        self.player.x, self.player.y = victima_pos

        # Limpiar y actualizar
        self.dungeon.explored.add((self.dungeon.i, self.dungeon.j))
        self.door_cooldown = 0.25
        self.projectiles.clear()
        self.enemy_projectiles.clear()
        self.death_effect_manager.clear()
        power_effect_manager.limpiar()  # Limpiar efectos de poderes al cambiar sala

        new_room = self.dungeon.current_room
        depth = self.dungeon.depth_map.get((self.dungeon.i, self.dungeon.j), -1)
        log_room.room_enter((self.dungeon.i, self.dungeon.j), depth)
        # [FIX SYNC] Cliente NO crea enemigos — los recibe del servidor
        if self.net is None or self.net.es_servidor:
            self._spawn_room_enemies(new_room)
        self._update_room_lock(new_room)

        # Notificar al cliente si estamos en servidor
        if self.net and self.net.es_servidor and self.remote_players:
            aliado_pos = victima_pos  # Mismo punto de entrada
            from network.protocol import msg_transicion_completada
            msg = msg_transicion_completada(
                sala_nueva=(self.dungeon.i, self.dungeon.j),
                pos_victima=victima_pos,
                pos_aliado=aliado_pos,
            )
            self.net.enviar(msg)
            log_game.info(f"[TRANSICION] Servidor notificó transición completada a sala ({self.dungeon.i}, {self.dungeon.j})")

            # [FIX SYNC] Enviar estado de enemigos inmediatamente después de la transición
            # para que el cliente no vea una sala vacía
            self._sync_enemies_to_client(new_room)
            self._sync_enemy_projectiles_to_client(new_room)

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

            # Efecto visual: onda expansiva eléctrica cian
            power_effect_manager.spawn_emp(
                self.player.x + self.player.w // 2,
                self.player.y + self.player.h // 2
            )

            if hasattr(self, "subtitulos"):
                self.subtitulos.agregar(f"[EMP] {count} enemigos congelados!", duracion=2.5, tipo="apoyo")
            log_game.info("EMP usado: %d enemigos congelados", count)

        elif iid == "modo_privado":
            if not getattr(self.player, "_ibarra_modo_privado", False):
                return
            self.player._ibarra_modo_privado = False
            current = getattr(self.player, "invulnerable_timer", 0.0)
            self.player.invulnerable_timer = max(current, 5.0)

            # Efecto visual: aura dorada pulsante
            power_effect_manager.spawn_invulnerabilidad(self.player)

            if hasattr(self, "subtitulos"):
                self.subtitulos.agregar("[Modo Privado] Invulnerable 5s!", duracion=2.5, tipo="apoyo")
            log_game.info("Modo Privado usado: invulnerable 5s")

        elif iid == "red_apoyo":
            # Verificar si tiene curaciones acumuladas (ahora es un contador)
            cantidad = getattr(self.player, "_ibarra_red_apoyo", 0)
            if cantidad <= 0:
                return
            # Restar 1 cura
            self.player._ibarra_red_apoyo = cantidad - 1
            # Restaurar FULL HP (todos los corazones)
            self.player.lives = self.player.max_lives
            self.player.hp = self.player.max_hp
            self.player._hits_taken_current_life = 0

            # Efecto visual: partículas verdes/rosas ascendentes + número flotante
            power_effect_manager.spawn_cura(
                self.player.x + self.player.w // 2,
                self.player.y + self.player.h // 2,
                cantidad_curada=2  # Vida recuperada (2 corazones completos)
            )

            if hasattr(self, "subtitulos"):
                self.subtitulos.agregar("[Red de Apoyo] ¡Salud restaurada al máximo!", duracion=2.5, tipo="apoyo")
            log_game.info("Red de Apoyo usada: salud restaurada a máximo")

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

    def _check_zone_transitions(self) -> None:
        """
        Verifica si el jugador ha entrado en una nueva zona.
        - La cinemática de transición se dispara UNA SOLA VEZ por zona por partida.
        - Además muestra un banner estilo Binding of Isaac con el nombre de la zona.
        """
        if not hasattr(self.dungeon, "room_zone"):
            return

        current_pos = (self.dungeon.i, self.dungeon.j)
        new_zone = self.dungeon.room_zone(current_pos)

        if new_zone is None:
            return

        if new_zone != self._current_zone:
            self._current_zone = new_zone

            # --- Cambiar tileset según la zona ---
            self.tileset_manager.set_zone(new_zone)

            # --- Cambiar paleta del fondo matrix según la zona ---
            self.matrix_bg.set_zona(new_zone)

            # Cinemática: solo una vez por zona por partida (excepto Zona 2)
            if new_zone not in self._zones_cinematics_shown and new_zone != 2:
                self._zones_cinematics_shown.add(new_zone)
                cinematic_id = f"zone_transition_{new_zone}"
                self.cinematics.reproducir(cinematic_id)

            # Banner de zona (siempre que cambia, no solo la primera vez)
            _ZONE_NAMES = {
                1: ("ZONA 1", "Los primeros comentarios"),
                2: ("ZONA 2", "La viralización"),
            }
            name, sub = _ZONE_NAMES.get(new_zone, (f"ZONA {new_zone}", ""))
            self._show_zone_banner(name, sub)

    def _check_boss_room_entry(self, room) -> None:
        """Muestra un banner temporal al entrar a la sala del boss (solo una vez por run)."""
        if self._boss_banner_shown:
            return
        if getattr(room, "type", "") != "boss":
            return
        self._boss_banner_shown = True
        self._show_zone_banner("SALA DEL BOSS", "¿Estás listo?")

        # Activar boss si existe en la sala
        if hasattr(room, "boss") and room.boss:
            room.boss.activar()

    def _show_zone_banner(self, title: str, subtitle: str = "") -> None:
        """Activa el banner de zona con el texto dado."""
        self._zone_banner_text = title
        self._zone_banner_sub = subtitle
        self._zone_banner_timer = self._ZONE_BANNER_DURATION

    def _draw_zone_banner(self) -> None:
        """Dibuja el banner estilo Binding of Isaac si está activo."""
        if self._zone_banner_timer <= 0:
            return

        sw, sh = self.screen.get_size()
        t = self._zone_banner_timer
        dur = self._ZONE_BANNER_DURATION
        fade = self._ZONE_BANNER_FADE

        # Calcular alpha (fade in al inicio, fade out al final)
        if t > dur - fade:
            alpha = int(255 * (dur - t) / fade)
        elif t < fade:
            alpha = int(255 * t / fade)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))

        # Fuente grande para el título (cacheada en el objeto)
        if not hasattr(self, "_banner_font_title"):
            try:
                vt323 = str(assets_dir("ui") / "VT323-Regular.ttf")
                self._banner_font_title = pygame.font.Font(vt323, 72)
                self._banner_font_sub   = pygame.font.Font(vt323, 36)
            except Exception:
                self._banner_font_title = pygame.font.SysFont("consolas", 52)
                self._banner_font_sub   = pygame.font.SysFont("consolas", 28)
        font_title = self._banner_font_title
        font_sub   = self._banner_font_sub

        title_surf = font_title.render(self._zone_banner_text, True, (230, 220, 200))
        sub_surf = font_sub.render(self._zone_banner_sub, True, (170, 155, 135)) if self._zone_banner_sub else None

        # Franja horizontal semitransparente en tercio superior
        banner_h = title_surf.get_height() + (sub_surf.get_height() + 8 if sub_surf else 0) + 28
        banner_y = sh // 3 - banner_h // 2  # Posicionar en tercio superior en lugar de centro

        banner = pygame.Surface((sw, banner_h), pygame.SRCALPHA)
        banner.fill((0, 0, 0, int(160 * alpha / 255)))
        self.screen.blit(banner, (0, banner_y))

        # Líneas decorativas
        line_col = (180, 140, 80, alpha)
        line_surf = pygame.Surface((sw, 2), pygame.SRCALPHA)
        line_surf.fill(line_col)
        self.screen.blit(line_surf, (0, banner_y))
        self.screen.blit(line_surf, (0, banner_y + banner_h - 2))

        # Título
        title_surf.set_alpha(alpha)
        self.screen.blit(title_surf, title_surf.get_rect(center=(sw // 2, banner_y + 16 + title_surf.get_height() // 2)))

        # Subtítulo
        if sub_surf:
            sub_surf.set_alpha(alpha)
            self.screen.blit(sub_surf, sub_surf.get_rect(center=(sw // 2, banner_y + banner_h - 16 - sub_surf.get_height() // 2)))


    def _render(self) -> None:
        self._render_world()
        self._render_ui()

    def _render_world(self) -> None:
        self.world.fill(self.cfg.COLOR_BG)

        # --- Renderizar fondo matrix antes de salas y entidades ---
        self.matrix_bg.render(self.world)

        room = self.dungeon.current_room
        # Usar tileset correspondiente a la zona actual
        current_tileset = self.tileset_manager.get_current_tileset()
        room.draw(self.world, current_tileset)

        if hasattr(room, "enemies"):
            # [DIAG] Log cada 60 frames para ver qué se renderiza
            if not hasattr(self, '_diag_render_counter'):
                self._diag_render_counter = 0
            self._diag_render_counter += 1

            if self._diag_render_counter % 60 == 0:
                muertos_en_lista = sum(1 for e in room.enemies if getattr(e, "_is_dying", False))
                log_game.warning(f"[DIAG_CLIENTE_RENDER] room.enemies={len(room.enemies)}, muertos={muertos_en_lista}")
                for enemy in room.enemies:
                    dying = getattr(enemy, "_is_dying", False)
                    log_game.warning(f"[DIAG_CLIENTE_RENDER] → {enemy.enemy_id} (_is_dying={dying})")

            for enemy in room.enemies:
                enemy.draw(self.world)

        # Renderizar boss si existe
        if hasattr(room, "boss") and room.boss:
            room.boss.render(self.world)

        # Renderizar efectos de muerte
        self.death_effect_manager.render(self.world)

        # Renderizar efectos de poderes (EMP, invulnerabilidad, cura)
        power_effect_manager.render(self.world, camera_offset=(0, 0))

        for pickup in getattr(room, "pickups", ()):
            pickup.draw(self.world)

        # Flash effect ahora manejado internamente en Player._render_revival()
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

            pygame.mouse.set_visible(False)  # Ocultar cursor durante cinemática
            self.cinematics.draw(self.screen, screen_scale=self.cfg.SCREEN_SCALE)
            # Consola de debug encima de todo
            self.debug_console.draw(self.screen)
            pygame.display.flip()
            return

        # --- Dibujar diálogos si están activos ---
        if self.dialogue.activo:
            pygame.mouse.set_visible(True)  # Mostrar cursor en diálogos
            self.dialogue.draw(self.screen, screen_scale=self.cfg.SCREEN_SCALE)
            # Consola de debug encima de todo
            self.debug_console.draw(self.screen)
            pygame.display.flip()
            return

        # --- Dibujar minijuego Papers si está activo ---
        if self.minijuego_papers is not None:
            pygame.mouse.set_visible(True)  # Mostrar cursor en minijuego
            self.minijuego_papers.render(self.screen)
            # Consola de debug encima de todo
            self.debug_console.draw(self.screen)
            pygame.display.flip()
            return

        # Panel de inventario anterior eliminado
        # La vida y monedas se mostrarán en los nuevos paneles cuando lleguen

        seed_text = self.ui_font.render(f"Seed: {self.current_seed}", True, (230, 230, 230))
        seed_position = (20, 100)
        self.screen.blit(seed_text, seed_position)

        # Dibujar los nuevos paneles de jugadores (con placeholders de color)
        player_data_p1 = {
            "health": getattr(self.player, "lives", 0),
            "max_health": getattr(self.player, "max_lives", 0),
            "coins": getattr(self.player, "gold", 0),
            "red_apoyo": getattr(self.player, "_ibarra_red_apoyo", 0),  # Contador de curaciones acumuladas
            "modo_privado": getattr(self.player, "_ibarra_modo_privado", False),
            "emp": getattr(self.player, "_ibarra_emp", False),
            "eco_señal": getattr(self.player, "_ibarra_double_shot", False)
        }
        self.hud_panel_p1.render(self.screen, player_data_p1, es_p2=False)

        # Panel del Jugador 2 (si hay jugador remoto)
        if self.remote_players:
            # Obtener datos del primer jugador remoto
            remote_player = next(iter(self.remote_players.values()), None)
            if remote_player:
                player_data_p2 = {
                    "health": getattr(remote_player, "lives", 0),
                    "max_health": getattr(remote_player, "max_lives", 0),
                    "coins": getattr(remote_player, "gold", 0),
                    "red_apoyo": getattr(remote_player, "_ibarra_red_apoyo", 0),  # Contador de curaciones acumuladas
                    "modo_privado": getattr(remote_player, "_ibarra_modo_privado", False),
                    "emp": getattr(remote_player, "_ibarra_emp", False),
                    "eco_señal": getattr(remote_player, "_ibarra_double_shot", False)
                }
            else:
                player_data_p2 = {
                    "health": 0, "max_health": 0, "coins": 0,
                    "red_apoyo": 0, "modo_privado": False, "emp": False, "eco_señal": False
                }
        else:
            player_data_p2 = {
                "health": 0, "max_health": 0, "coins": 0,
                "red_apoyo": 0, "modo_privado": False, "emp": False, "eco_señal": False
            }

        self.hud_panel_p2.render(self.screen, player_data_p2, es_p2=True)

        minimap_surface = self.minimap.render(self.dungeon)
        minimap_position = self.hud_panels.compute_minimap_position(self.screen, minimap_surface)
        # Renderizar minimapa sin el marco (frame panel eliminado)
        self.screen.blit(minimap_surface, minimap_position)

        # Paneles de esquina eliminados (panel_esquina.png, panel_esquina_inverso.png)

        # Contador de fragmentos de empatía
        self._draw_empathy_counter()

        # Iconos de ítems guardados del Profesor Ibarra (EMP / Modo Privado)
        self._draw_ibarra_item_hud(self.screen)

        # Notificaciones de subtítulos (fragmentos ganados, apoyos, etc.)
        self.subtitulos.draw(self.screen, screen_scale=self.cfg.SCREEN_SCALE)

        # Diálogo del Profesor Ibarra (encima del HUD)
        _ibarra_interacting = False
        try:
            _room = self.dungeon.current_room
            if getattr(_room, "type", "") == "profesor_ibarra":
                _prof = getattr(_room, "profesor_ibarra", None)
                if _prof is not None:
                    # Verificar si Profesor Ibarra está en estado de interacción (no IDLE)
                    if getattr(_prof, "estado", "idle") != "idle":
                        _ibarra_interacting = True
                    _prof.draw_screen(self.screen)
        except Exception:
            pass

        # Mostrar/ocultar cursor según estado de interfaz
        # El cursor debe estar visible en: tienda, interacción con Profesor Ibarra, menú de pausa
        shop_active = getattr(self.shop, "active", False)
        should_show_cursor = _ibarra_interacting or shop_active

        # Siempre establecer el estado correcto del cursor cada frame
        # para evitar desincronización cuando el menú de pausa oculta/muestra el cursor
        pygame.mouse.set_visible(should_show_cursor)

        # Banner de cambio de zona / sala del boss (encima de todo el HUD)
        self._draw_zone_banner()

        # Consola de debug: se dibuja encima de todo
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

    # MÉTODOS DE BATERÍAS REMOVIDOS - Reemplazados con sistema de corazones en HUDPanel
    # - _load_battery_states()
    # - _player_hits_remaining()
    # - _battery_surface()
    # - _blit_life_batteries() 
