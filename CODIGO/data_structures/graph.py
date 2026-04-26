"""
data_structures/graph.py
========================
Grafo genérico implementado con LISTA DE ADYACENCIA.

Características académicas (Fase 2 — EDD 2, UniNorte):
  - Soporta grafos dirigidos y NO dirigidos.
  - Cada nodo puede almacenar datos adicionales (metadata).
  - Cada arista tiene un peso flotante (por defecto 1.0).
  - Algoritmos incluidos:
      * BFS  (recorrido en anchura)
      * DFS  (recorrido en profundidad — iterativo con pila)
      * bfs_con_distancias  → dict{nodo: distancia_entera}
      * camino_mas_corto    → Dijkstra con heapq (sin librerías externas)
      * es_conexo           → verifica si el grafo es conexo
      * hay_camino          → decide si existe ruta entre dos nodos
      * componentes_conexas → lista de componentes (BFS por componente)

Uso en el proyecto:
  - world/Dungeon.py instancia un Grafo para representar la red de salas
    y delega el cálculo del mapa de profundidades a bfs_con_distancias().
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import Any, Dict, Generator, Hashable, Iterable, List, Optional, Tuple

# Tipo alias para mayor legibilidad
Nodo = Hashable
Peso = float


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class Grafo:
    """
    Grafo ponderado representado como lista de adyacencia.

    Parámetros
    ----------
    dirigido : bool
        Si True, agregar_arista(u, v) crea una arista unidireccional u→v.
        Si False (por defecto), crea aristas en ambas direcciones.

    Estructura interna
    ------------------
    _nodos : dict[Nodo, dict]
        Metadatos asociados a cada nodo (color, tipo, etc.).
    _adyacencia : dict[Nodo, list[tuple[Nodo, Peso]]]
        Vecinos de cada nodo con su peso de arista.
    """

    def __init__(self, dirigido: bool = False) -> None:
        self._dirigido: bool = dirigido
        self._nodos: Dict[Nodo, Dict[str, Any]] = {}
        self._adyacencia: Dict[Nodo, List[Tuple[Nodo, Peso]]] = {}

    # ------------------------------------------------------------------ #
    # Propiedades básicas
    # ------------------------------------------------------------------ #

    @property
    def dirigido(self) -> bool:
        return self._dirigido

    @property
    def num_nodos(self) -> int:
        return len(self._nodos)

    @property
    def num_aristas(self) -> int:
        total = sum(len(vecinos) for vecinos in self._adyacencia.values())
        return total if self._dirigido else total // 2

    # ------------------------------------------------------------------ #
    # Modificación del grafo
    # ------------------------------------------------------------------ #

    def agregar_nodo(self, nodo: Nodo, **datos: Any) -> None:
        """
        Añade un nodo al grafo con metadatos opcionales.

        Si el nodo ya existe sus datos se actualizan (no se sobreescribe
        la lista de adyacencia).

        Ejemplo
        -------
        >>> g.agregar_nodo((2, 3), tipo="shop", profundidad=4)
        """
        if nodo not in self._nodos:
            self._nodos[nodo] = {}
            self._adyacencia[nodo] = []
        self._nodos[nodo].update(datos)

    def agregar_arista(
        self,
        origen: Nodo,
        destino: Nodo,
        peso: Peso = 1.0,
    ) -> None:
        """
        Añade una arista entre *origen* y *destino*.

        Si alguno de los nodos no existe se crea automáticamente.
        En grafos no dirigidos se añade también la arista inversa.

        Parámetros
        ----------
        origen, destino : Nodo
            Extremos de la arista.
        peso : float
            Costo de atravesar esta arista (1.0 por defecto).
        """
        # Asegurar que ambos nodos existen
        if origen not in self._nodos:
            self.agregar_nodo(origen)
        if destino not in self._nodos:
            self.agregar_nodo(destino)

        # Evitar aristas duplicadas: si ya existe se actualiza el peso
        self._actualizar_o_agregar(self._adyacencia[origen], destino, peso)

        if not self._dirigido:
            self._actualizar_o_agregar(self._adyacencia[destino], origen, peso)

    def eliminar_nodo(self, nodo: Nodo) -> None:
        """Elimina un nodo y todas las aristas que lo involucran."""
        if nodo not in self._nodos:
            return
        del self._nodos[nodo]
        del self._adyacencia[nodo]
        # Quitar referencias en otros nodos
        for vecinos in self._adyacencia.values():
            vecinos[:] = [(v, p) for v, p in vecinos if v != nodo]

    def eliminar_arista(self, origen: Nodo, destino: Nodo) -> None:
        """Elimina la arista origen→destino (y destino→origen si es no dirigido)."""
        if origen in self._adyacencia:
            self._adyacencia[origen] = [
                (v, p) for v, p in self._adyacencia[origen] if v != destino
            ]
        if not self._dirigido and destino in self._adyacencia:
            self._adyacencia[destino] = [
                (v, p) for v, p in self._adyacencia[destino] if v != origen
            ]

    # ------------------------------------------------------------------ #
    # Consultas básicas
    # ------------------------------------------------------------------ #

    def nodos(self) -> List[Nodo]:
        """Devuelve la lista de todos los nodos."""
        return list(self._nodos.keys())

    def vecinos(self, nodo: Nodo) -> List[Tuple[Nodo, Peso]]:
        """
        Devuelve los vecinos de *nodo* como lista de (vecino, peso).

        Ejemplo
        -------
        >>> g.vecinos((0, 0))
        [((1, 0), 1.0), ((0, 1), 1.0)]
        """
        return list(self._adyacencia.get(nodo, []))

    def datos_nodo(self, nodo: Nodo) -> Dict[str, Any]:
        """Devuelve el diccionario de metadatos del nodo."""
        return dict(self._nodos.get(nodo, {}))

    def grado(self, nodo: Nodo) -> int:
        """
        Grado del nodo (número de aristas que lo conectan).

        En grafos dirigidos devuelve el grado de salida (out-degree).
        """
        return len(self._adyacencia.get(nodo, []))

    def tiene_nodo(self, nodo: Nodo) -> bool:
        return nodo in self._nodos

    def tiene_arista(self, origen: Nodo, destino: Nodo) -> bool:
        return any(v == destino for v, _ in self._adyacencia.get(origen, []))

    # ------------------------------------------------------------------ #
    # Recorridos
    # ------------------------------------------------------------------ #

    def bfs(self, inicio: Nodo) -> List[Nodo]:
        """
        Recorrido en ANCHURA (Breadth-First Search).

        Devuelve la lista de nodos en el orden en que son visitados.
        Si *inicio* no pertenece al grafo devuelve lista vacía.

        Complejidad: O(V + E)
        """
        if inicio not in self._nodos:
            return []

        visitados: Dict[Nodo, bool] = {}
        cola: deque[Nodo] = deque([inicio])
        visitados[inicio] = True
        orden: List[Nodo] = []

        while cola:
            nodo = cola.popleft()
            orden.append(nodo)
            for vecino, _ in self._adyacencia[nodo]:
                if vecino not in visitados:
                    visitados[vecino] = True
                    cola.append(vecino)

        return orden

    def dfs(self, inicio: Nodo) -> List[Nodo]:
        """
        Recorrido en PROFUNDIDAD (Depth-First Search) — versión iterativa.

        Devuelve la lista de nodos en el orden en que son visitados.
        Si *inicio* no pertenece al grafo devuelve lista vacía.

        Complejidad: O(V + E)
        """
        if inicio not in self._nodos:
            return []

        visitados: Dict[Nodo, bool] = {}
        pila: List[Nodo] = [inicio]
        orden: List[Nodo] = []

        while pila:
            nodo = pila.pop()
            if nodo in visitados:
                continue
            visitados[nodo] = True
            orden.append(nodo)
            # Invertimos para mantener el orden "izquierda-primero"
            for vecino, _ in reversed(self._adyacencia[nodo]):
                if vecino not in visitados:
                    pila.append(vecino)

        return orden

    def bfs_con_distancias(self, inicio: Nodo) -> Dict[Nodo, int]:
        """
        BFS que devuelve la distancia mínima (en saltos) desde *inicio*
        hasta cada nodo alcanzable.

        Útil para calcular el mapa de profundidad de salas en el dungeon.

        Retorna
        -------
        dict[Nodo, int]
            Nodos no alcanzables NO aparecen en el diccionario.

        Complejidad: O(V + E)
        """
        if inicio not in self._nodos:
            return {}

        distancias: Dict[Nodo, int] = {inicio: 0}
        cola: deque[Nodo] = deque([inicio])

        while cola:
            nodo = cola.popleft()
            dist_actual = distancias[nodo]
            for vecino, _ in self._adyacencia[nodo]:
                if vecino not in distancias:
                    distancias[vecino] = dist_actual + 1
                    cola.append(vecino)

        return distancias

    # ------------------------------------------------------------------ #
    # Camino más corto — Dijkstra
    # ------------------------------------------------------------------ #

    def camino_mas_corto(
        self,
        origen: Nodo,
        destino: Nodo,
    ) -> Optional[Tuple[List[Nodo], Peso]]:
        """
        Algoritmo de DIJKSTRA para camino de menor costo.

        No usa librerías externas; emplea ``heapq`` de la biblioteca estándar.

        Parámetros
        ----------
        origen, destino : Nodo
            Nodos de inicio y fin de la ruta.

        Retorna
        -------
        (camino, costo_total) si existe ruta, o None si no hay conexión.

        Ejemplo
        -------
        >>> resultado = g.camino_mas_corto((0,0), (3,3))
        >>> if resultado:
        ...     camino, costo = resultado
        ...     print(camino, costo)

        Complejidad: O((V + E) log V)
        """
        if origen not in self._nodos or destino not in self._nodos:
            return None

        # dist[nodo] = costo mínimo conocido desde origen
        dist: Dict[Nodo, Peso] = {origen: 0.0}
        previo: Dict[Nodo, Optional[Nodo]] = {origen: None}

        # Montículo mínimo: (costo_acumulado, nodo)
        heap: List[Tuple[Peso, Any]] = [(0.0, origen)]

        while heap:
            costo_actual, nodo = heapq.heappop(heap)

            # Si ya encontramos el destino, reconstruimos el camino
            if nodo == destino:
                return self._reconstruir_camino(previo, origen, destino), costo_actual

            # Descartamos entradas obsoletas del heap
            if costo_actual > dist.get(nodo, float("inf")):
                continue

            for vecino, peso in self._adyacencia[nodo]:
                nuevo_costo = costo_actual + peso
                if nuevo_costo < dist.get(vecino, float("inf")):
                    dist[vecino] = nuevo_costo
                    previo[vecino] = nodo
                    heapq.heappush(heap, (nuevo_costo, vecino))

        return None  # sin ruta

    def distancias_dijkstra(self, origen: Nodo) -> Dict[Nodo, Peso]:
        """
        Dijkstra desde *origen* hacia TODOS los nodos alcanzables.

        Útil cuando se necesita el costo exacto (pesos variables) a
        todos los destinos, no sólo el número de saltos.

        Retorna
        -------
        dict[Nodo, float] — nodos inalcanzables tienen inf implícito.
        """
        if origen not in self._nodos:
            return {}

        dist: Dict[Nodo, Peso] = {origen: 0.0}
        heap: List[Tuple[Peso, Any]] = [(0.0, origen)]

        while heap:
            costo_actual, nodo = heapq.heappop(heap)
            if costo_actual > dist.get(nodo, float("inf")):
                continue
            for vecino, peso in self._adyacencia[nodo]:
                nuevo_costo = costo_actual + peso
                if nuevo_costo < dist.get(vecino, float("inf")):
                    dist[vecino] = nuevo_costo
                    heapq.heappush(heap, (nuevo_costo, vecino))

        return dist

    # ------------------------------------------------------------------ #
    # Análisis estructural
    # ------------------------------------------------------------------ #

    def es_conexo(self) -> bool:
        """
        Verifica si el grafo es CONEXO (todos los nodos se alcanzan entre sí).

        Para grafos dirigidos comprueba la conectividad débil (ignora sentido).

        Retorna True si el grafo está vacío (vacuamente conexo).
        """
        if not self._nodos:
            return True
        inicio = next(iter(self._nodos))
        alcanzados = self.bfs(inicio)
        return len(alcanzados) == len(self._nodos)

    def hay_camino(self, origen: Nodo, destino: Nodo) -> bool:
        """
        Devuelve True si existe al menos un camino entre *origen* y *destino*.

        Implementación: BFS limitado — se detiene al encontrar el destino.
        """
        if origen not in self._nodos or destino not in self._nodos:
            return False
        if origen == destino:
            return True

        visitados: Dict[Nodo, bool] = {origen: True}
        cola: deque[Nodo] = deque([origen])

        while cola:
            nodo = cola.popleft()
            for vecino, _ in self._adyacencia[nodo]:
                if vecino == destino:
                    return True
                if vecino not in visitados:
                    visitados[vecino] = True
                    cola.append(vecino)

        return False

    def componentes_conexas(self) -> List[List[Nodo]]:
        """
        Devuelve la lista de componentes conexas del grafo.

        Cada componente es una lista de nodos que se alcanzan entre sí.
        En grafos dirigidos opera sobre la versión no dirigida (conectividad débil).
        """
        visitados: Dict[Nodo, bool] = {}
        componentes: List[List[Nodo]] = []

        for nodo in self._nodos:
            if nodo not in visitados:
                componente = self._bfs_componente(nodo, visitados)
                componentes.append(componente)

        return componentes

    # ------------------------------------------------------------------ #
    # Utilidades / depuración
    # ------------------------------------------------------------------ #

    def imprimir_lista_adyacencia(self) -> None:
        """
        Imprime la lista de adyacencia en formato legible.

        Ejemplo de salida::

            (0,0)  →  [(1,0):1.0]  [(0,1):1.0]
            (1,0)  →  [(0,0):1.0]  [(1,1):1.0]
        """
        for nodo in sorted(self._nodos, key=str):
            vecinos_str = "  ".join(
                f"[{v}:{p:.1f}]" for v, p in self._adyacencia[nodo]
            )
            print(f"  {nodo!s:<18}->  {vecinos_str}")

    def resumen(self) -> str:
        """Cadena de una línea con estadísticas del grafo."""
        tipo = "Dirigido" if self._dirigido else "No dirigido"
        return (
            f"Grafo {tipo} | "
            f"Nodos: {self.num_nodos} | "
            f"Aristas: {self.num_aristas} | "
            f"Conexo: {self.es_conexo()}"
        )

    # ------------------------------------------------------------------ #
    # Métodos privados de apoyo
    # ------------------------------------------------------------------ #

    @staticmethod
    def _actualizar_o_agregar(
        lista: List[Tuple[Nodo, Peso]],
        destino: Nodo,
        peso: Peso,
    ) -> None:
        """Actualiza el peso si ya existe la arista; si no, la añade."""
        for i, (v, _) in enumerate(lista):
            if v == destino:
                lista[i] = (destino, peso)
                return
        lista.append((destino, peso))

    @staticmethod
    def _reconstruir_camino(
        previo: Dict[Nodo, Optional[Nodo]],
        origen: Nodo,
        destino: Nodo,
    ) -> List[Nodo]:
        """Recorre el dict *previo* hacia atrás para obtener la ruta."""
        camino: List[Nodo] = []
        actual: Optional[Nodo] = destino
        while actual is not None:
            camino.append(actual)
            actual = previo.get(actual)
        camino.reverse()
        return camino

    def _bfs_componente(
        self,
        inicio: Nodo,
        visitados: Dict[Nodo, bool],
    ) -> List[Nodo]:
        """BFS interno que respeta el conjunto global de visitados."""
        cola: deque[Nodo] = deque([inicio])
        visitados[inicio] = True
        componente: List[Nodo] = []

        while cola:
            nodo = cola.popleft()
            componente.append(nodo)
            # Para conectividad débil en grafos dirigidos también miramos
            # la dirección inversa; en no dirigidos ya está en adyacencia.
            vecinos_efectivos = list(self._adyacencia[nodo])
            if self._dirigido:
                for otro, adj in self._adyacencia.items():
                    if any(v == nodo for v, _ in adj):
                        vecinos_efectivos.append((otro, 0.0))

            for vecino, _ in vecinos_efectivos:
                if vecino not in visitados:
                    visitados[vecino] = True
                    cola.append(vecino)

        return componente

    # ------------------------------------------------------------------ #
    # Protocolo Python estándar
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return self.num_nodos

    def __contains__(self, nodo: object) -> bool:
        return nodo in self._nodos

    def __repr__(self) -> str:
        return (
            f"Grafo(dirigido={self._dirigido}, "
            f"nodos={self.num_nodos}, aristas={self.num_aristas})"
        )
