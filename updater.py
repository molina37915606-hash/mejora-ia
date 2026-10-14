"""Actualizador de Zompix instalado. Descarga instalador firmado por release, sin duplicar ejecutables."""
import json, os, sys, tempfile, pathlib, subprocess, urllib.request, urllib.error, shutil
VERSION="1.2.0"
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
def install(info,current):
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
  with urllib.request.urlopen(request,timeout=300) as source,target.open("wb") as destination:
   shutil.copyfileobj(source,destination,1024*1024)
  if target.stat().st_size!=info["bytes"]:raise ValueError("El tamaño descargado no coincide con el esperado")
  # El instalador actualiza el mismo directorio y acceso directo sin crear otra instalación.
  flags=getattr(subprocess,"CREATE_NO_WINDOW",0)|getattr(subprocess,"DETACHED_PROCESS",0)
  script=tempdir/"apply.ps1"
  setup=str(target).replace("'","''")
  application=str(expected).replace("'","''")
  ps="$ErrorActionPreference='Stop'\nStart-Sleep -Seconds 3\n$p=Start-Process -FilePath '"+setup+"' -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS' -Wait -PassThru\nif($p.ExitCode -eq 0){Start-Process -FilePath '"+application+"'}\n"
  temporary=str(tempdir).replace("'","''")
  ps += "Start-Sleep -Seconds 2\nRemove-Item -LiteralPath '"+temporary+"' -Recurse -Force -ErrorAction SilentlyContinue\n"
  script.write_text(ps,encoding="utf-8")
  subprocess.Popen(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(script)],creationflags=flags,close_fds=True)
 except:
  shutil.rmtree(tempdir,ignore_errors=True)
  raise
 return True
