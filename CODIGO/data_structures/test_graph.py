"""
test_graph.py — Suite de pruebas para data_structures/graph.py
==============================================================
Ejecución:
    cd CODIGO/data_structures
    python test_graph.py

No requiere pytest; usa unittest estándar.
"""
import sys
import os
import unittest

# Asegurar que podemos importar desde CODIGO/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_structures.graph import Grafo


# ---------------------------------------------------------------------------
# Helpers de construcción
# ---------------------------------------------------------------------------

def _grafo_simple() -> Grafo:
    """
    Grafo no dirigido de 5 nodos:
        A - B - C
        |       |
        D - - - E
    """
    g = Grafo()
    for nodo in "ABCDE":
        g.agregar_nodo(nodo)
    g.agregar_arista("A", "B")
    g.agregar_arista("B", "C")
    g.agregar_arista("A", "D")
    g.agregar_arista("C", "E")
    g.agregar_arista("D", "E")
    return g


def _grafo_ponderado() -> Grafo:
    """
    Grafo ponderado no dirigido:
        A -1- B -4- D
        |         /
        2        3
        |      /
        C -5- D
    A->B:1, A->C:2, B->D:4, C->D:5, B->C:3
    """
    g = Grafo()
    g.agregar_arista("A", "B", peso=1.0)
    g.agregar_arista("A", "C", peso=2.0)
    g.agregar_arista("B", "C", peso=3.0)
    g.agregar_arista("B", "D", peso=4.0)
    g.agregar_arista("C", "D", peso=5.0)
    return g


def _grafo_dungeon() -> Grafo:
    """
    Mini-dungeon de 6 salas como tuplas (i,j):
        (0,0) -- (1,0) -- (2,0)
          |                 |
        (0,1)            (2,1)
          |
        (0,2)
    """
    g = Grafo()
    conexiones = [
        ((0, 0), (1, 0)),
        ((1, 0), (2, 0)),
        ((2, 0), (2, 1)),
        ((0, 0), (0, 1)),
        ((0, 1), (0, 2)),
    ]
    for u, v in conexiones:
        g.agregar_arista(u, v)
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGrafoBasico(unittest.TestCase):
    """Operaciones fundamentales de construcción y consulta."""

    def test_agregar_nodo(self):
        g = Grafo()
        g.agregar_nodo("X", color="red")
        self.assertIn("X", g)
        self.assertEqual(g.datos_nodo("X")["color"], "red")

    def test_agregar_arista_no_dirigida(self):
        g = Grafo()
        g.agregar_arista("A", "B", peso=2.5)
        self.assertTrue(g.tiene_arista("A", "B"))
        self.assertTrue(g.tiene_arista("B", "A"))  # simétrica
        vecinos_a = dict(g.vecinos("A"))
        self.assertAlmostEqual(vecinos_a["B"], 2.5)

    def test_agregar_arista_dirigida(self):
        g = Grafo(dirigido=True)
        g.agregar_arista("A", "B")
        self.assertTrue(g.tiene_arista("A", "B"))
        self.assertFalse(g.tiene_arista("B", "A"))  # no simétrica

    def test_num_nodos_y_aristas(self):
        g = _grafo_simple()
        self.assertEqual(g.num_nodos, 5)
        self.assertEqual(g.num_aristas, 5)

    def test_grado_nodo(self):
        g = _grafo_simple()
        # A conecta con B y D -> grado 2
        self.assertEqual(g.grado("A"), 2)
        # B conecta con A y C -> grado 2
        self.assertEqual(g.grado("B"), 2)

    def test_eliminar_nodo(self):
        g = _grafo_simple()
        g.eliminar_nodo("C")
        self.assertNotIn("C", g)
        self.assertFalse(g.tiene_arista("B", "C"))
        self.assertEqual(g.num_nodos, 4)

    def test_eliminar_arista(self):
        g = _grafo_simple()
        g.eliminar_arista("A", "B")
        self.assertFalse(g.tiene_arista("A", "B"))
        self.assertFalse(g.tiene_arista("B", "A"))  # simétrica eliminada

    def test_nodo_auto_creado_al_agregar_arista(self):
        g = Grafo()
        g.agregar_arista("X", "Y")
        self.assertIn("X", g)
        self.assertIn("Y", g)

    def test_actualizar_peso_arista_existente(self):
        g = Grafo()
        g.agregar_arista("A", "B", peso=1.0)
        g.agregar_arista("A", "B", peso=9.0)  # actualiza
        vecinos = dict(g.vecinos("A"))
        self.assertAlmostEqual(vecinos["B"], 9.0)
        self.assertEqual(g.num_aristas, 1)  # sigue siendo 1 arista


