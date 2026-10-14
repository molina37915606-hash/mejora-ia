"""Actualizador de Zompix instalado. Descarga instalador firmado por release, sin duplicar ejecutables."""
import json, os, sys, tempfile, pathlib, subprocess, urllib.request, urllib.error, shutil
VERSION="1.4.3"
REPO="molina37915606-hash/mejora-ia"
ASSET="Zompix-Setup.exe"
API=f"https://api.github.com/repos/{REPO}/releases/latest"
def version_key(v):
 return tuple(int(x) for x in v.lstrip("v").split("."))
def check():
 request=urllib.request.Request(API,headers={"User-Agent":"Zompix-Updater/1","Accept":"application/vnd.github+json"})
 with urllib.request.urlopen(request,timeout=15) as response:release=json.load(response)
 latest=release.get("tag_name","").lstrip("v")
 asset=next((a for a in release.get("assets",[]) if a.get("name")==ASSET),None)
 if not asset or not latest:return {"available":False,"version":VERSION,"message":"No hay un instalador público disponible."}
 return {"available":version_key(latest)>version_key(VERSION),"version":VERSION,"latest":latest,"url":asset["browser_download_url"],"bytes":asset["size"],"notes":(release.get("body") or "")[:1000]}
def install(info,current,on_progress=None):
 if not info.get("available"):raise ValueError("No hay versión más reciente")
 current=pathlib.Path(current).resolve()
 expected=pathlib.Path(os.environ.get("LOCALAPPDATA",str(pathlib.Path.home())))/"Programs"/"Zompix"/"Zompix.exe"
 if current!=expected or not current.is_file():raise ValueError("Instalá Zompix con Zompix-Setup.exe una vez para activar las actualizaciones.")
 url=info["url"]
 if not url.startswith(f"https://github.com/{REPO}/releases/download/"):raise ValueError("Origen de descarga no válido")
 tempdir=pathlib.Path(tempfile.mkdtemp(prefix="zompix_update_"))
 target=tempdir/ASSET
 request=urllib.request.Request(url,headers={"User-Agent":"Zompix-Updater/1"})
 try:
  total=int(info.get("bytes") or 0)
  received=0
  with urllib.request.urlopen(request,timeout=300) as source,target.open("wb") as destination:
   while True:
    block=source.read(256*1024)
    if not block:break
    destination.write(block);received+=len(block)
    if on_progress:on_progress(phase="downloading",downloaded=received,total=total,percent=round(received*100/total,1) if total else 0,message="Descargando instalador")
  if on_progress:on_progress(phase="verifying",percent=100,message="Verificando descarga")
  if target.stat().st_size!=info["bytes"]:raise ValueError("El tamaño descargado no coincide con el esperado")
  # Auxiliar externo: espera a que ZOMPIX se cierre antes de reemplazar su EXE.
  # Guarda el estado para poder diagnosticar errores después de reiniciar.
  state_dir=pathlib.Path(os.environ.get("LOCALAPPDATA",str(pathlib.Path.home())))/"Zompix"
  state_dir.mkdir(parents=True,exist_ok=True)
  status_file=state_dir/"ultima_actualizacion.txt"
  status_file.write_text("Instalador descargado. Esperando cierre de ZOMPIX.",encoding="utf-8")
  script=tempdir/"apply.ps1"
  setup=str(target).replace("'","''")
  application=str(expected).replace("'","''")
  report=str(status_file).replace("'","''")
  pid=os.getpid()
  ps="""$ErrorActionPreference='Stop'
$report='REPORT'
$setup='SETUP'
$app='APPLICATION'
try {
 'Esperando cierre de ZOMPIX...' | Set-Content -LiteralPath $report -Encoding UTF8
 $deadline=(Get-Date).AddMinutes(3)
 while (Get-Process -Id PID -ErrorAction SilentlyContinue) {
  if ((Get-Date) -gt $deadline) { throw 'ZOMPIX no se cerró a tiempo' }
  Start-Sleep -Seconds 1
 }
 'Instalando actualización...' | Set-Content -LiteralPath $report -Encoding UTF8
 $proc=Start-Process -FilePath $setup -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS' -PassThru -Wait
 if ($proc.ExitCode -ne 0) { throw ('Instalador terminó con código '+$proc.ExitCode) }
 if (-not (Test-Path -LiteralPath $app)) { throw 'No se encontró el ejecutable actualizado' }
 'Instalación terminada. Abriendo ZOMPIX...' | Set-Content -LiteralPath $report -Encoding UTF8
 Start-Process -FilePath $app
 'Actualización finalizada. ZOMPIX reiniciado.' | Set-Content -LiteralPath $report -Encoding UTF8
} catch {
 ('Error al actualizar: '+$_.Exception.Message) | Set-Content -LiteralPath $report -Encoding UTF8
}
"""
  ps=ps.replace("REPORT",report).replace("SETUP",setup).replace("APPLICATION",application).replace("PID",str(pid))
  script.write_text(ps,encoding="utf-8-sig")
  creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"CREATE_NO_WINDOW",0)
  subprocess.Popen(["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",str(script)],creationflags=creationflags,close_fds=True)

 except:
  shutil.rmtree(tempdir,ignore_errors=True)
  raise
 return True
