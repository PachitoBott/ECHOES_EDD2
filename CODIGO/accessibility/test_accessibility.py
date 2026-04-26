"""
accessibility/test_accessibility.py
=====================================
Suite de pruebas para los modulos de accesibilidad de Echoes (Fase 5).

Cubre:
  - SubtitleSystem   (cola, tick, limpiar, atajos semanticos)
  - VisualAlertSystem (alertar, tick, atajos, limites)
  - ColorSettings     (paletas, get, set, export)
  - HelpScreen        (toggle, visible, handle_event)
  - CrashGuard        (safe_call, contexto, ErrorOverlay)

Todos los tests corren sin display grafico.
"""
from __future__ import annotations

import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock de pygame (igual que en test_narrative.py)
# ---------------------------------------------------------------------------

def _mock_pygame() -> None:
    try:
        import pygame
        pygame.font.init()
        return
    except ImportError:
        pass
    except Exception:
        pass

    _pg = types.ModuleType("pygame")
    _pg.SRCALPHA        = 65536
    _pg.MOUSEBUTTONDOWN = 5
    _pg.MOUSEMOTION     = 4
    _pg.MOUSEWHEEL      = 1027
    _pg.KEYDOWN         = 2
    _pg.K_ESCAPE        = 27
    _pg.K_F1            = 282
    _pg.K_UP            = 273; _pg.K_DOWN = 274
    _pg.K_s = 115; _pg.K_w = 119

    class _FakeSurface:
        def __init__(self, size=(0, 0), flags=0):
            self.size = size
        def fill(self, *a, **kw): pass
        def blit(self, *a, **kw): pass
        def get_width(self):  return 960
        def get_height(self): return 640
        def set_alpha(self, *a): pass

    class _FakeFont:
        def render(self, txt, aa, col): return _FakeSurface((len(txt)*8, 14))
        def size(self, txt): return (len(txt) * 8, 14)
        def get_linesize(self): return 16

    class _FakeFontModule:
        @staticmethod
        def SysFont(name, size): return _FakeFont()

    _pg.Surface  = _FakeSurface
    _pg.font     = _FakeFontModule
    _pg.draw     = MagicMock()
    _pg.event    = MagicMock()

    sys.modules["pygame"] = _pg

_mock_pygame()


# ---------------------------------------------------------------------------
# Importaciones del proyecto
# ---------------------------------------------------------------------------

from accessibility.subtitles    import SubtitleSystem
from accessibility.visual_alerts import VisualAlertSystem
from accessibility.color_settings import ColorSettings
from accessibility.help_screen  import HelpScreen
from accessibility.crash_guard  import safe_call, CrashGuard, ErrorOverlay


# ===========================================================================
# 1. Tests de SubtitleSystem
# ===========================================================================

class TestSubtitleSystem(unittest.TestCase):

    def _ss(self, activo=True) -> SubtitleSystem:
        return SubtitleSystem(960, 640, font_size=13, activo=activo)

    # ---- estado inicial ----
    def test_vacio_al_inicio(self):
        ss = self._ss()
        self.assertEqual(ss.num_activos, 0)

    def test_activo_por_defecto(self):
        ss = self._ss()
        self.assertTrue(ss.activo)

    # ---- agregar ----
    def test_agregar_aumenta_cola(self):
        ss = self._ss()
        ss.agregar("Hola")
        self.assertEqual(ss.num_activos, 1)

    def test_agregar_varios(self):
        ss = self._ss()
        for i in range(3):
            ss.agregar(f"Sub {i}")
        self.assertEqual(ss.num_activos, 3)

    def test_agregar_inactivo_no_agrega(self):
        ss = self._ss(activo=False)
        ss.agregar("No deberia aparecer")
        self.assertEqual(ss.num_activos, 0)

    # ---- tick / expiracion ----
    def test_tick_no_elimina_recientes(self):
        ss = self._ss()
        ss.agregar("Nuevo", duracion=10.0)
        ss.tick(0.016)
        self.assertEqual(ss.num_activos, 1)

    def test_limpiar_vacia_todo(self):
        ss = self._ss()
        for _ in range(3):
            ss.agregar("x")
        ss.limpiar()
        self.assertEqual(ss.num_activos, 0)

    def test_subtitulo_expira_con_tiempo_real(self):
        ss = self._ss()
        ss.agregar("Breve", duracion=0.001)
        time.sleep(0.01)
        ss.tick(0.016)
        self.assertEqual(ss.num_activos, 0)

    # ---- atajos semanticos ----
    def test_golpe_agrega(self):
        ss = self._ss()
        ss.golpe("Enemigo")
        self.assertEqual(ss.num_activos, 1)

    def test_curacion_agrega(self):
        ss = self._ss()
        ss.curacion(10)
        self.assertEqual(ss.num_activos, 1)

    def test_apoyo_recibido_agrega(self):
        ss = self._ss()
        ss.apoyo_recibido("escudo")
        self.assertEqual(ss.num_activos, 1)

    def test_peligro_agrega(self):
        ss = self._ss()
        ss.peligro("Acosador cerca")
        self.assertEqual(ss.num_activos, 1)

    def test_sistema_agrega(self):
        ss = self._ss()
        ss.sistema("Partida guardada")
        self.assertEqual(ss.num_activos, 1)

    def test_victoria_agrega(self):
        ss = self._ss()
        ss.victoria()
        self.assertEqual(ss.num_activos, 1)

    # ---- limite maximo ----
    def test_no_desborda_cola(self):
        ss = self._ss()
        for i in range(20):
            ss.agregar(f"Linea {i}", duracion=999)
        # maxlen de deque evita desbordamiento
        self.assertLessEqual(ss.num_activos, 10)