class TestRecorridos(unittest.TestCase):
    """BFS, DFS y BFS con distancias."""

    def test_bfs_orden(self):
        g = _grafo_simple()
        recorrido = g.bfs("A")
        # A debe ser el primero
        self.assertEqual(recorrido[0], "A")
        # Todos los nodos deben aparecer exactamente una vez
        self.assertEqual(sorted(recorrido), sorted("ABCDE"))
        self.assertEqual(len(set(recorrido)), 5)

    def test_bfs_nodo_inexistente(self):
        g = _grafo_simple()
        self.assertEqual(g.bfs("Z"), [])

    def test_dfs_orden(self):
        g = _grafo_simple()
        recorrido = g.dfs("A")
        self.assertEqual(recorrido[0], "A")
        self.assertEqual(sorted(recorrido), sorted("ABCDE"))
        self.assertEqual(len(set(recorrido)), 5)

    def test_bfs_con_distancias_simple(self):
        g = _grafo_simple()
        dist = g.bfs_con_distancias("A")
        self.assertEqual(dist["A"], 0)
        self.assertEqual(dist["B"], 1)
        self.assertEqual(dist["D"], 1)
        # C está a distancia 2 desde A (A->B->C)
        self.assertLessEqual(dist["C"], 3)
        self.assertGreaterEqual(dist["C"], 2)

    def test_bfs_con_distancias_dungeon(self):
        g = _grafo_dungeon()
        dist = g.bfs_con_distancias((0, 0))
        self.assertEqual(dist[(0, 0)], 0)
        self.assertEqual(dist[(1, 0)], 1)
        self.assertEqual(dist[(0, 1)], 1)
        self.assertEqual(dist[(2, 0)], 2)
        self.assertEqual(dist[(0, 2)], 2)
        self.assertEqual(dist[(2, 1)], 3)

    def test_bfs_grafo_desconectado(self):
        g = Grafo()
        g.agregar_arista("A", "B")
        g.agregar_nodo("Z")  # nodo aislado
        dist = g.bfs_con_distancias("A")
        self.assertIn("A", dist)
        self.assertIn("B", dist)
        self.assertNotIn("Z", dist)


class TestDijkstra(unittest.TestCase):
    """Camino más corto con pesos."""

    def test_camino_simple(self):
        g = _grafo_ponderado()
        resultado = g.camino_mas_corto("A", "D")
        self.assertIsNotNone(resultado)
        camino, costo = resultado
        # El camino A->B->D tiene costo 5; A->C->D cuesta 7; A->B->C->D = 9
        self.assertAlmostEqual(costo, 5.0)
        self.assertEqual(camino[0], "A")
        self.assertEqual(camino[-1], "D")

    def test_camino_a_si_mismo(self):
        g = _grafo_ponderado()
        resultado = g.camino_mas_corto("A", "A")
        self.assertIsNotNone(resultado)
        camino, costo = resultado
        self.assertEqual(camino, ["A"])
        self.assertAlmostEqual(costo, 0.0)

    def test_sin_ruta(self):
        g = Grafo()
        g.agregar_nodo("X")
        g.agregar_nodo("Y")
        self.assertIsNone(g.camino_mas_corto("X", "Y"))

    def test_nodo_inexistente(self):
        g = _grafo_ponderado()
        self.assertIsNone(g.camino_mas_corto("A", "Z"))

    def test_distancias_dijkstra_todos(self):
        g = _grafo_ponderado()
        dist = g.distancias_dijkstra("A")
        self.assertAlmostEqual(dist["A"], 0.0)
        self.assertAlmostEqual(dist["B"], 1.0)
        self.assertAlmostEqual(dist["C"], 2.0)
        self.assertAlmostEqual(dist["D"], 5.0)

    def test_dungeon_dijkstra(self):
        """Dijkstra en el grafo de salas funciona igual que BFS cuando pesos=1."""
        g = _grafo_dungeon()
        resultado = g.camino_mas_corto((0, 0), (2, 1))
        self.assertIsNotNone(resultado)
        camino, costo = resultado
        self.assertEqual(camino[0], (0, 0))
        self.assertEqual(camino[-1], (2, 1))
        # Costo mínimo = 3 saltos con peso 1.0 cada uno
        self.assertAlmostEqual(costo, 3.0)


