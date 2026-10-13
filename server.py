import io, os, sys, uuid, tempfile, subprocess, threading, webbrowser, json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageOps
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
 try:
  upd(j,stage="Leyendo imagen",pct=5)
  with Image.open(io.BytesIO(raw)) as source:
   im=ImageOps.exif_transpose(source);im.load()
  target=(im.width*scale,im.height*scale)
  if im.mode not in ("RGB","RGBA"):im=im.convert("RGBA" if "A" in im.getbands() else "RGB")
  with tempfile.TemporaryDirectory() as tmp:
   if mode=="ia":
    if not ENGINE.is_file():raise RuntimeError("Motor IA no encontrado")
    src=Path(tmp)/"in.png";im.save(src)
    name="realesrgan-x4plus" if model=="foto" else "realesrgan-x4plus-anime"
    steps=1 if scale<=4 else (2 if scale<=16 else 3)
    for i in range(steps):
     if JOBS[j]["cancel"]:raise InterruptedError("Cancelado")
     upd(j,stage="IA etapa %d/%d"%(i+1,steps),pct=15+int(55*i/steps))
     dst=Path(tmp)/("out%d.png"%i)
     cmd=[str(ENGINE),"-i",str(src),"-o",str(dst),"-n",name,"-m",str(MODELS),"-s","4","-t","32","-f","png"]
     p=subprocess.Popen(cmd,cwd=str(ENGINE.parent),stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
     upd(j,proc=p)
     out,err=p.communicate()
     upd(j,proc=None)
     if JOBS[j]["cancel"]:raise InterruptedError("Cancelado")
     if p.returncode!=0 or not dst.exists():raise RuntimeError((err or out).decode("utf-8","replace")[-500:])
     src=dst
    with Image.open(src) as result:im=result.copy()
   if JOBS[j]["cancel"]:raise InterruptedError("Cancelado")
   upd(j,stage="Ampliando",pct=76)
   im=im.resize(target,Image.Resampling.LANCZOS)
   if JOBS[j]["cancel"]:raise InterruptedError("Cancelado")
   upd(j,stage="Guardando PNG",pct=90)
   fn="mejora_"+uuid.uuid4().hex[:12]+".png"
   dest=BASE/fn;im.save(dest)
   if JOBS[j]["cancel"]:
    dest.unlink(missing_ok=True);raise InterruptedError("Cancelado")
  upd(j,state="done",stage="Finalizado",pct=100,url="/download/"+fn,preview="/preview/"+fn,size=list(target))
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
  if self.path=="/status":return self.send(200,{"ia":ENGINE.is_file() and MODELS.is_dir(),"destino":str(BASE)})
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
   with LOCK:JOBS[jid]={"state":"running","stage":"Iniciando","pct":0,"cancel":False,"proc":None}
   threading.Thread(target=worker,args=(jid,raw,scale,mode,model),daemon=True).start()
   return self.send(200,{"job":jid})
  except Exception as e:return self.send(400,{"error":str(e)})
 def log_message(self,*args):pass
if __name__=="__main__":
 server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
 port=server.server_port
 threading.Timer(0.6,lambda:webbrowser.open(f"http://127.0.0.1:{port}/")).start()
 server.serve_forever()
