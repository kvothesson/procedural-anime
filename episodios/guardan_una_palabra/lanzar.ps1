# Storyboard y render completo. Lanzarlo con WMI para que no dependa de la app:
#   Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\repos\procedural-anime\episodios\guardan_una_palabra\lanzar.ps1'}
# (un Start-Process desde la app muere con la sesion). Si se corta, volver a
# lanzarlo: render_todo.py se saltea los planos terminados.
Set-Location D:\repos\procedural-anime
while (Get-Process -Name blender -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
if (-not (Test-Path episodios\guardan_una_palabra\out\storyboard.png)) {
    python motor/storyboard.py episodios/guardan_una_palabra *> episodios\guardan_una_palabra\out\_storyboard.log
}
python motor/render_todo.py episodios/guardan_una_palabra
