"""
narrative/dialogue_system.py
=============================
Sistema de dialogos para Echoes.

Responsabilidades:
  1. Cargar arboles de dialogo desde archivos JSON (usa ArbolDialogo de Fase 2).
  2. Mantener el estado de la conversacion activa (nodo actual).
  3. Renderizar el cuadro de dialogo en pantalla con pygame.
  4. Procesar eventos (click en opcion, teclado) y avanzar el arbol.

Arquitectura de la UI:
  DialogueBox  — dibuja el cuadro en una superficie pygame.
  DialogueSystem — gestiona estado + carga JSON + integra con ArbolDialogo.

Uso minimo desde Game.py::

    ds = DialogueSystem(screen_w=960, screen_h=640)
    ds.cargar_json("narrative/data/alex_dialogues.json", "alex")

    # Iniciar conversacion:
    ds.iniciar("alex", estado_juego={"armas": ["bloqueo"]})

    # En el game loop:
    if ds.activo:
        eventos_consumidos = ds.handle_event(evento_pygame)
        efecto = ds.tick(dt)           # avanza animaciones, retorna efecto si lo hay
        ds.draw(screen)                # dibuja sobre la pantalla
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pygame

from data_structures.tree import ArbolDialogo, NodoArbol


# ---------------------------------------------------------------------------
# Paleta de colores del cuadro de dialogo
# ---------------------------------------------------------------------------

_COL_BG        = (15, 20, 40, 220)    # RGBA fondo semitransparente
_COL_BORDE     = (80, 120, 200)
_COL_NOMBRE    = (100, 200, 255)
_COL_TEXTO     = (230, 230, 230)
_COL_OPCION    = (180, 220, 255)
_COL_OPCION_HL = (255, 255, 150)       # hover
_COL_OPCION_BG = (30, 40, 70, 180)
_COL_SEPARADOR = (60, 80, 140)


# ---------------------------------------------------------------------------
# DialogueBox — renderizado puro, sin estado de árbol
# ---------------------------------------------------------------------------

class DialogueBox:
    """
    Renderiza el cuadro de dialogo en una superficie pygame.

    No sabe nada del arbol de dialogos; solo recibe texto y opciones.

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones de la pantalla en pixeles logicos (antes del SCREEN_SCALE).
    font_size : int
        Tamanio de la fuente principal.
    """

    ALTO_CUADRO_RATIO = 0.35     # fraccion de la altura de pantalla
    MARGEN             = 16
    SEPARACION_OPCIONES = 28

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        font_size: int = 14,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._font       = pygame.font.SysFont(None, font_size)
        self._font_name  = pygame.font.SysFont(None, font_size + 4)
        self._font_hint  = pygame.font.SysFont(None, font_size - 2)
        self._scale      = 1          # se ajusta si se llama con SCREEN_SCALE

        # Cuadro: ocupa toda la anchura y ALTO_CUADRO_RATIO de la altura
        alto = int(screen_h * self.ALTO_CUADRO_RATIO)
        self._rect = pygame.Rect(0, screen_h - alto, screen_w, alto)

        # Superficie semitransparente reutilizable
        self._bg_surface = pygame.Surface(
            (self._rect.width, self._rect.height), pygame.SRCALPHA
        )

        # Indice de la opcion bajo el cursor
        self._hover_index: int = -1
        # Rects de cada opcion (para deteccion de clicks)
        self._option_rects: List[pygame.Rect] = []

    # ------------------------------------------------------------------ #
    # Dibujo
    # ------------------------------------------------------------------ #

    def draw(
        self,
        surface: pygame.Surface,
        nombre_npc: str,
        texto: str,
        opciones: List[str],
        screen_scale: int = 1,
    ) -> None:
        """
        Dibuja el cuadro completo sobre *surface*.

        Parametros
        ----------
        surface       : superficie de pantalla final (ya escalada).
        nombre_npc    : nombre que aparece en la cabecera.
        texto         : dialogo del NPC o narrador.
        opciones      : lista de textos de las opciones del jugador.
        screen_scale  : factor de escala (para ajustar posicion a la pantalla real).
        """
        self._scale = screen_scale
        # Recalcular rect escalado
        rect_real = pygame.Rect(
            self._rect.x * screen_scale,
            self._rect.y * screen_scale,
            self._rect.width * screen_scale,
            self._rect.height * screen_scale,
        )

        # Fondo semitransparente
        bg = pygame.Surface(rect_real.size, pygame.SRCALPHA)
        bg.fill(_COL_BG)
        surface.blit(bg, rect_real.topleft)

        # Borde superior
        pygame.draw.line(
            surface, _COL_BORDE,
            rect_real.topleft, rect_real.topright, 2
        )

        m = self.MARGEN * screen_scale
        x0 = rect_real.x + m
        y0 = rect_real.y + m

        # Nombre del NPC
        nombre_surf = self._font_name.render(nombre_npc, True, _COL_NOMBRE)
        surface.blit(nombre_surf, (x0, y0))
        y0 += nombre_surf.get_height() + int(6 * screen_scale)

        # Separador
        pygame.draw.line(
            surface, _COL_SEPARADOR,
            (x0, y0), (rect_real.right - m, y0), 1
        )
        y0 += int(8 * screen_scale)

        # Texto del NPC (con wrapping manual)
        max_ancho = rect_real.width - 2 * m
        lineas = self._wrap_text(texto, self._font, max_ancho)
        for linea in lineas:
            surf = self._font.render(linea, True, _COL_TEXTO)
            surface.blit(surf, (x0, y0))
            y0 += surf.get_height() + int(3 * screen_scale)

        y0 += int(10 * screen_scale)

        # Opciones
        self._option_rects = []
        if opciones:
            hint = self._font_hint.render(
                "Elige una respuesta:", True, _COL_SEPARADOR
            )
            surface.blit(hint, (x0, y0))
            y0 += hint.get_height() + int(4 * screen_scale)

        for i, op_texto in enumerate(opciones):
            lbl = self._font.render(f"  {i+1}. {op_texto}", True,
                                    _COL_OPCION_HL if i == self._hover_index else _COL_OPCION)
            op_rect = pygame.Rect(
                x0 - int(4 * screen_scale),
                y0 - int(2 * screen_scale),
                lbl.get_width() + int(8 * screen_scale),
                lbl.get_height() + int(4 * screen_scale),
            )
            self._option_rects.append(op_rect)
            if i == self._hover_index:
                hl_surf = pygame.Surface(op_rect.size, pygame.SRCALPHA)
                hl_surf.fill(_COL_OPCION_BG)
                surface.blit(hl_surf, op_rect.topleft)
            surface.blit(lbl, (x0, y0))
            y0 += self.SEPARACION_OPCIONES * screen_scale

        if not opciones:
            hint2 = self._font_hint.render(
                "[Clic o Espacio para continuar]", True, _COL_SEPARADOR
            )
            surface.blit(hint2, (x0, y0))

    # ------------------------------------------------------------------ #
    # Interaccion
    # ------------------------------------------------------------------ #

    def update_hover(self, mouse_pos: Tuple[int, int]) -> None:
        """Actualiza que opcion esta bajo el cursor (para efecto hover)."""
        self._hover_index = -1
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(mouse_pos):
                self._hover_index = i
                break

    def click_index(self, mouse_pos: Tuple[int, int]) -> int:
        """
        Retorna el indice de la opcion clickeada, o -1 si no hay opcion
        en esa posicion (clic en texto libre = avanzar sin opcion).
        """
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(mouse_pos):
                return i
        return -1

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #

    @staticmethod
    def _wrap_text(texto: str, font: pygame.font.Font, max_w: int) -> List[str]:
        """Parte el texto en lineas que caben dentro de max_w pixeles."""
        palabras = texto.split()
        lineas: List[str] = []
        actual = ""
        for palabra in palabras:
            prueba = (actual + " " + palabra).strip()
            if font.size(prueba)[0] <= max_w:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
        return lineas if lineas else [""]


# ---------------------------------------------------------------------------
# DialogueSystem — estado + carga JSON + integracion con ArbolDialogo
# ---------------------------------------------------------------------------

class DialogueSystem:
    """
    Gestiona conversaciones cargadas desde JSON y renderizadas con DialogueBox.

    Estado de la conversacion:
        _activo       : True mientras hay un dialogo en pantalla.
        _arbol_actual : ArbolDialogo en uso.
        _nodo_actual  : ID del nodo donde esta el jugador ahora.
        _opciones     : lista de NodoArbol disponibles en este nodo.
        _nombre_npc   : nombre del NPC que aparece en el cuadro.
        _estado_juego : dict con el estado actual del juego (armas, etc.).

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    font_size : int
        Tamanio de fuente del cuadro de dialogo.
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        font_size: int = 14,
    ) -> None:
        self._box = DialogueBox(screen_w, screen_h, font_size)
        self._arboles: Dict[str, ArbolDialogo] = {}    # cargados por ID
        self._activo = False
        self._arbol_actual: Optional[ArbolDialogo] = None
        self._nodo_actual: Optional[str] = None
        self._opciones: List[NodoArbol] = []
        self._nombre_npc: str = "???"
        self._estado_juego: Dict[str, Any] = {}
        self._callback_fin: Optional[Callable[[], None]] = None
        self._historial: List[str] = []    # IDs de nodos visitados

    # ------------------------------------------------------------------ #
    # Carga de datos
    # ------------------------------------------------------------------ #

    def cargar_json(self, ruta: str | Path, id_arbol: str) -> ArbolDialogo:
        """
        Carga un ArbolDialogo desde un archivo JSON y lo registra con *id_arbol*.

        El JSON debe tener la estructura de ArbolDialogo.exportar_dict():
          { "id": "...", "texto": "...", "meta": {...}, "hijos": [...] }

        Las condiciones se registran por nombre (clave "condicion_clave" en
        meta) y se resuelven contra el estado del juego en tiempo de ejecucion.

        Retorna el ArbolDialogo creado.
        """
        ruta = Path(ruta)
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)

        arbol = ArbolDialogo.desde_dict(data)
        # Reinstalar condiciones desde la clave "condicion_clave" en meta
        self._instalar_condiciones(arbol)
        self._arboles[id_arbol] = arbol
        return arbol

    def registrar_arbol(self, id_arbol: str, arbol: ArbolDialogo) -> None:
        """Registra un ArbolDialogo ya construido (de construir_arbol_alex, etc.)."""
        self._arboles[id_arbol] = arbol

    # ------------------------------------------------------------------ #
    # Control de la conversacion
    # ------------------------------------------------------------------ #

    def iniciar(
        self,
        id_arbol: str,
        nombre_npc: str = "Alex",
        estado_juego: Optional[Dict[str, Any]] = None,
        callback_fin: Optional[Callable[[], None]] = None,
    ) -> bool:
        """
        Inicia una conversacion con el arbol indicado.

        Parametros
        ----------
        id_arbol     : clave del arbol registrado (ver cargar_json/registrar_arbol).
        nombre_npc   : nombre que aparece en el cuadro de dialogo.
        estado_juego : dict con el estado actual (armas, vidas, apoyo...).
        callback_fin : funcion opcional llamada cuando termina el dialogo.

        Retorna True si el arbol existe y la conversacion comenzo.
        """
        arbol = self._arboles.get(id_arbol)
        if arbol is None:
            return False

        self._arbol_actual  = arbol
        self._nodo_actual   = arbol.raiz.id
        self._nombre_npc    = nombre_npc
        self._estado_juego  = estado_juego if estado_juego is not None else {}
        self._callback_fin  = callback_fin
        self._historial     = [arbol.raiz.id]
        self._activo        = True
        self._refrescar_opciones()
        return True

    def cerrar(self) -> None:
        """Cierra la conversacion activa sin disparar el callback."""
        self._activo = False
        self._arbol_actual = None
        self._nodo_actual = None
        self._opciones = []

    def obtener_nodo_actual(self) -> Optional[NodoArbol]:
        """Retorna el nodo actual del diálogo (útil para detectar opciones seleccionadas)."""
        if self._arbol_actual is None or self._nodo_actual is None:
            return None
        return self._arbol_actual.buscar(self._nodo_actual)

    def obtener_meta_nodo_actual(self) -> Dict[str, Any]:
        """Retorna la metadata del nodo actual."""
        nodo = self.obtener_nodo_actual()
        if nodo is None:
            return {}
        return nodo.meta or {}

    @property
    def activo(self) -> bool:
        return self._activo

    # ------------------------------------------------------------------ #
    # Game loop
    # ------------------------------------------------------------------ #

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Procesa un evento de pygame.

        Retorna True si el evento fue consumido (el juego no debe procesarlo).
        """
        if not self._activo:
            return False

        # Click con el mouse
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._box.click_index(event.pos)
            if idx >= 0 and idx < len(self._opciones):
                self._elegir_opcion(idx)
            elif idx == -1 and not self._opciones:
                # Sin opciones: clic avanza (o cierra)
                self._avanzar_o_cerrar()
            return True

        # Numeros 1-9 para elegir opcion
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and not self._opciones:
                self._avanzar_o_cerrar()
                return True
            if pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self._opciones):
                    self._elegir_opcion(idx)
                    return True
            if event.key == pygame.K_ESCAPE:
                self._terminar()
                return True

        # Movimiento del raton para hover
        if event.type == pygame.MOUSEMOTION:
            self._box.update_hover(event.pos)
            return True

        return True   # mientras el dialogo esta activo, consume todos los eventos

    def tick(self, dt: float) -> Optional[Dict[str, Any]]:
        """
        Actualiza el sistema de dialogos.

        Retorna el dict del efecto aplicado en este tick (si hubo), o None.
        """
        if not self._activo:
            return None
        return None

    def draw(self, surface: pygame.Surface, screen_scale: int = 1) -> None:
        """Dibuja el cuadro de dialogo sobre *surface*."""
        if not self._activo or self._nodo_actual is None or self._arbol_actual is None:
            return
        nodo = self._arbol_actual.buscar(self._nodo_actual)
        if nodo is None:
            return

        self._box.draw(
            surface,
            nombre_npc=self._nombre_npc,
            texto=nodo.texto,
            opciones=[op.texto for op in self._opciones],
            screen_scale=screen_scale,
        )

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _refrescar_opciones(self) -> None:
        """Actualiza la lista de opciones disponibles para el nodo actual."""
        if self._arbol_actual is None or self._nodo_actual is None:
            self._opciones = []
            return
        self._opciones = self._arbol_actual.obtener_opciones(
            self._nodo_actual, self._estado_juego
        )

    def _elegir_opcion(self, idx: int) -> None:
        """El jugador eligio la opcion en la posicion idx."""
        if idx >= len(self._opciones):
            return
        nodo_elegido = self._opciones[idx]
        self._historial.append(nodo_elegido.id)
        self._nodo_actual = nodo_elegido.id
        self._refrescar_opciones()

        # Si es hoja (sin opciones) y el nodo elegido tampoco tiene hijos,
        # el siguiente clic/espacio cerrara el dialogo
        if nodo_elegido.es_hoja():
            # Aplicar efecto si tiene uno
            efecto = nodo_elegido.meta.get("efecto")
            if efecto:
                self._arbol_actual.ejecutar_efecto(nodo_elegido.id, self._estado_juego)

    def _avanzar_o_cerrar(self) -> None:
        """Avanza al siguiente nodo (si hay exactamente uno) o cierra."""
        if self._arbol_actual is None:
            self._terminar()
            return
        nodo = self._arbol_actual.buscar(self._nodo_actual)
        if nodo and len(nodo.hijos) == 1:
            hijo = nodo.hijos[0]
            self._historial.append(hijo.id)
            self._nodo_actual = hijo.id
            self._refrescar_opciones()
            # Aplicar efecto si el nodo al que avanzamos es hoja con efecto
            if hijo.es_hoja():
                efecto = hijo.meta.get("efecto")
                if efecto:
                    self._arbol_actual.ejecutar_efecto(hijo.id, self._estado_juego)
        else:
            self._terminar()

    def _terminar(self) -> None:
        """Finaliza la conversacion y llama al callback."""
        self._activo = False
        if callable(self._callback_fin):
            self._callback_fin()

    def _instalar_condiciones(self, arbol: ArbolDialogo) -> None:
        """
        Recorre todos los nodos del arbol y asigna condiciones Python
        a partir de la clave "condicion_clave" en sus metadatos.

        La clave indica una condicion predefinida:
            "tiene_evidencia"  -> estado["armas"] contiene "evidencia"
            "etapa_2"          -> estado["etapa"] >= 2
            "etapa_3"          -> estado["etapa"] >= 3
            "vidas_bajas"      -> estado["vidas"] <= 1
        """
        _condiciones: Dict[str, Callable[[Dict], bool]] = {
            "tiene_evidencia": lambda e: "evidencia" in e.get("armas", []),
            "etapa_2":         lambda e: e.get("etapa", 1) >= 2,
            "etapa_3":         lambda e: e.get("etapa", 1) >= 3,
            "vidas_bajas":     lambda e: e.get("vidas", 10) <= 1,
        }
        for nodo in arbol.recorrer_preorden():
            clave = nodo.meta.get("condicion_clave")
            if clave and clave in _condiciones:
                nodo.condicion = _condiciones[clave]