# ===========================================================================
# 2. Tests de VisualAlertSystem
# ===========================================================================

class TestVisualAlertSystem(unittest.TestCase):

    def _vas(self) -> VisualAlertSystem:
        return VisualAlertSystem(960, 640, activo=True)

    # ---- estado inicial ----
    def test_sin_alertas_al_inicio(self):
        vas = self._vas()
        self.assertEqual(vas.num_activas, 0)

    def test_activo_por_defecto(self):
        vas = self._vas()
        self.assertTrue(vas.activo)

    # ---- alertar ----
    def test_alertar_tipo_valido(self):
        vas = self._vas()
        vas.alertar("golpe")
        self.assertEqual(vas.num_activas, 1)

    def test_alertar_tipo_invalido_no_explota(self):
        vas = self._vas()
        vas.alertar("no_existe")
        self.assertEqual(vas.num_activas, 0)

    def test_alertar_inactivo_no_agrega(self):
        vas = VisualAlertSystem(960, 640, activo=False)
        vas.alertar("golpe")
        self.assertEqual(vas.num_activas, 0)

    # ---- tick / expiracion ----
    def test_alerta_expira(self):
        vas = self._vas()
        vas.alertar("error")  # duracion 0.4s
        time.sleep(0.5)
        vas.tick(0.016)
        self.assertEqual(vas.num_activas, 0)

    def test_alerta_no_expira_antes_de_tiempo(self):
        vas = self._vas()
        vas.alertar("apoyo")  # duracion 0.6s
        vas.tick(0.016)
        self.assertGreater(vas.num_activas, 0)

    # ---- hay_alerta ----
    def test_hay_alerta_true(self):
        vas = self._vas()
        vas.alertar("curacion")
        self.assertTrue(vas.hay_alerta("curacion"))

    def test_hay_alerta_false(self):
        vas = self._vas()
        self.assertFalse(vas.hay_alerta("golpe"))

    # ---- atajos ----
    def test_on_golpe(self):
        vas = self._vas()
        vas.on_golpe()
        self.assertTrue(vas.hay_alerta("golpe"))

    def test_on_curacion(self):
        vas = self._vas()
        vas.on_curacion()
        self.assertTrue(vas.hay_alerta("curacion"))

    def test_on_apoyo(self):
        vas = self._vas()
        vas.on_apoyo()
        self.assertTrue(vas.hay_alerta("apoyo"))

    def test_on_peligro(self):
        vas = self._vas()
        vas.on_peligro()
        self.assertTrue(vas.hay_alerta("peligro"))

    def test_on_victoria(self):
        vas = self._vas()
        vas.on_victoria()
        self.assertTrue(vas.hay_alerta("victoria"))

    def test_on_error(self):
        vas = self._vas()
        vas.on_error()
        self.assertTrue(vas.hay_alerta("error"))

    # ---- limite de alertas simultaneas ----
    def test_no_supera_max_alertas(self):
        vas = self._vas()
        for _ in range(VisualAlertSystem.MAX_ALERTAS + 5):
            vas.alertar("golpe")
        self.assertLessEqual(vas.num_activas, VisualAlertSystem.MAX_ALERTAS)

    # ---- registrar tipo personalizado ----
    def test_registrar_tipo_personalizado(self):
        vas = self._vas()
        vas.registrar_tipo("especial", (255, 0, 255), duracion=1.0, grosor=5, pulsos=2)
        vas.alertar("especial")
        self.assertTrue(vas.hay_alerta("especial"))

    def test_tipos_disponibles(self):
        vas = self._vas()
        tipos = vas.tipos_disponibles()
        self.assertIn("golpe", tipos)
        self.assertIn("curacion", tipos)
        self.assertIn("victoria", tipos)


