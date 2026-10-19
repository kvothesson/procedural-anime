# Espera a que termine el render completo, borra los planos 14 y 15 (tenian el
# techo del crucero titilando) y vuelve a lanzar render_todo: rehace solo esos
# y arma el montaje de nuevo. Lanzado por WMI para no depender de la app.
Set-Location D:\repos\procedural-anime
$log = 'episodios\guardan_una_palabra\out\_render_todo.log'
while (-not (Select-String -Path $log -Pattern 'terminado' -Quiet)) { Start-Sleep -Seconds 60 }
while (Get-Process -Name blender -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
Add-Content $log ("{0} rehacer 14 y 15: techo del crucero corregido" -f (Get-Date -Format HH:mm:ss))
Get-ChildItem episodios\guardan_una_palabra\out, episodios\guardan_una_palabra\render -Directory |
    Where-Object { $_.Name -match '^(14[a-h]_hora|15[a-e]_)' } | Remove-Item -Recurse -Force
python motor/render_todo.py episodios/guardan_una_palabra
