# Storyboard y render completo, desacoplado (sobrevive a cerrar la app).
# Si se corta, volver a lanzarlo: render_todo.py se saltea los planos terminados.
Set-Location D:\repos\procedural-anime
while (Get-Process -Name blender -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
if (-not (Test-Path episodios\guardan_una_palabra\out\storyboard.png) -or $args -contains '-storyboard') {
    python motor/storyboard.py episodios/guardan_una_palabra *> episodios\guardan_una_palabra\out\_storyboard.log
}
python motor/render_todo.py episodios/guardan_una_palabra