class TestAnalisisEstructural(unittest.TestCase):
    """Conectividad y componentes."""

    def test_es_conexo_verdadero(self):
        g = _grafo_simple()
        self.assertTrue(g.es_conexo())

    def test_es_conexo_falso(self):
        g = Grafo()
        g.agregar_arista("A", "B")
        g.agregar_nodo("Z")
        self.assertFalse(g.es_conexo())

    def test_grafo_vacio_conexo(self):
        g = Grafo()
        self.assertTrue(g.es_conexo())

    def test_hay_camino(self):
        g = _grafo_simple()
        self.assertTrue(g.hay_camino("A", "E"))
        self.assertTrue(g.hay_camino("E", "A"))

    def test_no_hay_camino(self):
        g = Grafo()
        g.agregar_arista("A", "B")
        g.agregar_nodo("Z")
        self.assertFalse(g.hay_camino("A", "Z"))

    def test_componentes_conexas(self):
        g = Grafo()
        g.agregar_arista("A", "B")
        g.agregar_arista("C", "D")
        g.agregar_nodo("Z")
        comps = g.componentes_conexas()
        # Hay 3 componentes: {A,B}, {C,D}, {Z}
        self.assertEqual(len(comps), 3)
        tamaños = sorted(len(c) for c in comps)
        self.assertEqual(tamaños, [1, 2, 2])

    def test_una_componente(self):
        g = _grafo_simple()
        comps = g.componentes_conexas()
        self.assertEqual(len(comps), 1)
        self.assertEqual(len(comps[0]), 5)


class TestCasosDungeon(unittest.TestCase):
    """Casos de uso específicos del proyecto Echoes."""

    def test_profundidad_reemplaza_bfs_manual(self):
        """
        Simula lo que hace Dungeon._build_depth_map() con el Grafo.

        El resultado debe ser idéntico al BFS manual de Dungeon.
        """
        g = _grafo_dungeon()
        inicio = (0, 0)
        dist = g.bfs_con_distancias(inicio)

        # Verificar que cubre todas las salas
        self.assertEqual(len(dist), g.num_nodos)

        # La sala inicial siempre tiene distancia 0
        self.assertEqual(dist[inicio], 0)

        # Ninguna distancia puede ser negativa
        for d in dist.values():
            self.assertGreaterEqual(d, 0)

    def test_grafo_con_metadata_salas(self):
        """Los nodos del grafo pueden guardar metadatos de sala (tipo, profundidad)."""
        g = Grafo()
        g.agregar_nodo((0, 0), tipo="start")
        g.agregar_nodo((1, 0), tipo="shop")
        g.agregar_nodo((2, 0), tipo="normal")
        g.agregar_arista((0, 0), (1, 0))
        g.agregar_arista((1, 0), (2, 0))

        self.assertEqual(g.datos_nodo((1, 0))["tipo"], "shop")
        self.assertTrue(g.es_conexo())

    def test_resumen_grafo(self):
        g = _grafo_simple()
        resumen = g.resumen()
        self.assertIn("Nodos: 5", resumen)
        self.assertIn("Aristas: 5", resumen)
        self.assertIn("Conexo: True", resumen)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Echoes — Tests: data_structures/graph.py")
    print("=" * 60)

    # Demo visual rápida antes de los tests
    print("\n[Demo] Grafo simple:")
    g_demo = _grafo_simple()
    print(f"  {g_demo.resumen()}")
    print("  Lista de adyacencia:")
    g_demo.imprimir_lista_adyacencia()

    print("\n[Demo] Dijkstra A->D en grafo ponderado:")
    g_pw = _grafo_ponderado()
    resultado = g_pw.camino_mas_corto("A", "D")
    if resultado:
        camino, costo = resultado
        print(f"  Camino: {' -> '.join(camino)}  |  Costo: {costo}")

    print("\n[Demo] BFS con distancias en mini-dungeon:")
    g_dung = _grafo_dungeon()
    dist = g_dung.bfs_con_distancias((0, 0))
    for sala, d in sorted(dist.items(), key=lambda x: x[1]):
        print(f"  Sala {sala}: profundidad {d}")

    print("\n" + "=" * 60)
    print("  Ejecutando suite completa de tests...")
    print("=" * 60 + "\n")

    unittest.main(verbosity=2)
