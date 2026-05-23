# test_client_crash.ps1
# Script para reproducir el bug: cliente se cierra al recibir START_GAME

$servidor_path = "F:\martin\Universidad\ECHOES_EDD2\CODIGO"
$cd_cmd = "cd `"$servidor_path`""

# Lanzar servidor en una nueva ventana
Write-Host "Lanzando servidor en puerto 5555..."
$servidor_cmd = "$cd_cmd; python Main.py --server --port 5555"
Start-Process powershell -ArgumentList "-NoExit -Command `"$servidor_cmd`""

# Esperar a que el servidor esté listo
Start-Sleep -Seconds 2

# Lanzar cliente en otra ventana
Write-Host "Lanzando cliente..."
$cliente_cmd = "$cd_cmd; python Main.py --client --host 127.0.0.1 --port 5555 --role victim"
Start-Process powershell -ArgumentList "-NoExit -Command `"$cliente_cmd`""

Write-Host "Servidor y cliente lanzados."
Write-Host "En el servidor: presiona ENTER para ir al lobby"
Write-Host "En el servidor: presiona ENTER en el botón JUGAR para iniciar el juego"
Write-Host "Observa si el cliente se cierra cuando recibe START_GAME"
