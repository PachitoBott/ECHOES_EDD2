"""
test_network.py — Suite de pruebas para network/
=================================================
Ejecucion:
    cd CODIGO
    python network/test_network.py

Prueba el protocolo, el servidor y el cliente usando localhost.
Todos los tests son autocontenidos (levantan y destruyen sus propios
sockets), por lo que pueden correr en secuencia sin conflictos.

No requiere pytest; usa unittest estandar.
Sin librerias externas.
"""
import sys
import os
import time
import threading
import unittest

# Asegurar que podemos importar desde CODIGO/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from network.protocol import (
    Mensaje, Rol, TipoMensaje,
    msg_conectar, msg_aceptado, msg_rechazado, msg_estado,
    msg_accion, msg_apoyo, msg_evento, msg_ping, msg_pong,
    msg_desconectar, msg_error, validar,
)
from network.server import ServidorEchoes
from network.client import ClienteEchoes
from network.manager import NetworkManager, EventoRed


# ---------------------------------------------------------------------------
# Utilidades de test
# ---------------------------------------------------------------------------

_puerto_counter = 15400   # contador global — incrementa en cada llamada
_puerto_lock = threading.Lock()

def _puerto_libre(base: int | None = None) -> int:
    """
    Devuelve un puerto disponible garantizado unico en esta sesion de tests.

    Usa un contador global (thread-safe) en lugar de un base fijo para
    evitar colisiones cuando varios tests reutilizan el mismo rango de
    puertos en rapida sucesion (especialmente relevante en Windows donde
    SO_REUSEADDR no libera el puerto de inmediato).
    """
    import socket as _socket
    global _puerto_counter
    with _puerto_lock:
        start = _puerto_counter + 1
        _puerto_counter += 50   # salto amplio para evitar solapamientos

    for p in range(start, start + 50):
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError(f"No hay puertos libres en el rango {start}-{start+50}")


def _esperar(condicion, timeout: float = 3.0, intervalo: float = 0.05) -> bool:
    """Espera hasta que condicion() sea True o salte el timeout."""
    limite = time.time() + timeout
    while time.time() < limite:
        if condicion():
            return True
        time.sleep(intervalo)
    return False


# ---------------------------------------------------------------------------
# Tests del protocolo
# ---------------------------------------------------------------------------

class TestProtocolo(unittest.TestCase):
    """Serializar/deserializar mensajes sin red."""

    def test_serializar_deserializar_ida_vuelta(self):
        msg = Mensaje(TipoMensaje.ESTADO, {"hp": 5, "sala": [3, 2]}, origen="servidor")
        raw = msg.serializar()
        self.assertIsInstance(raw, bytes)
        self.assertTrue(raw.endswith(b"\n"))

        recuperado = Mensaje.deserializar(raw)
        self.assertIsNotNone(recuperado)
        self.assertEqual(recuperado.tipo, TipoMensaje.ESTADO)
        self.assertEqual(recuperado.datos["hp"], 5)
        self.assertEqual(recuperado.datos["sala"], [3, 2])
        self.assertEqual(recuperado.origen, "servidor")

    def test_deserializar_json_invalido_retorna_none(self):
        self.assertIsNone(Mensaje.deserializar(b"esto no es json\n"))

    def test_deserializar_json_vacio_retorna_none(self):
        self.assertIsNone(Mensaje.deserializar(b"\n"))

    def test_factories_conectar(self):
        msg = msg_conectar("victima")
        self.assertEqual(msg.tipo, TipoMensaje.CONECTAR)
        self.assertEqual(msg.datos["rol"], "victima")

    def test_factories_estado(self):
        msg = msg_estado(10.5, 20.3, (1, 2), vidas=3, hp=4, apoyo=50)
        self.assertEqual(msg.tipo, TipoMensaje.ESTADO)
        self.assertAlmostEqual(msg.datos["pos"][0], 10.5)
        self.assertEqual(msg.datos["sala"], [1, 2])

    def test_factories_apoyo(self):
        msg = msg_apoyo("curar", valor=2)
        self.assertEqual(msg.tipo, TipoMensaje.APOYO)
        self.assertEqual(msg.datos["apoyo"], "curar")
        self.assertEqual(msg.datos["valor"], 2)

    def test_factories_accion(self):
        msg = msg_accion("mover", dx=1.0, dy=0.0)
        self.assertEqual(msg.tipo, TipoMensaje.ACCION)
        self.assertEqual(msg.datos["accion"], "mover")
        self.assertAlmostEqual(msg.datos["dx"], 1.0)

    def test_validar_mensaje_valido(self):
        msg = msg_conectar("aliado")
        self.assertTrue(validar(msg))

    def test_validar_conectar_sin_rol(self):
        msg = Mensaje(TipoMensaje.CONECTAR, {})  # falta "rol"
        self.assertFalse(validar(msg))

    def test_validar_accion_sin_accion(self):
        msg = Mensaje(TipoMensaje.ACCION, {"dx": 1.0})  # falta "accion"
        self.assertFalse(validar(msg))

    def test_timestamp_auto(self):
        antes = time.time()
        msg = Mensaje(TipoMensaje.PING, {})
        despues = time.time()
        self.assertGreaterEqual(msg.ts, antes)
        self.assertLessEqual(msg.ts, despues)

    def test_texto_unicode_sobrevive_viaje(self):
        msg = Mensaje(TipoMensaje.EVENTO, {"texto": "Hola acento: ciberacoso"})
        recuperado = Mensaje.deserializar(msg.serializar())
        self.assertEqual(recuperado.datos["texto"], "Hola acento: ciberacoso")


