"""
data_structures — Estructuras de datos académicas (Fase 2, EDD 2 UniNorte)
==========================================================================

Módulos disponibles:
  graph.py  — Grafo genérico ponderado (BFS, DFS, Dijkstra)
  tree.py   — Árbol N-ario de diálogos para el NPC aliado «Alex»

Importación rápida::

    from data_structures.graph import Grafo
    from data_structures.tree  import ArbolDialogo, construir_arbol_alex
"""

from data_structures.graph import Grafo
from data_structures.tree import ArbolDialogo, NodoArbol, construir_arbol_alex

__all__ = [
    "Grafo",
    "ArbolDialogo",
    "NodoArbol",
    "construir_arbol_alex",
]