# ===========================================================================
# 3. Tests de ColorSettings
# ===========================================================================

class TestColorSettings(unittest.TestCase):

    def test_paleta_normal_por_defecto(self):
        cs = ColorSettings()
        self.assertEqual(cs.nombre_paleta, "normal")

    def test_aplicar_paleta_valida(self):
        cs = ColorSettings()
        ok = cs.aplicar("alto_contraste")
        self.assertTrue(ok)
        self.assertEqual(cs.nombre_paleta, "alto_contraste")

    def test_aplicar_paleta_invalida(self):
        cs = ColorSettings()
        ok = cs.aplicar("no_existe")
        self.assertFalse(ok)
        self.assertEqual(cs.nombre_paleta, "normal")

    def test_get_clave_existente(self):
        cs = ColorSettings()
        col = cs.get("jugador")
        self.assertIsInstance(col, tuple)
        self.assertEqual(len(col), 3)
        self.assertTrue(all(0 <= c <= 255 for c in col))

    def test_get_clave_inexistente_fallback(self):
        cs = ColorSettings()
        col = cs.get("no_existe", fallback=(1, 2, 3))
        self.assertEqual(col, (1, 2, 3))

    def test_get_clave_inexistente_blanco(self):
        cs = ColorSettings()
        col = cs.get("no_existe")
        self.assertEqual(col, (255, 255, 255))

    def test_set_color_sobreescribe(self):
        cs = ColorSettings()
        cs.set_color("jugador", (1, 2, 3))
        self.assertEqual(cs.get("jugador"), (1, 2, 3))

    def test_exportar_es_copia(self):
        cs = ColorSettings()
        exp = cs.exportar()
        exp["jugador"] = (0, 0, 0)
        self.assertNotEqual(cs.get("jugador"), (0, 0, 0))

    def test_subscript_operator(self):
        cs = ColorSettings()
        col = cs["jugador"]
        self.assertIsInstance(col, tuple)

    def test_paletas_disponibles(self):
        paletas = ColorSettings.paletas_disponibles()
        self.assertIn("normal", paletas)
        self.assertIn("alto_contraste", paletas)
        self.assertIn("daltonismo_rj", paletas)
        self.assertIn("daltonismo_az", paletas)
        self.assertIn("oscuro_puro", paletas)

    def test_nombre_legible(self):
        n = ColorSettings.nombre_legible("alto_contraste")
        self.assertIsInstance(n, str)
        self.assertGreater(len(n), 0)

    def test_aplicar_cada_paleta(self):
        cs = ColorSettings()
        for nombre in ColorSettings.paletas_disponibles():
            with self.subTest(paleta=nombre):
                ok = cs.aplicar(nombre)
                self.assertTrue(ok)
                # Verificar que clave basica existe
                col = cs.get("jugador")
                self.assertIsInstance(col, tuple)

    def test_paleta_inicial_personalizada(self):
        cs = ColorSettings(paleta_inicial="daltonismo_rj")
        self.assertEqual(cs.nombre_paleta, "daltonismo_rj")

    def test_claves_disponibles(self):
        cs = ColorSettings()
        claves = cs.claves_disponibles()
        self.assertIn("jugador", claves)
        self.assertIn("enemigo", claves)
        self.assertIn("fondo", claves)