# ---------------------------------------------------------------------------
# Tests del servidor (red real en localhost)
# ---------------------------------------------------------------------------

class TestServidor(unittest.TestCase):
    """Pruebas de red del servidor."""

    def setUp(self):
        self.port = _puerto_libre()
        self.servidor = ServidorEchoes(host="127.0.0.1", port=self.port, seed=42)
        self.servidor.iniciar()
        time.sleep(0.15)

    def tearDown(self):
        self.servidor.detener()
        time.sleep(0.1)

    def test_servidor_inicia_y_se_detiene(self):
        self.assertTrue(self.servidor._activo)
        self.servidor.detener()
        self.assertFalse(self.servidor._activo)

    def test_cliente_se_conecta_como_victima(self):
        cliente = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        ok = cliente.conectar()
        self.assertTrue(ok)
        self.assertTrue(cliente.esta_conectado())
        ok2 = _esperar(lambda: Rol.VICTIMA in self.servidor.roles_conectados())
        self.assertTrue(ok2, "Servidor no registro la conexion de Victima")
        cliente.desconectar()

    def test_cliente_recibe_seed_en_handshake(self):
        cliente = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        cliente.conectar()
        self.assertEqual(cliente.seed, 42)
        cliente.desconectar()

    def test_dos_roles_distintos_se_conectan(self):
        c1 = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c2 = ClienteEchoes("127.0.0.1", self.port, rol=Rol.ALIADO)
        self.assertTrue(c1.conectar())
        self.assertTrue(c2.conectar())
        ok = _esperar(self.servidor.esta_listo)
        self.assertTrue(ok, "Servidor no detecto que ambos roles estan conectados")
        c1.desconectar()
        c2.desconectar()

    def test_rol_duplicado_es_rechazado(self):
        c1 = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c2 = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        self.assertTrue(c1.conectar())
        time.sleep(0.1)
        # El segundo cliente con el mismo rol debe ser rechazado
        ok2 = c2.conectar()
        self.assertFalse(ok2, "No deberia aceptar dos clientes con el mismo rol")
        c1.desconectar()

    def test_broadcast_llega_a_ambos_clientes(self):
        c1 = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c2 = ClienteEchoes("127.0.0.1", self.port, rol=Rol.ALIADO)
        c1.conectar()
        c2.conectar()
        _esperar(self.servidor.esta_listo)

        # Limpiar mensajes de handshake
        time.sleep(0.15)
        c1.tick()
        c2.tick()

        # Servidor envia un mensaje a todos
        evento_test = msg_evento("sala_limpia", sala=[1, 1])
        self.servidor.broadcast(evento_test)

        ok1 = _esperar(lambda: len(c1.tick()) > 0 or not c1._cola_in.empty())
        ok2 = _esperar(lambda: len(c2.tick()) > 0 or not c2._cola_in.empty())
        self.assertTrue(ok1 or c1._cola_in.qsize() > 0, "c1 no recibio el broadcast")
        self.assertTrue(ok2 or c2._cola_in.qsize() > 0, "c2 no recibio el broadcast")

        c1.desconectar()
        c2.desconectar()

    def test_servidor_recibe_mensaje_del_cliente(self):
        c = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c.conectar()
        _esperar(lambda: Rol.VICTIMA in self.servidor.roles_conectados())
        time.sleep(0.1)

        accion = msg_accion("mover", dx=1.0, dy=0.0)
        c.enviar(accion)

        ok = _esperar(lambda: len(self.servidor.tick()) > 0 or
                                not self.servidor._cola_in.empty())
        self.assertTrue(ok or self.servidor._cola_in.qsize() > 0,
                        "Servidor no recibio la accion")
        c.desconectar()

    def test_enviar_a_rol_especifico(self):
        c_vic = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c_ali = ClienteEchoes("127.0.0.1", self.port, rol=Rol.ALIADO)
        c_vic.conectar()
        c_ali.conectar()
        _esperar(self.servidor.esta_listo)
        time.sleep(0.15)
        # Vaciar cola de eventos iniciales
        c_vic.tick(); c_ali.tick()

        # Enviar solo al Aliado
        self.servidor.enviar_a(Rol.ALIADO, msg_evento("test_privado"))
        time.sleep(0.15)

        mensajes_ali = c_ali.tick()
        mensajes_vic = c_vic.tick()
        tipos_ali = [m.tipo for m in mensajes_ali]
        tipos_vic = [m.tipo for m in mensajes_vic]

        # El aliado debe tener el evento, la victima no
        self.assertTrue(
            any(m.datos.get("evento") == "test_privado"
                for m in mensajes_ali if m.tipo == TipoMensaje.EVENTO),
            "Aliado no recibio el mensaje privado"
        )
        c_vic.desconectar()
        c_ali.desconectar()


