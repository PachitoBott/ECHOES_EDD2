"""
test_tree.py — Suite de pruebas para data_structures/tree.py
============================================================
Ejecución:
    cd CODIGO/data_structures
    python test_tree.py

No requiere pytest; usa unittest estándar.
"""
import sys
import os
import unittest

# Asegurar que podemos importar desde CODIGO/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_structures.tree import ArbolDialogo, NodoArbol, construir_arbol_alex


# ---------------------------------------------------------------------------
# Helpers de construcción
# ---------------------------------------------------------------------------

def _arbol_simple() -> ArbolDialogo:
    """
    Árbol de 7 nodos:
        raiz
        ├── hijo_a
        │   ├── nieto_a1
        │   └── nieto_a2
        └── hijo_b
            └── nieto_b1
                └── biznieto_b1
    """
    arbol = ArbolDialogo("raiz", "Texto raíz")
    arbol.insertar("hijo_a", "Hijo A", id_padre="raiz")
    arbol.insertar("hijo_b", "Hijo B", id_padre="raiz")
    arbol.insertar("nieto_a1", "Nieto A1", id_padre="hijo_a")
    arbol.insertar("nieto_a2", "Nieto A2", id_padre="hijo_a")
    arbol.insertar("nieto_b1", "Nieto B1", id_padre="hijo_b")
    arbol.insertar("biznieto_b1", "Biznieto B1", id_padre="nieto_b1")
    return arbol


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNodoArbol(unittest.TestCase):
    """Pruebas unitarias del NodoArbol."""

    def test_creacion_basica(self):
        nodo = NodoArbol("n1", "Texto de prueba", color="blue")
        self.assertEqual(nodo.id, "n1")
        self.assertEqual(nodo.texto, "Texto de prueba")
        self.assertEqual(nodo.meta["color"], "blue")
        self.assertIsNone(nodo.padre)
        self.assertEqual(nodo.hijos, [])

    def test_agregar_hijo_vincula_padre(self):
        padre = NodoArbol("p", "Padre")
        hijo = NodoArbol("h", "Hijo")
        padre.agregar_hijo(hijo)
        self.assertIn(hijo, padre.hijos)
        self.assertIs(hijo.padre, padre)

    def test_quitar_hijo(self):
        padre = NodoArbol("p", "Padre")
        hijo = NodoArbol("h", "Hijo")
        padre.agregar_hijo(hijo)
        resultado = padre.quitar_hijo("h")
        self.assertTrue(resultado)
        self.assertNotIn(hijo, padre.hijos)
        self.assertIsNone(hijo.padre)

    def test_es_hoja(self):
        nodo = NodoArbol("n", "Texto")
        self.assertTrue(nodo.es_hoja())
        nodo.agregar_hijo(NodoArbol("h", "hijo"))
        self.assertFalse(nodo.es_hoja())

    def test_condicion_none_siempre_disponible(self):
        nodo = NodoArbol("n", "T")
        self.assertTrue(nodo.esta_disponible({}))
        self.assertTrue(nodo.esta_disponible({"armas": []}))

    def test_condicion_personalizada(self):
        nodo = NodoArbol(
            "n", "T",
            condicion=lambda estado: estado.get("vidas", 0) >= 3
        )
        self.assertFalse(nodo.esta_disponible({"vidas": 1}))
        self.assertTrue(nodo.esta_disponible({"vidas": 5}))

    def test_condicion_error_oculta_opcion(self):
        """Si la condición lanza excepción, el nodo se oculta (retorna False)."""
        nodo = NodoArbol("n", "T", condicion=lambda e: e["clave_inexistente"])
        self.assertFalse(nodo.esta_disponible({}))

    def test_profundidad(self):
        arbol = _arbol_simple()
        raiz = arbol.buscar("raiz")
        hijo_a = arbol.buscar("hijo_a")
        nieto_a1 = arbol.buscar("nieto_a1")
        biznieto = arbol.buscar("biznieto_b1")
        self.assertEqual(raiz.profundidad(), 0)
        self.assertEqual(hijo_a.profundidad(), 1)
        self.assertEqual(nieto_a1.profundidad(), 2)
        self.assertEqual(biznieto.profundidad(), 3)