# ===========================================================================
# 4. Tests de HelpScreen
# ===========================================================================

class TestHelpScreen(unittest.TestCase):

    def _hs(self) -> HelpScreen:
        return HelpScreen(960, 640, font_size=13)

    # ---- estado inicial ----
    def test_no_visible_al_inicio(self):
        hs = self._hs()
        self.assertFalse(hs.visible)

    # ---- toggle ----
    def test_toggle_abre(self):
        hs = self._hs()
        hs.toggle()
        self.assertTrue(hs.visible)

    def test_toggle_cierra(self):
        hs = self._hs()
        hs.toggle()
        hs.toggle()
        self.assertFalse(hs.visible)

    def test_cerrar(self):
        hs = self._hs()
        hs.toggle()
        hs.cerrar()
        self.assertFalse(hs.visible)

    def test_visible_setter(self):
        hs = self._hs()
        hs.visible = True
        self.assertTrue(hs.visible)

    # ---- handle_event ----
    def test_handle_no_consume_cuando_cerrado(self):
        hs = self._hs()
        import pygame
        ev = MagicMock()
        ev.type = pygame.KEYDOWN
        ev.key  = pygame.K_F1
        consumido = hs.handle_event(ev)
        self.assertFalse(consumido)

    def test_handle_escape_cierra(self):
        hs = self._hs()
        hs.toggle()
        import pygame
        ev = MagicMock()
        ev.type = pygame.KEYDOWN
        ev.key  = pygame.K_ESCAPE
        consumido = hs.handle_event(ev)
        self.assertTrue(consumido)
        self.assertFalse(hs.visible)

    def test_handle_f1_cierra(self):
        hs = self._hs()
        hs.toggle()
        import pygame
        ev = MagicMock()
        ev.type = pygame.KEYDOWN
        ev.key  = pygame.K_F1
        hs.handle_event(ev)
        self.assertFalse(hs.visible)

    def test_handle_consume_todo_cuando_abierto(self):
        hs = self._hs()
        hs.toggle()
        ev = MagicMock()
        ev.type = 99   # tipo desconocido
        self.assertTrue(hs.handle_event(ev))


# ===========================================================================
# 5. Tests de CrashGuard y ErrorOverlay
# ===========================================================================

class TestSafeCall(unittest.TestCase):

    def test_funcion_normal(self):
        @safe_call
        def suma(a, b): return a + b
        self.assertEqual(suma(2, 3), 5)

    def test_excepcion_retorna_none(self):
        @safe_call
        def falla(): raise ValueError("boom")
        self.assertIsNone(falla())

    def test_excepcion_no_propaga(self):
        @safe_call
        def falla(): raise RuntimeError("error grave")
        try:
            resultado = falla()
            self.assertIsNone(resultado)
        except RuntimeError:
            self.fail("safe_call no deberia propagar la excepcion")

    def test_preserva_nombre(self):
        @safe_call
        def mi_funcion(): pass
        self.assertEqual(mi_funcion.__name__, "mi_funcion")


class TestCrashGuard(unittest.TestCase):

    def test_bloque_sin_error(self):
        guard = CrashGuard()
        with guard:
            x = 1 + 1
        self.assertIsNone(guard.ultimo_error)

    def test_bloque_con_error_capturado(self):
        guard = CrashGuard()
        with guard:
            raise ValueError("fallo")
        self.assertIsNotNone(guard.ultimo_error)

    def test_on_error_llamado(self):
        recibidos = []
        guard = CrashGuard(on_error=lambda m: recibidos.append(m))
        with guard:
            raise RuntimeError("error")
        self.assertEqual(len(recibidos), 1)
        self.assertIn("RuntimeError", recibidos[0])

    def test_no_captura_teclado_interrupt(self):
        guard = CrashGuard(excepciones=(ValueError,))
        with self.assertRaises(RuntimeError):
            with guard:
                raise RuntimeError("debe propagarse")

    def test_relanzar_true(self):
        guard = CrashGuard(relanzar=True)
        with self.assertRaises(ValueError):
            with guard:
                raise ValueError("relanzar")

    def test_run_safe_sin_error(self):
        guard = CrashGuard()
        resultado = guard.run_safe(lambda: 42)
        self.assertEqual(resultado, 42)

    def test_run_safe_con_error(self):
        guard = CrashGuard()
        resultado = guard.run_safe(lambda: (_ for _ in ()).throw(ValueError("fallo")))
        self.assertIsNone(resultado)

    def test_zona_sin_error(self):
        guard = CrashGuard()
        with guard.zona("test"):
            x = 1
        self.assertIsNone(guard.ultimo_error)

    def test_zona_con_error_capturado(self):
        guard = CrashGuard()
        with guard.zona("renderizado"):
            raise Exception("fallo en zona")
        self.assertIn("renderizado", guard.ultimo_error)


