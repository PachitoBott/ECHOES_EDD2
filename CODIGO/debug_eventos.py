#!/usr/bin/env python3
"""
Debug: Verificar que los eventos se envían correctamente
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("="*70)
print("DEBUG: ESTRUCTURA DE EVENTOS")
print("="*70)

# Test 1: Crear evento enemigo_muerto
print("\n[TEST 1] Crear evento enemigo_muerto...")
from network.protocol import msg_enemigo_muerto, Mensaje

msg = msg_enemigo_muerto(100.0, 200.0, "BasicEnemy", (1, 2))
print(f"  Tipo: {msg.tipo}")
print(f"  Datos: {msg.datos}")
print(f"  Datos['tipo']: {msg.datos.get('tipo')}")

# Test 2: Serializar y deserializar
print("\n[TEST 2] Serializar y deserializar...")
serializado = msg.serializar()
print(f"  Serializado: {serializado[:100]}...")

deserializado = Mensaje.deserializar(serializado)
print(f"  Tipo después: {deserializado.tipo}")
print(f"  Datos['tipo'] después: {deserializado.datos.get('tipo')}")

# Test 3: Crear EventoRed como lo hace el servidor
print("\n[TEST 3] Simular EventoRed del servidor...")
from network.protocol import EventoRed

# Esto es lo que probablemente hace NetworkManager
ev = EventoRed(
    tipo=deserializado.tipo,  # Debería ser "evento"
    datos=deserializado.datos,
    origen="victima"
)
print(f"  EventoRed tipo: {ev.tipo}")
print(f"  EventoRed datos['tipo']: {ev.datos.get('tipo')}")

# Test 4: Verificar que el handler debería funcionar
print("\n[TEST 4] Verificar handler...")
if ev.tipo == "evento":
    tipo_evento = ev.datos.get("tipo")
    if tipo_evento == "enemigo_muerto":
        print(f"  ✅ CORRECTO: Se procesaría como enemigo_muerto")
    else:
        print(f"  ❌ ERROR: tipo_evento = {tipo_evento}")
else:
    print(f"  ❌ ERROR: ev.tipo = {ev.tipo}")

print("\n" + "="*70)