class TestArbolDialogoModificacion(unittest.TestCase):
    """Inserción, eliminación y consultas básicas."""

    def test_raiz_disponible_al_crear(self):
        arbol = ArbolDialogo("r", "Raíz")
        self.assertIsNotNone(arbol.buscar("r"))
        self.assertEqual(arbol.tamaño(), 1)

    def test_insertar_hijo_de_raiz(self):
        arbol = ArbolDialogo("r", "Raíz")
        arbol.insertar("h1", "Hijo 1")  # id_padre=None -> hijo de raíz
        self.assertIsNotNone(arbol.buscar("h1"))
        self.assertEqual(arbol.tamaño(), 2)

    def test_insertar_id_duplicado_lanza_error(self):
        arbol = _arbol_simple()
        with self.assertRaises(ValueError):
            arbol.insertar("hijo_a", "Duplicado")

    def test_insertar_padre_inexistente_lanza_error(self):
        arbol = ArbolDialogo("r", "Raíz")
        with self.assertRaises(KeyError):
            arbol.insertar("h", "Hijo", id_padre="no_existe")

    def test_eliminar_nodo_intermedio(self):
        arbol = _arbol_simple()
        # Eliminar hijo_a y su subárbol (nieto_a1, nieto_a2)
        resultado = arbol.eliminar("hijo_a")
        self.assertTrue(resultado)
        self.assertIsNone(arbol.buscar("hijo_a"))
        self.assertIsNone(arbol.buscar("nieto_a1"))
        self.assertIsNone(arbol.buscar("nieto_a2"))
        # El resto del árbol sigue intacto
        self.assertIsNotNone(arbol.buscar("hijo_b"))
        self.assertIsNotNone(arbol.buscar("nieto_b1"))

    def test_eliminar_raiz_lanza_error(self):
        arbol = ArbolDialogo("r", "Raíz")
        with self.assertRaises(ValueError):
            arbol.eliminar("r")

    def test_eliminar_nodo_inexistente_retorna_false(self):
        arbol = _arbol_simple()
        self.assertFalse(arbol.eliminar("no_existe"))

    def test_tamaño(self):
        arbol = _arbol_simple()
        self.assertEqual(arbol.tamaño(), 7)

    def test_es_hoja(self):
        arbol = _arbol_simple()
        self.assertTrue(arbol.es_hoja("nieto_a1"))
        self.assertTrue(arbol.es_hoja("biznieto_b1"))
        self.assertFalse(arbol.es_hoja("raiz"))
        self.assertFalse(arbol.es_hoja("hijo_a"))


class TestArbolDialogoBusqueda(unittest.TestCase):
    """Búsqueda de nodos."""

    def test_buscar_existente(self):
        arbol = _arbol_simple()
        nodo = arbol.buscar("nieto_a2")
        self.assertIsNotNone(nodo)
        self.assertEqual(nodo.id, "nieto_a2")

    def test_buscar_inexistente_retorna_none(self):
        arbol = _arbol_simple()
        self.assertIsNone(arbol.buscar("fantasma"))

    def test_buscar_por_texto(self):
        arbol = _arbol_simple()
        resultados = arbol.buscar_por_texto("nieto")
        ids = {n.id for n in resultados}
        self.assertIn("nieto_a1", ids)
        self.assertIn("nieto_a2", ids)
        self.assertIn("nieto_b1", ids)

    def test_ruta_a_nodo(self):
        arbol = _arbol_simple()
        ruta = arbol.ruta_a("biznieto_b1")
        self.assertIsNotNone(ruta)
        ids_ruta = [n.id for n in ruta]
        self.assertEqual(ids_ruta, ["raiz", "hijo_b", "nieto_b1", "biznieto_b1"])

    def test_ruta_a_inexistente_retorna_none(self):
        arbol = _arbol_simple()
        self.assertIsNone(arbol.ruta_a("fantasma"))