class TestErrorOverlay(unittest.TestCase):

    def test_no_activo_al_inicio(self):
        eo = ErrorOverlay(960, 640)
        self.assertFalse(eo.activo)

    def test_mostrar_activa(self):
        eo = ErrorOverlay(960, 640)
        eo.mostrar("Error de prueba")
        self.assertTrue(eo.activo)

    def test_expira_con_tiempo(self):
        eo = ErrorOverlay(960, 640, duracion=0.01)
        eo.mostrar("Breve")
        time.sleep(0.02)
        eo.tick(0.016)
        self.assertFalse(eo.activo)

    def test_mensaje_largo_truncado(self):
        eo = ErrorOverlay(960, 640)
        eo.mostrar("x" * 500)
        # No debe guardar mas de 200 chars
        self.assertLessEqual(len(eo._mensaje), 200)

    def test_tick_sin_mensaje_no_explota(self):
        eo = ErrorOverlay(960, 640)
        eo.tick(0.016)   # no debe lanzar excepcion


# ===========================================================================
# 6. Test de integracion — accesibilidad en juego simulado
# ===========================================================================

class TestIntegracionAccesibilidad(unittest.TestCase):

    def test_flujo_completo_sin_errores(self):
        """Simula un frame del juego con todos los sistemas de accesibilidad."""
        import pygame
        screen = pygame.Surface((960, 640))

        ss  = SubtitleSystem(960, 640, activo=True)
        vas = VisualAlertSystem(960, 640, activo=True)
        cs  = ColorSettings(paleta_inicial="alto_contraste")
        hs  = HelpScreen(960, 640)
        eo  = ErrorOverlay(960, 640)
        guard = CrashGuard(on_error=eo.mostrar)

        # Simular eventos del juego
        ss.golpe("Acosador1")
        vas.on_golpe()
        vas.on_peligro()
        ss.sistema("Reporte enviado")
        eo.mostrar("Test error no critico")

        # Simular tick
        dt = 0.016
        ss.tick(dt)
        vas.tick(dt)
        eo.tick(dt)

        # Verificar estado
        self.assertGreater(ss.num_activos, 0)
        self.assertGreater(vas.num_activas, 0)
        self.assertEqual(cs.nombre_paleta, "alto_contraste")
        self.assertFalse(hs.visible)

        # Draw (no debe lanzar excepcion)
        with guard:
            ss.draw(screen, screen_scale=1)
            vas.draw(screen, screen_scale=1)
            eo.draw(screen, screen_scale=1)

    def test_color_settings_con_entidades(self):
        """Verifica que los colores de paleta son usables para renderizar."""
        cs = ColorSettings("daltonismo_rj")
        col_j = cs["jugador"]
        col_e = cs["enemigo"]
        col_a = cs["aliado"]
        # Deben ser distintos entre si (sin ambiguedad)
        self.assertNotEqual(col_j, col_e)
        self.assertNotEqual(col_j, col_a)

    def test_crash_guard_protege_narrativa(self):
        """CrashGuard captura errores en el sistema narrativo."""
        errores = []
        guard = CrashGuard(on_error=lambda m: errores.append(m))

        def narrativa_rota():
            raise RuntimeError("NarrativeManager exploto")

        with guard:
            narrativa_rota()

        self.assertEqual(len(errores), 1)
        self.assertIn("RuntimeError", errores[0])

    def test_subtitulos_multilingue(self):
        """SubtitleSystem maneja correctamente tildes y eñes."""
        ss = SubtitleSystem(960, 640)
        ss.agregar("¡Cuidado! Acosador: ñoño")
        ss.agregar("Curación aplicada correctamente")
        self.assertEqual(ss.num_activos, 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
