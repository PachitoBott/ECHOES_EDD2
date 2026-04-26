"""
data_structures/tree.py
=======================
Árbol de diálogos N-ario para el NPC aliado «Alex».

Características académicas (Fase 2 — EDD 2, UniNorte):
  - Árbol N-ario genérico: cada nodo puede tener cualquier cantidad de hijos.
  - Cada nodo almacena un fragmento de diálogo, una condición de desbloqueo
    opcional y metadatos arbitrarios (emoción, sprite, efectos de juego).
  - Operaciones implementadas:
      * insertar(id, texto, id_padre, condicion, **kwargs)
      * buscar(id)            -> NodoArbol | None   (BFS interno)
      * eliminar(id)          -> bool
      * recorrer_preorden()   -> list[NodoArbol]    (raíz, luego hijos)
      * recorrer_postorden()  -> list[NodoArbol]    (hijos, luego raíz)
      * recorrer_por_niveles()-> list[list[NodoArbol]]  (BFS por niveles)
      * obtener_opciones(id_actual, estado_juego)
                              -> list[NodoArbol]   (hijos desbloqueados)
      * altura()              -> int
      * tamaño()              -> int
      * es_hoja(id)           -> bool

Uso en el proyecto:
  - narrative/DialogueSystem.py cargará un JSON y reconstruirá el árbol.
  - Game.py llama a obtener_opciones() para mostrar las respuestas al jugador.
  - Cada NodoArbol puede disparar efectos: curación, ganancia de «apoyo», etc.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Nodo
# ---------------------------------------------------------------------------

class NodoArbol:
    """
    Un nodo del árbol de diálogos.

    Atributos
    ---------
    id : str
        Identificador único dentro del árbol (ej. ``"alex_intro_1"``).
    texto : str
        Diálogo que pronuncia el NPC (o el jugador) en este nodo.
    padre : NodoArbol | None
        Referencia al nodo padre; None para la raíz.
    hijos : list[NodoArbol]
        Lista ordenada de respuestas/continuaciones disponibles.
    condicion : Callable[[dict], bool] | None
        Función que recibe el estado del juego y devuelve True si este nodo
        está disponible.  None -> siempre disponible.
    meta : dict[str, Any]
        Datos adicionales libres: emoción del NPC, sprite, efectos, etc.
    """

    def __init__(
        self,
        id: str,
        texto: str,
        condicion: Optional[Callable[[Dict[str, Any]], bool]] = None,
        **meta: Any,
    ) -> None:
        self.id: str = id
        self.texto: str = texto
        self.padre: Optional[NodoArbol] = None
        self.hijos: List[NodoArbol] = []
        self.condicion: Optional[Callable[[Dict[str, Any]], bool]] = condicion
        self.meta: Dict[str, Any] = dict(meta)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def agregar_hijo(self, hijo: NodoArbol) -> None:
        """Vincula *hijo* como hijo directo de este nodo."""
        hijo.padre = self
        self.hijos.append(hijo)

    def quitar_hijo(self, id_hijo: str) -> bool:
        """Elimina el hijo con el id indicado. Devuelve True si lo encontró."""
        for i, h in enumerate(self.hijos):
            if h.id == id_hijo:
                self.hijos.pop(i).padre = None
                return True
        return False

    def esta_disponible(self, estado_juego: Dict[str, Any]) -> bool:
        """
        Evalúa si el nodo puede ser elegido dado el estado actual del juego.

        Si no tiene condición asignada siempre está disponible.
        """
        if self.condicion is None:
            return True
        try:
            return bool(self.condicion(estado_juego))
        except Exception:
            return False  # ante cualquier error, ocultamos la opción

    def es_hoja(self) -> bool:
        """True si el nodo no tiene hijos (fin de rama de diálogo)."""
        return len(self.hijos) == 0

    def profundidad(self) -> int:
        """Distancia desde la raíz hasta este nodo (raíz = 0)."""
        depth = 0
        actual = self.padre
        while actual is not None:
            depth += 1
            actual = actual.padre
        return depth

    # ------------------------------------------------------------------ #
    # Representación
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        cond = "sí" if self.condicion else "no"
        return (
            f"NodoArbol(id={self.id!r}, hijos={len(self.hijos)}, "
            f"condicion={cond})"
        )


# ---------------------------------------------------------------------------
# Árbol de diálogos
# ---------------------------------------------------------------------------

class ArbolDialogo:
    """
    Árbol N-ario de diálogos para el NPC aliado «Alex».

    La raíz representa el estado inicial de la conversación.  Cada hijo de
    un nodo es una opción de respuesta que el jugador puede elegir (si su
    condición lo permite).

    Parámetros
    ----------
    id_raiz : str
        Identificador del nodo raíz.
    texto_raiz : str
        Texto que pronuncia Alex al comenzar la conversación.
    """

    def __init__(self, id_raiz: str, texto_raiz: str, **meta: Any) -> None:
        self._raiz: NodoArbol = NodoArbol(id_raiz, texto_raiz, **meta)
        self._indice: Dict[str, NodoArbol] = {id_raiz: self._raiz}

    # ------------------------------------------------------------------ #
    # Propiedades
    # ------------------------------------------------------------------ #

    @property
    def raiz(self) -> NodoArbol:
        return self._raiz

    # ------------------------------------------------------------------ #
    # Modificación
    # ------------------------------------------------------------------ #

    def insertar(
        self,
        id: str,
        texto: str,
        id_padre: Optional[str] = None,
        condicion: Optional[Callable[[Dict[str, Any]], bool]] = None,
        **meta: Any,
    ) -> NodoArbol:
        """
        Crea un nuevo nodo y lo añade como hijo de *id_padre*.

        Si *id_padre* es None el nodo se inserta como hijo directo de la raíz.
        Si el *id* ya existe levanta ValueError.

        Parámetros
        ----------
        id : str
            Identificador único del nuevo nodo.
        texto : str
            Diálogo asociado al nodo.
        id_padre : str | None
            ID del nodo padre.  None -> hijo de la raíz.
        condicion : Callable | None
            Predicado ``(estado_juego: dict) -> bool`` que controla la
            visibilidad de la opción.
        **meta :
            Metadatos adicionales (emocion, sprite, efecto, etc.).

        Retorna
        -------
        NodoArbol recién creado.
        """
        if id in self._indice:
            raise ValueError(f"Ya existe un nodo con id={id!r} en el árbol.")

        padre_nodo = self._raiz if id_padre is None else self._indice.get(id_padre)
        if padre_nodo is None:
            raise KeyError(f"No se encontró el nodo padre con id={id_padre!r}.")

        nuevo = NodoArbol(id, texto, condicion=condicion, **meta)
        padre_nodo.agregar_hijo(nuevo)
        self._indice[id] = nuevo
        return nuevo

    def eliminar(self, id: str) -> bool:
        """
        Elimina el nodo con el *id* indicado y todo su subárbol.

        No se puede eliminar la raíz.

        Retorna True si lo eliminó, False si no lo encontró.
        """
        if id == self._raiz.id:
            raise ValueError("No se puede eliminar la raíz del árbol.")

        nodo = self._indice.get(id)
        if nodo is None:
            return False

        # Eliminar del índice recursivamente
        for descendiente in self._preorden_desde(nodo):
            self._indice.pop(descendiente.id, None)

        # Desvincularlo de su padre
        if nodo.padre:
            nodo.padre.quitar_hijo(id)

        return True

    # ------------------------------------------------------------------ #
    # Búsqueda
    # ------------------------------------------------------------------ #

    def buscar(self, id: str) -> Optional[NodoArbol]:
        """
        Devuelve el nodo con el *id* dado, o None si no existe.

        Usa el índice interno -> O(1).
        """
        return self._indice.get(id)

    def buscar_por_texto(self, fragmento: str) -> List[NodoArbol]:
        """
        Devuelve todos los nodos cuyo texto contiene *fragmento* (ignorando
        mayúsculas/minúsculas).
        """
        frag = fragmento.lower()
        return [n for n in self._indice.values() if frag in n.texto.lower()]

    # ------------------------------------------------------------------ #
    # Recorridos
    # ------------------------------------------------------------------ #

    def recorrer_preorden(self) -> List[NodoArbol]:
        """
        Recorrido PREORDEN: visita la raíz antes que sus hijos.

        Orden: raíz -> hijo₁ (y su subárbol) -> hijo₂ (y su subárbol) -> …

        Complejidad: O(n)
        """
        return self._preorden_desde(self._raiz)

    def recorrer_postorden(self) -> List[NodoArbol]:
        """
        Recorrido POSTORDEN: visita los hijos antes que la raíz.

        Complejidad: O(n)
        """
        resultado: List[NodoArbol] = []
        self._postorden_rec(self._raiz, resultado)
        return resultado

    def recorrer_por_niveles(self) -> List[List[NodoArbol]]:
        """
        Recorrido POR NIVELES (BFS): devuelve una lista de listas donde
        cada sublista contiene los nodos de un mismo nivel del árbol.

        Nivel 0 -> [raíz]
        Nivel 1 -> hijos directos de la raíz
        Nivel 2 -> nietos de la raíz
        …

        Complejidad: O(n)
        """
        if not self._raiz:
            return []

        niveles: List[List[NodoArbol]] = []
        cola: deque[NodoArbol] = deque([self._raiz])

        while cola:
            nivel_actual: List[NodoArbol] = []
            for _ in range(len(cola)):
                nodo = cola.popleft()
                nivel_actual.append(nodo)
                cola.extend(nodo.hijos)
            niveles.append(nivel_actual)

        return niveles

    # ------------------------------------------------------------------ #
    # Interfaz de juego
    # ------------------------------------------------------------------ #

    def obtener_opciones(
        self,
        id_nodo_actual: str,
        estado_juego: Optional[Dict[str, Any]] = None,
    ) -> List[NodoArbol]:
        """
        Devuelve los hijos del nodo *id_nodo_actual* que estén disponibles
        según el *estado_juego*.

        Este método es el punto de integración con el motor del juego:
        Game.py lo llama para saber qué respuestas puede elegir el jugador.

        Parámetros
        ----------
        id_nodo_actual : str
            ID del nodo de diálogo donde está el jugador ahora.
        estado_juego : dict | None
            Diccionario con el estado actual: vidas, monedas, sala, etc.
            Si es None se trata como dict vacío (sin condiciones extra).

        Retorna
        -------
        list[NodoArbol] — puede ser vacío (fin de conversación).
        """
        estado = estado_juego or {}
        nodo = self._indice.get(id_nodo_actual)
        if nodo is None:
            return []
        return [hijo for hijo in nodo.hijos if hijo.esta_disponible(estado)]

    def ejecutar_efecto(
        self,
        id_nodo: str,
        estado_juego: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Aplica el efecto asociado al nodo (si existe) sobre el estado del juego.

        El efecto se guarda en ``nodo.meta["efecto"]`` como dict con claves:
          - ``"tipo"``   : "curar" | "apoyo" | "habilidad" | ...
          - ``"valor"``  : int | float (opcional)

        Retorna el dict del efecto aplicado, o None si el nodo no tiene efecto.
        """
        nodo = self._indice.get(id_nodo)
        if nodo is None:
            return None
        efecto = nodo.meta.get("efecto")
        if efecto is None:
            return None

        tipo = efecto.get("tipo")
        valor = efecto.get("valor", 0)

        if tipo == "curar":
            estado_juego["vidas"] = estado_juego.get("vidas", 0) + valor
        elif tipo == "apoyo":
            estado_juego["apoyo"] = estado_juego.get("apoyo", 0) + valor
        elif tipo == "habilidad":
            habilidades = estado_juego.setdefault("habilidades", [])
            if valor not in habilidades:
                habilidades.append(valor)

        return efecto

    # ------------------------------------------------------------------ #
    # Métricas del árbol
    # ------------------------------------------------------------------ #

    def altura(self) -> int:
        """
        Altura del árbol = número de aristas en el camino más largo
        desde la raíz hasta una hoja.

        Árbol vacío -> -1.  Árbol de un solo nodo -> 0.
        """
        return self._altura_rec(self._raiz)

    def tamaño(self) -> int:
        """Número total de nodos en el árbol."""
        return len(self._indice)

    def es_hoja(self, id: str) -> bool:
        """True si el nodo con el id dado no tiene hijos."""
        nodo = self._indice.get(id)
        return nodo is not None and nodo.es_hoja()

    def ruta_a(self, id: str) -> Optional[List[NodoArbol]]:
        """
        Devuelve la lista de nodos desde la raíz hasta el nodo con *id*,
        o None si el nodo no existe.
        """
        nodo = self._indice.get(id)
        if nodo is None:
            return None
        camino: List[NodoArbol] = []
        actual: Optional[NodoArbol] = nodo
        while actual is not None:
            camino.append(actual)
            actual = actual.padre
        camino.reverse()
        return camino

    # ------------------------------------------------------------------ #
    # Serialización básica (para guardar/cargar desde JSON en Fase 4)
    # ------------------------------------------------------------------ #

    def exportar_dict(self) -> Dict[str, Any]:
        """
        Exporta el árbol como diccionario anidado, listo para json.dumps().

        Las condiciones (funciones Python) se omiten en la serialización.
        """
        def _nodo_a_dict(n: NodoArbol) -> Dict[str, Any]:
            return {
                "id": n.id,
                "texto": n.texto,
                "meta": n.meta,
                "hijos": [_nodo_a_dict(h) for h in n.hijos],
            }
        return _nodo_a_dict(self._raiz)

    @classmethod
    def desde_dict(cls, data: Dict[str, Any]) -> "ArbolDialogo":
        """
        Reconstruye un ArbolDialogo a partir del diccionario exportado.

        Las condiciones se pierden en la serialización; los nodos
        reconstruidos tendrán condición=None (siempre disponibles).
        """
        raiz_data = data
        arbol = cls(raiz_data["id"], raiz_data["texto"], **raiz_data.get("meta", {}))
        cls._cargar_hijos(arbol, arbol.raiz, raiz_data.get("hijos", []))
        return arbol

    @staticmethod
    def _cargar_hijos(
        arbol: "ArbolDialogo",
        padre: NodoArbol,
        hijos_data: List[Dict[str, Any]],
    ) -> None:
        for h in hijos_data:
            nodo = arbol.insertar(h["id"], h["texto"], id_padre=padre.id, **h.get("meta", {}))
            ArbolDialogo._cargar_hijos(arbol, nodo, h.get("hijos", []))

    # ------------------------------------------------------------------ #
    # Utilidades / depuración
    # ------------------------------------------------------------------ #

    def imprimir_arbol(self, mostrar_meta: bool = False) -> None:
        """
        Imprime el árbol con sangría visual para facilitar la depuración.

        Ejemplo de salida::

            [alex_root] "Hola, ¿cómo te sientes?"
              ├─ [resp_bien] "Estoy bien, gracias"
              │    └─ [alex_animo] "¡Me alegra escucharlo!"
              └─ [resp_mal]  "No muy bien..."  ← condicion
        """
        self._imprimir_rec(self._raiz, "", True, mostrar_meta)

    def __repr__(self) -> str:
        return (
            f"ArbolDialogo(raiz={self._raiz.id!r}, "
            f"nodos={self.tamaño()}, altura={self.altura()})"
        )

    # ------------------------------------------------------------------ #
    # Helpers privados
    # ------------------------------------------------------------------ #

    def _preorden_desde(self, nodo: NodoArbol) -> List[NodoArbol]:
        """Preorden iterativo usando pila."""
        resultado: List[NodoArbol] = []
        pila: List[NodoArbol] = [nodo]
        while pila:
            actual = pila.pop()
            resultado.append(actual)
            for hijo in reversed(actual.hijos):
                pila.append(hijo)
        return resultado

    def _postorden_rec(self, nodo: NodoArbol, resultado: List[NodoArbol]) -> None:
        """Postorden recursivo (árboles de diálogo raramente superan 50 nodos)."""
        for hijo in nodo.hijos:
            self._postorden_rec(hijo, resultado)
        resultado.append(nodo)

    def _altura_rec(self, nodo: Optional[NodoArbol]) -> int:
        if nodo is None:
            return -1
        if nodo.es_hoja():
            return 0
        return 1 + max(self._altura_rec(h) for h in nodo.hijos)

    def _imprimir_rec(
        self,
        nodo: NodoArbol,
        prefijo: str,
        es_ultimo: bool,
        mostrar_meta: bool,
    ) -> None:
        conector = "+- " if es_ultimo else "|- "
        cond_tag = "  [condicion]" if nodo.condicion else ""
        meta_str = f"  {nodo.meta}" if (mostrar_meta and nodo.meta) else ""
        print(f"{prefijo}{conector}[{nodo.id}] {nodo.texto!r}{cond_tag}{meta_str}")
        extension = "   " if es_ultimo else "|  "
        for i, hijo in enumerate(nodo.hijos):
            self._imprimir_rec(
                hijo,
                prefijo + extension,
                i == len(nodo.hijos) - 1,
                mostrar_meta,
            )


