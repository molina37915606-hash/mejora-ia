$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
py -m pip install --disable-pip-version-check pyinstaller pillow pywebview
if ($LASTEXITCODE -ne 0) {throw "No se pudieron instalar dependencias"}
$uri="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
$zip=Join-Path $env:TEMP 'mejoraia_motor.zip'
Invoke-WebRequest -Uri $uri -OutFile $zip
$unpack=Join-Path $env:TEMP ('mejoraia_engine_'+[guid]::NewGuid())
Expand-Archive $zip $unpack
$exe=Get-ChildItem $unpack -Filter realesrgan-ncnn-vulkan.exe -Recurse | Select-Object -First 1
if (-not $exe){throw "Descarga sin ejecutable Real-ESRGAN"}
if (Test-Path engine){Remove-Item engine -Recurse -Force}
New-Item engine -ItemType Directory | Out-Null
Copy-Item (Join-Path $exe.Directory.FullName '*') engine -Recurse -Force
if (-not (Test-Path engine/models)){throw "El paquete no contiene modelos de IA"}
py -m py_compile server.py updater.py disk_output.py generar_biblioteca.py
if ($LASTEXITCODE -ne 0){throw "Error de sintaxis en el código Python"}
py generar_biblioteca.py
if ($LASTEXITCODE -ne 0){throw "No se pudo generar la biblioteca incluida"}
py generar_icono.py
if ($LASTEXITCODE -ne 0){throw "No se pudo crear el icono"}
py -m PyInstaller --noconfirm --clean --onefile --windowed --name Zompix --icon "zompix.ico" --add-data "index.html;." --add-data "brand.svg;." --add-data "engine;engine" --add-data "biblioteca_incluida;biblioteca_incluida" server.py
if ($LASTEXITCODE -ne 0){throw "Falló compilación"}
Write-Host "EXE preparado: dist/Zompix.exe"