class TestArbolDialogoRecorridos(unittest.TestCase):
    """Recorridos preorden, postorden y por niveles."""

    def setUp(self):
        self.arbol = _arbol_simple()

    def test_preorden_raiz_primero(self):
        orden = self.arbol.recorrer_preorden()
        self.assertEqual(orden[0].id, "raiz")
        self.assertEqual(len(orden), 7)
        # Sin duplicados
        self.assertEqual(len({n.id for n in orden}), 7)

    def test_preorden_padre_antes_hijo(self):
        orden = self.arbol.recorrer_preorden()
        ids = [n.id for n in orden]
        self.assertLess(ids.index("hijo_a"), ids.index("nieto_a1"))
        self.assertLess(ids.index("nieto_b1"), ids.index("biznieto_b1"))

    def test_postorden_raiz_ultimo(self):
        orden = self.arbol.recorrer_postorden()
        self.assertEqual(orden[-1].id, "raiz")
        self.assertEqual(len(orden), 7)

    def test_postorden_hijos_antes_padre(self):
        orden = self.arbol.recorrer_postorden()
        ids = [n.id for n in orden]
        self.assertLess(ids.index("nieto_a1"), ids.index("hijo_a"))
        self.assertLess(ids.index("biznieto_b1"), ids.index("nieto_b1"))

    def test_por_niveles_estructura(self):
        niveles = self.arbol.recorrer_por_niveles()
        # Nivel 0: raíz
        self.assertEqual(len(niveles[0]), 1)
        self.assertEqual(niveles[0][0].id, "raiz")
        # Nivel 1: hijo_a, hijo_b
        self.assertEqual(len(niveles[1]), 2)
        # Nivel 2: nieto_a1, nieto_a2, nieto_b1
        self.assertEqual(len(niveles[2]), 3)
        # Nivel 3: biznieto_b1
        self.assertEqual(len(niveles[3]), 1)
        self.assertEqual(niveles[3][0].id, "biznieto_b1")

    def test_altura(self):
        # raiz -> hijo_b -> nieto_b1 -> biznieto_b1  = 3 aristas
        self.assertEqual(self.arbol.altura(), 3)

    def test_altura_solo_raiz(self):
        arbol = ArbolDialogo("r", "Raíz")
        self.assertEqual(arbol.altura(), 0)


class TestArbolDialogoJuego(unittest.TestCase):
    """Interfaz de juego: obtener_opciones y ejecutar_efecto."""

    def test_obtener_opciones_todas_sin_condicion(self):
        arbol = _arbol_simple()
        # hijo_a y hijo_b no tienen condición -> ambos disponibles
        opciones = arbol.obtener_opciones("raiz")
        self.assertEqual(len(opciones), 2)
        ids = {n.id for n in opciones}
        self.assertIn("hijo_a", ids)
        self.assertIn("hijo_b", ids)

    def test_obtener_opciones_con_condicion_bloqueada(self):
        arbol = ArbolDialogo("r", "Raíz")
        arbol.insertar(
            "libre", "Opción libre",
            id_padre="r"
        )
        arbol.insertar(
            "bloqueada", "Opción bloqueada",
            id_padre="r",
            condicion=lambda e: e.get("tiene_escudo", False),
        )
        # Sin escudo
        opciones = arbol.obtener_opciones("r", {"tiene_escudo": False})
        self.assertEqual(len(opciones), 1)
        self.assertEqual(opciones[0].id, "libre")

    def test_obtener_opciones_con_condicion_desbloqueada(self):
        arbol = ArbolDialogo("r", "Raíz")
        arbol.insertar(
            "bloqueada", "Opción desbloqueada",
            id_padre="r",
            condicion=lambda e: e.get("tiene_escudo", False),
        )
        opciones = arbol.obtener_opciones("r", {"tiene_escudo": True})
        self.assertEqual(len(opciones), 1)

    def test_obtener_opciones_nodo_inexistente_retorna_vacio(self):
        arbol = _arbol_simple()
        opciones = arbol.obtener_opciones("fantasma")
        self.assertEqual(opciones, [])

    def test_obtener_opciones_hoja_retorna_vacio(self):
        arbol = _arbol_simple()
        opciones = arbol.obtener_opciones("nieto_a1")
        self.assertEqual(opciones, [])

    def test_ejecutar_efecto_curar(self):
        arbol = ArbolDialogo("r", "Raíz")
        arbol.insertar("curar", "Texto curar", id_padre="r",
                       efecto={"tipo": "curar", "valor": 2})
        estado = {"vidas": 5}
        efecto = arbol.ejecutar_efecto("curar", estado)
        self.assertIsNotNone(efecto)
        self.assertEqual(estado["vidas"], 7)

    def test_ejecutar_efecto_apoyo(self):
        arbol = ArbolDialogo("r", "Raíz")
        arbol.insertar("apoyo", "Texto apoyo", id_padre="r",
                       efecto={"tipo": "apoyo", "valor": 10})
        estado = {"apoyo": 5}
        arbol.ejecutar_efecto("apoyo", estado)
        self.assertEqual(estado["apoyo"], 15)

    def test_ejecutar_efecto_habilidad(self):
        arbol = ArbolDialogo("r", "Raíz")
        arbol.insertar("hab", "Texto habilidad", id_padre="r",
                       efecto={"tipo": "habilidad", "valor": "escudo"})
        estado = {}
        arbol.ejecutar_efecto("hab", estado)
        self.assertIn("escudo", estado["habilidades"])

    def test_ejecutar_efecto_sin_efecto_retorna_none(self):
        arbol = _arbol_simple()
        resultado = arbol.ejecutar_efecto("nieto_a1", {})
        self.assertIsNone(resultado)


