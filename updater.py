"""Actualizador para releases públicos de GitHub. No almacena credenciales."""
import os, sys, json, urllib.request, urllib.error, hashlib, tempfile, pathlib, subprocess, shutil, time
VERSION="6.1.0"
REPO="molina37915606-hash/mejora-ia"
API=f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET="MejoraIA.exe"
def version_key(v):
 return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())
def check():
 req=urllib.request.Request(API,headers={"User-Agent":"MejoraIA-updater/5.0","Accept":"application/vnd.github+json"})
 try:
  with urllib.request.urlopen(req,timeout=12) as r: release=json.load(r)
 except urllib.error.HTTPError as e:
  if e.code==404:
   return {"available":False,"version":VERSION,"message":"No se encontró una versión pública. El repositorio privado requiere autenticación; no se guardan tokens."}
  raise
 latest=release.get("tag_name","").lstrip("v")
 assets=release.get("assets",[])
 asset=next((x for x in assets if x["name"]==ASSET),None)
 if not latest or not asset:return {"available":False,"version":VERSION,"message":"La publicación no incluye MejoraIA.exe."}
 return {"available":version_key(latest)>version_key(VERSION),"version":VERSION,"latest":latest,"url":asset["browser_download_url"],"bytes":asset["size"],"notes":(release.get("body") or "")[:1500]}
def install(info,current):
 if not info.get("available"):raise ValueError("No hay actualización disponible")
 current=pathlib.Path(current).resolve()
 if current.name.lower()!="mejoraia.exe" or not current.exists():raise ValueError("Para actualizar, ejecutá el MejoraIA.exe instalado.")
 url=info["url"]
 if not url.startswith(f"https://github.com/{REPO}/releases/download/"):raise ValueError("Origen de actualización inesperado")
 folder=current.parent
 staging=folder/("MejoraIA_nueva_"+str(os.getpid())+".exe")
 req=urllib.request.Request(url,headers={"User-Agent":"MejoraIA-updater/5.0"})
 with urllib.request.urlopen(req,timeout=180) as r,staging.open("wb") as out:
  shutil.copyfileobj(r,out,1024*1024)
 if staging.stat().st_size < 100000:staging.unlink(missing_ok=True);raise ValueError("Descarga incompleta")
 # A detached PowerShell updater can replace the exe after the original process exits.
 ps=pathlib.Path(tempfile.gettempdir())/("mejoraia_update_"+str(os.getpid())+".ps1")
 old=str(current).replace("'","''");new=str(staging).replace("'","''")
 ps.write_text("$ErrorActionPreference='Stop'\n$old='"+old+"'\n$new='"+new+"'\n"+
               "for($i=0;$i -lt 60;$i++){try{Move-Item -LiteralPath $new -Destination $old -Force -ErrorAction Stop; break}catch{Start-Sleep -Seconds 1}}\n"+
               "if(Test-Path -LiteralPath $new){exit 1}\nStart-Process -FilePath $old\n",encoding="utf-8")
 flags=getattr(subprocess,"CREATE_NO_WINDOW",0)|getattr(subprocess,"DETACHED_PROCESS",0)
 subprocess.Popen(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ps)],creationflags=flags,close_fds=True)
 return True