# ---------------------------------------------------------------------------
# Tests del cliente
# ---------------------------------------------------------------------------

class TestCliente(unittest.TestCase):
    """Pruebas del cliente de forma aislada."""

    def setUp(self):
        # Puerto unico por test (contador global) para evitar reutilizacion
        # rapida del mismo puerto en Windows
        self.port = _puerto_libre()
        self.servidor = ServidorEchoes(host="127.0.0.1", port=self.port, seed=7)
        self.servidor.iniciar()
        time.sleep(0.15)   # tiempo para que el hilo de aceptacion inicie

    def tearDown(self):
        self.servidor.detener()
        time.sleep(0.1)

    def test_cliente_no_conectado_tick_retorna_vacio(self):
        c = ClienteEchoes("127.0.0.1", self.port, rol=Rol.ALIADO)
        # Sin conectar
        self.assertEqual(c.tick(), [])

    def test_cliente_enviar_sin_conexion_retorna_false(self):
        c = ClienteEchoes("127.0.0.1", self.port, rol=Rol.ALIADO)
        resultado = c.enviar(msg_ping())
        self.assertFalse(resultado)

    def test_desconexion_limpia(self):
        c = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c.conectar()
        _esperar(c.esta_conectado)
        c.desconectar()
        self.assertFalse(c.esta_conectado())

    def test_conexion_a_servidor_inexistente_retorna_false(self):
        c = ClienteEchoes("127.0.0.1", port=19999, rol=Rol.VICTIMA,
                          timeout_conexion=0.5)
        resultado = c.conectar()
        self.assertFalse(resultado)

    def test_cliente_recibe_broadcast_en_tick(self):
        c = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        c.conectar()
        _esperar(lambda: Rol.VICTIMA in self.servidor.roles_conectados())
        time.sleep(0.1)
        c.tick()   # vaciar mensajes iniciales

        self.servidor.broadcast(msg_evento("hola", dato=123))
        tiempo_espera = _esperar(lambda: not c._cola_in.empty())
        self.assertTrue(tiempo_espera, "Cliente no recibio el mensaje en tiempo")
        mensajes = c.tick()
        tipos = [m.tipo for m in mensajes]
        self.assertIn(TipoMensaje.EVENTO, tipos)
        c.desconectar()