class TestArbolSerializacion(unittest.TestCase):
    """Exportar e importar el árbol como diccionario."""

    def test_exportar_importar_estructura(self):
        arbol_orig = _arbol_simple()
        data = arbol_orig.exportar_dict()
        arbol_copia = ArbolDialogo.desde_dict(data)

        self.assertEqual(arbol_copia.tamaño(), arbol_orig.tamaño())
        self.assertEqual(arbol_copia.altura(), arbol_orig.altura())

        # Todos los ids deben existir
        for nodo in arbol_orig.recorrer_preorden():
            self.assertIsNotNone(arbol_copia.buscar(nodo.id))

    def test_exportar_preserva_textos(self):
        arbol = _arbol_simple()
        data = arbol.exportar_dict()
        copia = ArbolDialogo.desde_dict(data)
        for nodo in arbol.recorrer_preorden():
            copia_nodo = copia.buscar(nodo.id)
            self.assertEqual(copia_nodo.texto, nodo.texto)


class TestArbolAlex(unittest.TestCase):
    """Pruebas del árbol de diálogos de Alex (instancia real del juego)."""

    def setUp(self):
        self.arbol = construir_arbol_alex()

    def test_estructura_basica(self):
        self.assertIsNotNone(self.arbol.buscar("alex_root"))
        # Raíz tiene 3 hijos
        raiz = self.arbol.buscar("alex_root")
        self.assertEqual(len(raiz.hijos), 3)

    def test_opciones_sin_evidencia(self):
        """Sin 'evidencia' en armas, la rama de arma debe estar bloqueada."""
        opciones = self.arbol.obtener_opciones("alex_root", {"armas": []})
        ids = {n.id for n in opciones}
        self.assertIn("resp_bien", ids)
        self.assertIn("resp_mal", ids)
        self.assertNotIn("resp_arma", ids)

    def test_opciones_con_evidencia(self):
        """Con 'evidencia' en armas, la rama debe desbloquearse."""
        opciones = self.arbol.obtener_opciones("alex_root", {"armas": ["evidencia"]})
        ids = {n.id for n in opciones}
        self.assertIn("resp_arma", ids)

    def test_efecto_curar_rama_mal(self):
        estado = {"vidas": 3}
        self.arbol.ejecutar_efecto("alex_curar", estado)
        self.assertEqual(estado["vidas"], 4)

    def test_efecto_apoyo_rama_bien(self):
        estado = {"apoyo": 0}
        self.arbol.ejecutar_efecto("alex_animo", estado)
        self.assertEqual(estado["apoyo"], 10)

    def test_recorrido_completo_cubre_todos(self):
        todos = self.arbol.recorrer_preorden()
        self.assertEqual(len(todos), self.arbol.tamaño())

    def test_serializar_alex(self):
        data = self.arbol.exportar_dict()
        copia = ArbolDialogo.desde_dict(data)
        self.assertEqual(copia.tamaño(), self.arbol.tamaño())


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Echoes — Tests: data_structures/tree.py")
    print("=" * 60)

    # Demo visual rápida
    print("\n[Demo] Árbol de diálogos de Alex:")
    arbol_alex = construir_arbol_alex()
    print(f"  {arbol_alex}")
    arbol_alex.imprimir_arbol(mostrar_meta=False)

    print("\n[Demo] Recorrido por niveles:")
    for nivel_idx, nivel in enumerate(arbol_alex.recorrer_por_niveles()):
        ids = ", ".join(n.id for n in nivel)
        print(f"  Nivel {nivel_idx}: {ids}")

    print("\n[Demo] Opciones disponibles en la raíz (sin evidencia):")
    opciones = arbol_alex.obtener_opciones("alex_root", {"armas": []})
    for op in opciones:
        print(f"  -> [{op.id}] {op.texto}")

    print("\n[Demo] Opciones disponibles en la raíz (CON evidencia):")
    opciones_con = arbol_alex.obtener_opciones("alex_root", {"armas": ["evidencia"]})
    for op in opciones_con:
        print(f"  -> [{op.id}] {op.texto}")

    print("\n" + "=" * 60)
    print("  Ejecutando suite completa de tests...")
    print("=" * 60 + "\n")

    unittest.main(verbosity=2)
