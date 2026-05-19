"""
Lanzador raíz — redirige automáticamente a CODIGO/Main.py con el
directorio de trabajo correcto para que los assets se encuentren.

Desde VSCode: usa F5 con la configuración "ECHOES - Jugar (Menu + Cinematica)".
Desde terminal: cd CODIGO && python Main.py
"""
import sys
import os
from pathlib import Path

# Asegurar que cwd sea CODIGO/ para que todos los paths relativos funcionen
codigo_dir = Path(__file__).parent / "CODIGO"
os.chdir(codigo_dir)
sys.path.insert(0, str(codigo_dir))

# Lanzar el juego real
import runpy
runpy.run_path(str(codigo_dir / "Main.py"), run_name="__main__")