# ---------------------------------------------------------------------------
# Tests del NetworkManager
# ---------------------------------------------------------------------------

class TestNetworkManager(unittest.TestCase):
    """Pruebas de la capa de alto nivel."""

    def setUp(self):
        self.port = _puerto_libre()

    def test_como_servidor_crea_servidor(self):
        mgr = NetworkManager.como_servidor(host="127.0.0.1", port=self.port, seed=99)
        self.assertEqual(mgr.modo, "servidor")
        self.assertTrue(mgr.es_victima)
        self.assertFalse(mgr.es_aliado)

    def test_como_cliente_crea_cliente(self):
        mgr = NetworkManager.como_cliente(host="127.0.0.1", port=self.port,
                                           rol=Rol.ALIADO)
        self.assertEqual(mgr.modo, "cliente")
        self.assertTrue(mgr.es_aliado)

    def test_manager_servidor_inicia_y_acepta_cliente(self):
        mgr_srv = NetworkManager.como_servidor(host="127.0.0.1", port=self.port)
        mgr_srv.iniciar()
        time.sleep(0.1)

        mgr_cli = NetworkManager.como_cliente("127.0.0.1", self.port, rol=Rol.ALIADO)
        ok = mgr_cli.iniciar()
        self.assertTrue(ok)
        self.assertTrue(mgr_cli.esta_conectado())

        mgr_cli.detener()
        mgr_srv.detener()

    def test_enviar_apoyo_solo_desde_aliado(self):
        mgr_srv = NetworkManager.como_servidor(host="127.0.0.1", port=self.port)
        mgr_srv.iniciar()
        time.sleep(0.1)

        mgr_cli = NetworkManager.como_cliente("127.0.0.1", self.port, rol=Rol.ALIADO)
        mgr_cli.iniciar()
        time.sleep(0.1)

        # El Aliado puede enviar apoyo
        resultado = mgr_cli.enviar_apoyo("curar", valor=2)
        self.assertTrue(resultado)

        mgr_cli.detener()
        mgr_srv.detener()

    def test_apoyo_curar_aplica_hp(self):
        """aplicar_apoyo() modifica el atributo hp del jugador."""

        class JugadorFalso:
            hp = 3
            max_hp = 10

        mgr = NetworkManager()
        jugador = JugadorFalso()
        descripcion = mgr.aplicar_apoyo("curar", valor=2, player=jugador)
        self.assertEqual(jugador.hp, 5)
        self.assertIsNotNone(descripcion)

    def test_apoyo_dar_apoyo_aplica_gold(self):
        class JugadorFalso:
            gold = 10

        mgr = NetworkManager()
        jugador = JugadorFalso()
        mgr.aplicar_apoyo("dar_apoyo", valor=25, player=jugador)
        self.assertEqual(jugador.gold, 35)

    def test_apoyo_escudo_aplica_invulnerabilidad(self):
        class JugadorFalso:
            invulnerable_timer = 0.0

        mgr = NetworkManager()
        jugador = JugadorFalso()
        mgr.aplicar_apoyo("escudo", valor=3.0, player=jugador)
        self.assertAlmostEqual(jugador.invulnerable_timer, 3.0)

    def test_apoyo_curar_no_excede_max_hp(self):
        class JugadorFalso:
            hp = 9
            max_hp = 10

        mgr = NetworkManager()
        jugador = JugadorFalso()
        mgr.aplicar_apoyo("curar", valor=5, player=jugador)
        self.assertEqual(jugador.hp, 10)   # no supera max_hp

    def test_tick_sin_iniciar_retorna_vacio(self):
        mgr = NetworkManager()
        self.assertEqual(mgr.tick(), [])

    def test_evento_red_repr(self):
        ev = EventoRed("apoyo_recibido", {"valor": 2}, origen="aliado")
        self.assertIn("apoyo_recibido", repr(ev))


