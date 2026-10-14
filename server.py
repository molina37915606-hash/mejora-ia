import io, os, sys, uuid, tempfile, subprocess, threading, webbrowser, json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageOps
import updater
ROOT=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
BASE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"MejoraIA"/"Resultados"
BASE.mkdir(parents=True,exist_ok=True)
ENGINE=ROOT/"engine"/"realesrgan-ncnn-vulkan.exe"
MODELS=ROOT/"engine"/"models"
Image.MAX_IMAGE_PIXELS=None

JOBS={}
LOCK=threading.Lock()
def upd(j,**fields):
 with LOCK:JOBS[j].update(fields)
def worker(j,raw,scale,mode,model):
 import time,math
 began=time.monotonic()
 def check():
  if JOBS[j]["cancel"]:raise InterruptedError("Cancelado")
 try:
  upd(j,stage="Leyendo imagen",pct=1,last_activity=time.time(),log=["Archivo recibido"])
  with Image.open(io.BytesIO(raw)) as source:
   im=ImageOps.exif_transpose(source);im.load()
  if im.mode not in ("RGB","RGBA"):im=im.convert("RGBA" if "A" in im.getbands() else "RGB")
  w,h=im.size;target=(w*scale,h*scale)
  tile=256 if mode=="ia" else 512
  cols=math.ceil(w/tile);rows=math.ceil(h/tile);total=cols*rows
  upd(j,stage="Preparando %d bloques"%total,tiles_total=total,tiles_done=0,pct=2,size=list(target))
  output=Image.new(im.mode,target)
  # Vista previa proporcional al lienzo, actualizada al completar cada bloque.
  factor=min(1,1000/max(target))
  psize=(max(1,round(target[0]*factor)),max(1,round(target[1]*factor)))
  preview=Image.new("RGB",psize,(33,40,55))
  preview_path=BASE/("mejora_"+j[:12]+"_partial.png")
  modelname="realesrgan-x4plus" if model=="foto" else "realesrgan-x4plus-anime"
  with tempfile.TemporaryDirectory() as temp:
   for y in range(rows):
    for x in range(cols):
     check()
     n=y*cols+x+1
     x0=x*tile;y0=y*tile;x1=min(w,x0+tile);y1=min(h,y0+tile)
     # Margen común para reducir marcas de unión en bordes.
     pad=12 if mode=="ia" else 0
     a=max(0,x0-pad);b=max(0,y0-pad);c=min(w,x1+pad);d=min(h,y1+pad)
     src_tile=im.crop((a,b,c,d))
     upd(j,stage="Procesando bloque %d de %d"%(n,total),current_tile=n,last_activity=time.time())
     if mode=="ia":
      src=Path(temp)/"in.png";src_tile.save(src)
      stages=1 if scale<=4 else (2 if scale<=16 else 3)
      for st in range(stages):
       check()
       dst=Path(temp)/("step%d.png"%st)
       cmd=[str(ENGINE),"-i",str(src),"-o",str(dst),"-n",modelname,"-m",str(MODELS),"-s","4","-t","32","-f","png"]
       p=subprocess.Popen(cmd,cwd=str(ENGINE.parent),stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
       upd(j,proc=p,stage="Bloque %d/%d: IA etapa %d/%d"%(n,total,st+1,stages))
       data,err=p.communicate()
       upd(j,proc=None)
       check()
       if p.returncode!=0 or not dst.is_file():raise RuntimeError("Error de IA bloque %d: "%n+(err or data).decode("utf-8","replace")[-400:])
       src=dst
      with Image.open(src) as pp:piece=pp.copy()
     else:piece=src_tile
     # Escalado final a la dimensión exacta solicitada.
     piece=piece.resize(((c-a)*scale,(d-b)*scale),Image.Resampling.LANCZOS)
     piece=piece.crop(((x0-a)*scale,(y0-b)*scale,(x1-a)*scale,(y1-b)*scale))
     output.paste(piece,(x0*scale,y0*scale))
     pbox=(round(x0*scale*factor),round(y0*scale*factor),round(x1*scale*factor),round(y1*scale*factor))
     if pbox[2]>pbox[0] and pbox[3]>pbox[1]:
      preview.paste(piece.convert("RGB").resize((pbox[2]-pbox[0],pbox[3]-pbox[1]),Image.Resampling.BILINEAR),pbox[:2])
     # Publicar una vista previa por cada bloque; el archivo es pequeño.
     prevtmp=preview_path.with_suffix(".tmp")
     preview.save(prevtmp,format="PNG");os.replace(prevtmp,preview_path)
     elapsed=time.monotonic()-began;remaining=(elapsed/n)*(total-n) if n else None
     event="Bloque %d/%d completado"%(n,total)
     with LOCK:
      previous=JOBS[j].get("log",[])
     upd(j,stage=event,pct=round(2+90*n/total,1),tiles_done=n,last_activity=time.time(),eta=round(remaining) if remaining is not None else None,preview="/partial/"+preview_path.name,preview_revision=n,log=(previous+[event])[-14:])
     check()
   upd(j,stage="Guardando PNG completo",pct=94,last_activity=time.time())
   fn="mejora_"+uuid.uuid4().hex[:12]+".png";dest=BASE/fn
   output.save(dest)
   check()
  upd(j,state="done",stage="Finalizado",pct=100,url="/download/"+fn,preview="/preview/"+fn,size=list(target),eta=0)
 except InterruptedError as e:upd(j,state="cancelled",stage="Cancelado",error=str(e))
 except Exception as e:upd(j,state="error",stage="Error",error=str(e))
 finally:upd(j,proc=None)

class Handler(BaseHTTPRequestHandler):
 def send(self,code,body,typ="application/json"):
  if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode("utf-8")
  self.send_response(code);self.send_header("Content-Type",typ);self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path=="/":return self.send(200,(ROOT/"index.html").read_bytes(),"text/html; charset=utf-8")
  if self.path.startswith("/job/"):
   jid=self.path.rsplit("/",1)[-1]
   with LOCK:
    v=JOBS.get(jid)
    data={k:x for k,x in v.items() if k not in ("proc","cancel")} if v else None
   return self.send(200,data) if data is not None else self.send(404,{"error":"No existe"})
  if self.path=="/status":return self.send(200,{"ia":ENGINE.is_file() and MODELS.is_dir(),"destino":str(BASE),"version":updater.VERSION})
  if self.path=="/update/check":
   try:return self.send(200,updater.check())
   except Exception as e:return self.send(200,{"available":False,"message":"No se pudo buscar la actualización: "+str(e)})

  if self.path.startswith("/partial/"):
   name=self.path.split("/")[-1].split("?")[0]
   p=BASE/name
   if not name.startswith("mejora_") or not name.endswith("_partial.png") or not p.is_file():return self.send(404,{"error":"No disponible"})
   return self.send(200,p.read_bytes(),"image/png")
  if self.path.startswith("/preview/"):
   name=self.path.split("/")[-1]
   p=BASE/name
   if not name.startswith("mejora_") or not name.endswith(".png") or not p.is_file():return self.send(404,{"error":"No encontrado"})
   with Image.open(p) as preview:
    preview.thumbnail((1500,1000),Image.Resampling.LANCZOS)
    buf=io.BytesIO();preview.save(buf,format="PNG")
   return self.send(200,buf.getvalue(),"image/png")
  if self.path.startswith("/download/"):
   name=self.path.split("/")[-1]
   p=BASE/name
   if not name.startswith("mejora_") or not name.endswith(".png") or not p.is_file():return self.send(404,{"error":"No encontrado"})
   return self.send(200,p.read_bytes(),"image/png")
  return self.send(404,{"error":"No encontrado"})
 def do_POST(self):
  try:
   if self.path=="/update/install":
    with LOCK:
     if any(v["state"]=="running" for v in JOBS.values()):raise ValueError("Esperá a que termine el procesamiento antes de actualizar")
    info=updater.check()
    if not info.get("available"):raise ValueError(info.get("message","No hay versión nueva"))
    if not getattr(sys,"frozen",False):raise ValueError("La actualización requiere el EXE compilado")
    updater.install(info,sys.executable)
    self.send(200,{"ok":True,"message":"Actualización descargada. Reiniciando..."})
    threading.Timer(1.5,lambda:os._exit(0)).start()
    return
   if self.path.startswith("/cancel/"):
    jid=self.path.rsplit("/",1)[-1]
    with LOCK:
     v=JOBS.get(jid)
     if not v:return self.send(404,{"error":"No existe"})
     v["cancel"]=True
     p=v.get("proc")
     if p is not None and p.poll() is None:p.kill()
    return self.send(200,{"ok":True})
   if self.path!="/process":return self.send(404,{"error":"No encontrado"})
   n=int(self.headers.get("Content-Length",0))
   if n<1:raise ValueError("Imagen vacía")
   scale=int(self.headers.get("X-Scale","4"))
   mode=self.headers.get("X-Mode","fiel")
   model=self.headers.get("X-Model","foto")
   if scale not in (2,4,8,16,32) or mode not in ("fiel","ia") or model not in ("foto","ilustracion"):raise ValueError("Opciones inválidas")
   raw=self.rfile.read(n);jid=uuid.uuid4().hex
   with LOCK:JOBS[jid]={"state":"running","stage":"Iniciando","pct":0,"cancel":False,"proc":None,"last_activity":__import__("time").time(),"log":[],"tiles_done":0,"tiles_total":0}
   threading.Thread(target=worker,args=(jid,raw,scale,mode,model),daemon=True).start()
   return self.send(200,{"job":jid})
  except Exception as e:return self.send(400,{"error":str(e)})
 def log_message(self,*args):pass
if __name__=="__main__":
 server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
 port=server.server_port
 threading.Timer(0.6,lambda:webbrowser.open(f"http://127.0.0.1:{port}/")).start()
 server.serve_forever()
