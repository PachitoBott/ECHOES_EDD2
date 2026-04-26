"""
narrative/narrative_manager.py
===============================
Orquestador central de la narrativa de Echoes.

Responsabilidades:
  - Seguir la etapa actual de la historia (1 → 2 → 3 → 4).
  - Lanzar cinematicas en los momentos correctos.
  - Gestionar el NPC Alex (creacion, reposicion por etapa, diálogos vistos).
  - Notificar al juego cuando cambiar de etapa o ejecutar un final.

Arquitectura de etapas:
  Etapa 1  — intro + sala inicial + Alex aparece.
  Etapa 2  — cinematica "etapa_2", mas enemigos, Alex sigue.
  Etapa 3  — cinematica "boss", jefe final.
  Etapa 4  — cinematica "final_bueno" o "final_malo" segun resultado.

Integracion tipica en Game.py::

    nm = NarrativeManager(
        screen_w=960, screen_h=640,
        tile_size=32, screen_scale=2,
    )
    nm.inicializar()   # carga JSON, crea NPCs y DialogueSystem

    # Inicio del juego:
    nm.iniciar_juego(estado_juego)

    # Game loop:
    nm.update(player, estado_juego, dt)
    if nm.cinematica_activa:
        nm.draw_cinematica(surface)
    if nm.dialogo_activo:
        nm.draw_dialogo(surface)
    nm.draw_npcs(surface, cam_x, cam_y)

    # Input (consume eventos si cinematica o dialogo activo):
    consumido = nm.handle_event(evento, estado_juego)

    # Cuando el jugador derrota al jefe:
    nm.on_boss_derrotado(estado_juego, victoria=True)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from narrative.cinematics import CinematicSystem
from narrative.dialogue_system import DialogueSystem
from narrative.npc import NPC
from data_structures.tree import construir_arbol_alex

try:
    import pygame
    _PYGAME_DISPONIBLE = True
except ImportError:
    _PYGAME_DISPONIBLE = False


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_DIR_DATA = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# NarrativeManager
# ---------------------------------------------------------------------------

class NarrativeManager:
    """
    Gestor de la narrativa completa del juego.

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    tile_size : int
        Tamano de tile en pixeles logicos.
    screen_scale : int
        Factor de escala (SCREEN_SCALE).
    on_etapa_cambio : callable | None
        Callback(nueva_etapa: int) llamado al avanzar de etapa.
    on_fin_juego : callable | None
        Callback(victoria: bool) llamado al llegar al final.
    """

    ETAPAS_TOTALES = 4

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        tile_size: int = 32,
        screen_scale: int = 2,
        on_etapa_cambio: Optional[Callable[[int], None]] = None,
        on_fin_juego: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self.screen_w      = screen_w
        self.screen_h      = screen_h
        self.tile_size     = tile_size
        self.screen_scale  = screen_scale

        self._etapa_actual  = 1
        self._inicializado  = False

        # Callbacks externos
        self._on_etapa_cambio = on_etapa_cambio
        self._on_fin_juego    = on_fin_juego

        # Sub-sistemas (se construyen en inicializar())
        self._cinematicas: Optional[CinematicSystem] = None
        self._dialogo:     Optional[DialogueSystem]  = None
        self._npcs:        List[NPC]                 = []
        self._alex:        Optional[NPC]             = None

        # Control de cinematica bloqueante
        self._cinem_bloquea = True

    # ------------------------------------------------------------------ #
    # Inicializacion
    # ------------------------------------------------------------------ #

    def inicializar(self) -> None:
        """
        Carga todos los recursos narrativos.

        Debe llamarse una vez antes del game loop, con pygame ya iniciado
        (o en modo test sin pygame).
        """
        # Sistema de cinematicas
        self._cinematicas = CinematicSystem(self.screen_w, self.screen_h, font_size=22)
        ruta_cinem = _DIR_DATA / "cinematics.json"
        if ruta_cinem.exists():
            self._cinematicas.cargar_json(ruta_cinem)

        # Sistema de dialogos
        self._dialogo = DialogueSystem(self.screen_w, self.screen_h, font_size=14)

        # Cargar arbol de Alex desde JSON; si falla, usar el construido en codigo
        ruta_alex = _DIR_DATA / "alex_dialogues.json"
        if ruta_alex.exists():
            try:
                self._dialogo.cargar_json(ruta_alex, "alex")
            except Exception:
                self._dialogo.registrar_arbol("alex", construir_arbol_alex())
        else:
            self._dialogo.registrar_arbol("alex", construir_arbol_alex())

        self._inicializado = True

    # ------------------------------------------------------------------ #
    # Creacion de NPCs
    # ------------------------------------------------------------------ #

    def crear_alex(self, tile_x: int, tile_y: int) -> NPC:
        """
        Crea y registra el NPC Alex en la posicion indicada.

        Retorna el NPC creado.
        """
        assert self._inicializado, "Llama inicializar() primero"
        alex = NPC(
            nombre="Alex",
            id_arbol="alex",
            tile_x=tile_x,
            tile_y=tile_y,
            tile_size=self.tile_size,
            dialogue_system=self._dialogo,
            sprite_color=(80, 160, 230),
        )
        self._alex = alex
        # Agregar a la lista si no estaba ya
        if alex not in self._npcs:
            self._npcs.append(alex)
        return alex

    def reposicionar_alex(self, tile_x: int, tile_y: int) -> None:
        """Mueve a Alex a una nueva posicion del dungeon."""
        if self._alex:
            self._alex.tile_x = tile_x
            self._alex.tile_y = tile_y
            self._alex.resetear_dialogo()

    # ------------------------------------------------------------------ #
    # Inicio del juego
    # ------------------------------------------------------------------ #

    def iniciar_juego(
        self,
        estado_juego: Optional[Dict[str, Any]] = None,
        mostrar_intro: bool = True,
    ) -> None:
        """
        Lanza la cinematica de intro y prepara la etapa 1.

        Parametros
        ----------
        estado_juego  : dict con el estado inicial del jugador.
        mostrar_intro : si False, salta la cinematica de intro.
        """
        assert self._inicializado, "Llama inicializar() primero"
        self._etapa_actual = 1
        if mostrar_intro and self._cinematicas:
            self._cinematicas.reproducir("intro")

    # ------------------------------------------------------------------ #
    # Transiciones de etapa
    # ------------------------------------------------------------------ #

    def avanzar_etapa(
        self,
        estado_juego: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Avanza a la siguiente etapa (1 -> 2 -> 3 -> 4).

        Dispara la cinematica correspondiente y llama al callback.

        Retorna el numero de la nueva etapa.
        """
        if self._etapa_actual >= self.ETAPAS_TOTALES:
            return self._etapa_actual

        self._etapa_actual += 1
        nueva = self._etapa_actual

        # Cinematica de transicion
        if self._cinematicas:
            if nueva == 2:
                self._cinematicas.reproducir("etapa_2")
            elif nueva == 3:
                self._cinematicas.reproducir("boss")

        # Resetear dialogo de Alex para la nueva etapa
        if self._alex:
            self._alex.resetear_dialogo()

        # Callback externo
        if callable(self._on_etapa_cambio):
            self._on_etapa_cambio(nueva)

        return nueva

    def on_boss_derrotado(
        self,
        estado_juego: Optional[Dict[str, Any]] = None,
        victoria: bool = True,
    ) -> None:
        """
        Llama a este metodo cuando el jefe final cae (o el jugador muere).

        Dispara la cinematica de final correspondiente y el callback.
        """
        id_cinem = "final_bueno" if victoria else "final_malo"
        if self._cinematicas:
            self._cinematicas.reproducir(
                id_cinem,
                callback_fin=lambda: self._notificar_fin(victoria),
            )
        else:
            self._notificar_fin(victoria)

    def _notificar_fin(self, victoria: bool) -> None:
        if callable(self._on_fin_juego):
            self._on_fin_juego(victoria)

    # ------------------------------------------------------------------ #
    # Game loop
    # ------------------------------------------------------------------ #

    def update(
        self,
        player_tile_x: float,
        player_tile_y: float,
        estado_juego: Optional[Dict[str, Any]] = None,
        dt: float = 0.0,
    ) -> None:
        """
        Actualiza todos los NPCs.

        Llama una vez por frame.
        """
        for npc in self._npcs:
            npc.update(player_tile_x, player_tile_y, estado_juego, dt)

    def handle_event(
        self,
        event: "pygame.event.Event",
        estado_juego: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Procesa un evento de pygame.

        Retorna True si el evento fue consumido (juego no debe procesarlo).
        """
        if not _PYGAME_DISPONIBLE:
            return False

        # Cinematica activa: solo permite Escape para saltar
        if self.cinematica_activa:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._cinematicas.saltar()
            return True   # consume el evento

        # Dialogo activo
        if self.dialogo_activo and self._dialogo:
            return self._dialogo.handle_event(event)

        # Interaccion con NPC (tecla E)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            for npc in self._npcs:
                if npc.puede_interactuar:
                    npc.interactuar(estado_juego)
                    return True

        return False

    # ------------------------------------------------------------------ #
    # Draw
    # ------------------------------------------------------------------ #

    def draw_cinematica(self, surface: "pygame.Surface") -> None:
        """Dibuja la cinematica activa (si hay una)."""
        if self._cinematicas and self._cinematicas.activo:
            self._cinematicas.draw(surface, self.screen_scale)

    def draw_dialogo(self, surface: "pygame.Surface") -> None:
        """Dibuja el cuadro de dialogo activo (si hay uno)."""
        if self._dialogo and self._dialogo.activo:
            self._dialogo.draw(surface, self.screen_scale)

    def draw_npcs(
        self,
        surface: "pygame.Surface",
        cam_x: int = 0,
        cam_y: int = 0,
    ) -> None:
        """Dibuja todos los NPCs visibles."""
        for npc in self._npcs:
            npc.draw(surface, cam_x, cam_y, self.screen_scale)

    def tick_cinematica(self, dt: float) -> None:
        """Avanza el tiempo de la cinematica activa."""
        if self._cinematicas and self._cinematicas.activo:
            self._cinematicas.tick(dt)

    def tick_dialogo(self, dt: float) -> Optional[Dict[str, Any]]:
        """Avanza el dialogo activo. Retorna efecto si hubo."""
        if self._dialogo and self._dialogo.activo:
            return self._dialogo.tick(dt)
        return None

    # ------------------------------------------------------------------ #
    # Consultas de estado
    # ------------------------------------------------------------------ #

    @property
    def etapa_actual(self) -> int:
        return self._etapa_actual

    @property
    def cinematica_activa(self) -> bool:
        return bool(self._cinematicas and self._cinematicas.activo)

    @property
    def dialogo_activo(self) -> bool:
        return bool(self._dialogo and self._dialogo.activo)

    @property
    def bloqueado(self) -> bool:
        """True si el input del juego debe estar bloqueado."""
        return self.cinematica_activa or self.dialogo_activo

    @property
    def alex(self) -> Optional[NPC]:
        return self._alex

    @property
    def dialogue_system(self) -> Optional[DialogueSystem]:
        return self._dialogo

    @property
    def cinematic_system(self) -> Optional[CinematicSystem]:
        return self._cinematicas

    @property
    def npcs(self) -> List[NPC]:
        return list(self._npcs)

    def etapa_como_str(self) -> str:
        nombres = {1: "Inicio", 2: "Escalada", 3: "Jefe Final", 4: "Epilogo"}
        return nombres.get(self._etapa_actual, "Desconocida")