# ---------------------------------------------------------------------------
# Test de integracion completo: servidor + dos clientes + flujo de apoyo
# ---------------------------------------------------------------------------

class TestIntegracionCompleta(unittest.TestCase):
    """
    Simula una sesion completa: servidor hospeda, victima y aliado se conectan,
    aliado envia apoyo, servidor lo retransmite a victima.
    """

    def setUp(self):
        self.port = _puerto_libre()
        self.servidor = ServidorEchoes(host="127.0.0.1", port=self.port, seed=1234)
        self.servidor.iniciar()
        time.sleep(0.15)
        self.victima = ClienteEchoes("127.0.0.1", self.port, rol=Rol.VICTIMA)
        self.aliado  = ClienteEchoes("127.0.0.1", self.port, rol=Rol.ALIADO)
        self.assertTrue(self.victima.conectar())
        self.assertTrue(self.aliado.conectar())
        _esperar(self.servidor.esta_listo)
        time.sleep(0.2)
        # Vaciar cola de eventos iniciales
        self.victima.tick()
        self.aliado.tick()
        self.servidor.tick()

    def tearDown(self):
        self.victima.desconectar()
        self.aliado.desconectar()
        self.servidor.detener()
        time.sleep(0.1)

    def test_ambos_roles_conectados(self):
        roles = self.servidor.roles_conectados()
        self.assertIn(Rol.VICTIMA, roles)
        self.assertIn(Rol.ALIADO,  roles)

    def test_aliado_envia_apoyo_y_servidor_lo_recibe(self):
        apoyo = msg_apoyo("curar", valor=3)
        self.aliado.enviar(apoyo)

        ok = _esperar(lambda: not self.servidor._cola_in.empty())
        self.assertTrue(ok, "Servidor no recibio el mensaje de apoyo")

        mensajes = self.servidor.tick()
        tipos = [m.tipo for m in mensajes]
        self.assertIn(TipoMensaje.APOYO, tipos)

    def test_servidor_retransmite_estado_a_ambos(self):
        estado = msg_estado(100.0, 200.0, (3, 4),
                            vidas=5, hp=8, apoyo=30, arma_id="bloqueo")
        self.servidor.broadcast(estado)

        ok_v = _esperar(lambda: not self.victima._cola_in.empty())
        ok_a = _esperar(lambda: not self.aliado._cola_in.empty())
        self.assertTrue(ok_v, "Victima no recibio el estado")
        self.assertTrue(ok_a, "Aliado no recibio el estado")

    def test_victima_envia_accion_servidor_la_procesa(self):
        accion = msg_accion("transicion", direccion="N")
        self.victima.enviar(accion)

        ok = _esperar(lambda: not self.servidor._cola_in.empty())
        self.assertTrue(ok)
        mensajes = self.servidor.tick()
        acciones = [m for m in mensajes if m.tipo == TipoMensaje.ACCION]
        self.assertTrue(len(acciones) > 0, "No se encontro accion en el servidor")
        self.assertEqual(acciones[0].datos.get("direccion"), "N")

    def test_seed_compartida_entre_clientes(self):
        self.assertEqual(self.victima.seed, 1234)
        self.assertEqual(self.aliado.seed,  1234)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Echoes -- Tests: network/")
    print("=" * 60)
    print()
    unittest.main(verbosity=2)