# ---------------------------------------------------------------------------
# Árbol de diálogos de Alex (instancia precargada para Fase 2)
# ---------------------------------------------------------------------------

def construir_arbol_alex() -> ArbolDialogo:
    """
    Construye el árbol de diálogos del NPC aliado «Alex» para la demo de Fase 2.

    Estructura de la conversación:
    ┌─ alex_root: "Hola, sobreviviente. ¿Cómo te encuentras?"
    ├─ resp_bien  (sin condición): "Estoy resistiendo."
    │   └─ alex_animo: "Cada paso cuenta. Te doy algo de apoyo."  [efecto: +10 apoyo]
    ├─ resp_mal   (sin condición): "Me siento solo/a..."
    │   ├─ alex_empatia: "Estoy aquí contigo. No estás solo/a."
    │   │   └─ alex_curar: "Toma, esto te ayudará a recuperarte."  [efecto: +1 vida]
    │   └─ alex_consejo: "Recuerda: puedes bloquear y reportar."
    └─ resp_arma  (condición: tiene arma 'evidencia'): "¿Cómo uso la evidencia?"
        └─ alex_arma: "Captura capturas de pantalla. La verdad es tu escudo."
    """
    arbol = ArbolDialogo(
        "alex_root",
        "Hola, sobreviviente. ¿Cómo te encuentras?",
        emocion="neutral",
        sprite="alex_idle",
    )

    # --- Rama 1: jugador en buen estado ---
    arbol.insertar(
        "resp_bien",
        "Estoy resistiendo.",
        id_padre="alex_root",
        emocion="jugador",
    )
    arbol.insertar(
        "alex_animo",
        "Cada paso cuenta. Aquí tienes algo de apoyo extra.",
        id_padre="resp_bien",
        emocion="alegre",
        sprite="alex_smile",
        efecto={"tipo": "apoyo", "valor": 10},
    )

    # --- Rama 2: jugador se siente solo ---
    arbol.insertar(
        "resp_mal",
        "Me siento solo/a...",
        id_padre="alex_root",
        emocion="jugador",
    )
    arbol.insertar(
        "alex_empatia",
        "Estoy aquí contigo. No estás solo/a en esto.",
        id_padre="resp_mal",
        emocion="empático",
        sprite="alex_concerned",
    )
    arbol.insertar(
        "alex_curar",
        "Toma, esto te ayudará a recuperarte un poco.",
        id_padre="alex_empatia",
        emocion="cálido",
        sprite="alex_give",
        efecto={"tipo": "curar", "valor": 1},
    )
    arbol.insertar(
        "alex_consejo",
        "Recuerda que tienes herramientas: puedes bloquear y reportar.",
        id_padre="resp_mal",
        emocion="serio",
        sprite="alex_point",
    )

    # --- Rama 3: pregunta sobre arma (bloqueada hasta tenerla) ---
    arbol.insertar(
        "resp_arma",
        "¿Cómo uso la 'Evidencia' que encontré?",
        id_padre="alex_root",
        emocion="jugador",
        condicion=lambda estado: "evidencia" in estado.get("armas", []),
    )
    arbol.insertar(
        "alex_arma",
        "Captura pantallas de los mensajes. La verdad documentada es tu escudo más poderoso.",
        id_padre="resp_arma",
        emocion="convencido",
        sprite="alex_explain",
    )

    return arbol
