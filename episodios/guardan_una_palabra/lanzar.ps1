# Espera al storyboard y lanza el render completo desacoplado (sobrevive a cerrar la app).
Set-Location D:\repos\procedural-anime
while (Get-Process -Name blender -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*storyboard.py*' }) { Start-Sleep -Seconds 20 }
python motor/render_todo.py episodios/guardan_una_palabra
