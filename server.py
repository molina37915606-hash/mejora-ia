import io, os, sys, uuid, tempfile, subprocess, threading, webbrowser, json, time, math, shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import updater
ROOT=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
ENGINE=ROOT/"engine"/"realesrgan-ncnn-vulkan.exe"
MODELS=ROOT/"engine"/"models"
Image.MAX_IMAGE_PIXELS=None
WORK=Path(tempfile.mkdtemp(prefix="zompix_"))
HISTORY_DIR=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"Zompix"/"Historial"
HISTORY_DIR.mkdir(parents=True,exist_ok=True)
HISTORY_FILE=HISTORY_DIR/"trabajos.json"
def get_history():
 try:return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))[:150]
 except (OSError,ValueError):return []
def save_history(rows):
 tmp=HISTORY_FILE.with_suffix(".tmp")
 tmp.write_text(json.dumps(rows[:150],ensure_ascii=False),encoding="utf-8")
 os.replace(tmp,HISTORY_FILE)
def record(j,settings):
 try:
  with LOCK:
   item=JOBS[j]
   row={"id":j,"date":time.strftime("%Y-%m-%d %H:%M"),"state":item["state"],"size":item.get("size"),"settings":settings,"name":settings.get("name","Imagen")}
   img=WORK/(j+"_preview.png")
   if img.exists():
    with Image.open(img) as thumb:
     thumb.thumbnail((220,160))
     thumb.convert("RGB").save(HISTORY_DIR/(j+".jpg"),quality=75,optimize=True)
   rows=get_history();rows.insert(0,row);save_history(rows)
 except Exception:pass
JOBS={}
LOCK=threading.RLock()
def upd(j,**fields):
 with LOCK:JOBS[j].update(fields)
def active(j):
 if JOBS[j]["cancel"]:raise InterruptedError("Proceso cancelado")
def run_job(j,raw,scale,mode,model,intensity,priority,settings):
 try:
  upd(j,stage="Leyendo imagen",pct=1,log=["Imagen cargada"])
  with Image.open(io.BytesIO(raw)) as incoming:
   im=ImageOps.exif_transpose(incoming)
   im.load()
  if im.mode not in ("RGB","RGBA"):im=im.convert("RGBA" if "A" in im.getbands() else "RGB")
  width,height=im.size
  target=(width*scale,height*scale)
  # Fiel prioriza forma y color. IA sólo pasa una vez por x4.
  use_ai=(mode=="ia")
  if use_ai and not ENGINE.is_file():raise RuntimeError("Motor de IA no disponible")
  tile=192 if use_ai else 256
  cols=math.ceil(width/tile);rows=math.ceil(height/tile)
  total=cols*rows
  upd(j,tiles_total=total,tiles_done=0,size=list(target),stage="Preparando bloques",pct=2)
  out=Image.new(im.mode,target)
  preview_factor=min(1,1000/max(target))
  preview_size=(max(1,round(target[0]*preview_factor)),max(1,round(target[1]*preview_factor)))
  overview=Image.new("RGB",preview_size,(22,27,41))
  modelname="realesrgan-x4plus" if model=="foto" else "realesrgan-x4plus-anime"
  began=time.monotonic()
  durations=[]
  with tempfile.TemporaryDirectory(prefix="zompix_tiles_") as scratch:
   for y in range(rows):
    for x in range(cols):
     active(j)
     block_began=time.monotonic()
     index=y*cols+x+1
     x0=x*tile;y0=y*tile;x1=min(width,x0+tile);y1=min(height,y0+tile)
     margin=12 if use_ai else 0
     a=max(0,x0-margin);b=max(0,y0-margin);c=min(width,x1+margin);d=min(height,y1+margin)
     section=im.crop((a,b,c,d))
     upd(j,stage=f"Mejorando bloque {index}/{total}",last_activity=time.time())
     if use_ai:
      source=Path(scratch)/"input.png";destination=Path(scratch)/"output.png"
      section.save(source)
      cmd=[str(ENGINE),"-i",str(source),"-o",str(destination),"-n",modelname,"-m",str(MODELS),"-s","4","-t","32","-f","png"]
      proc=subprocess.Popen(cmd,cwd=str(ENGINE.parent),stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
      upd(j,proc=proc)
      stdout,stderr=proc.communicate()
      upd(j,proc=None)
      active(j)
      if proc.returncode!=0 or not destination.exists():
       raise RuntimeError("IA, bloque "+str(index)+": "+(stderr or stdout).decode("utf-8","replace")[-450:])
      with Image.open(destination) as result: section=result.copy()
      if intensity!='fuerte':
       baseline=im.crop((a,b,c,d)).resize(section.size,Image.Resampling.LANCZOS)
       if baseline.mode!=section.mode:baseline=baseline.convert(section.mode)
       strength=0.48 if intensity=='suave' else 0.76
       if priority=='detalles':strength*=0.85
       section=Image.blend(baseline,section,strength)
      if priority=='detalles':section=section.filter(ImageFilter.UnsharpMask(radius=1.1,percent=65,threshold=3))
     # Para x2 se reduce desde x4 IA; para x8+ se escala una vez de x4,
     # sin repetir IA para inventar detalles.
     needed=((c-a)*scale,(d-b)*scale)
     if section.size!=needed:section=section.resize(needed,Image.Resampling.LANCZOS)
     section=section.crop(((x0-a)*scale,(y0-b)*scale,(x1-a)*scale,(y1-b)*scale))
     out.paste(section,(x0*scale,y0*scale))
     box=(round(x0*scale*preview_factor),round(y0*scale*preview_factor),round(x1*scale*preview_factor),round(y1*scale*preview_factor))
     if box[2]>box[0] and box[3]>box[1]:
      overview.paste(section.convert("RGB").resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.BILINEAR),box[:2])
     # Una vista liviana, evitando enviar original y resultado completos.
     if index==1 or index==total or index%max(1,total//25)==0:
      destination=WORK/(j+"_preview.png")
      temporary=WORK/(j+"_preview.tmp")
      overview.save(temporary,format="PNG")
      os.replace(temporary,destination)
      upd(j,preview="/preview/"+j,revision=index)
     durations.append(time.monotonic()-block_began)
     elapsed=time.monotonic()-began
     recent=(JOBS[j].get("log") or [])[-9:]
     event=f"Bloque {index}/{total} completado"
     upd(j,stage=event,pct=round(2+92*index/total,1),tiles_done=index,eta=round((sum(durations[-5:])/len(durations[-5:]))*(total-index)),last_activity=time.time(),log=recent+[event])
   active(j)
   upd(j,stage="Preparando exportación temporal",pct=95,last_activity=time.time())
   result_path=WORK/(j+"_full.png")
   out.save(result_path,format="PNG")
   active(j)
   overview.save(WORK/(j+"_preview.png"))
  upd(j,state="done",stage="Lista para exportar",pct=100,preview="/preview/"+j,revision=total+1,size=list(target),eta=0)
 except InterruptedError as e:
  upd(j,state="cancelled",stage="Cancelado",error=str(e))
 except Exception as e:
  upd(j,state="error",stage="Error",error=str(e))
 finally:
  upd(j,proc=None)
  record(j,settings)
  if JOBS[j]["state"]!="done":
   for suffix in ("_full.png","_preview.png","_preview.tmp"):
    (WORK/(j+suffix)).unlink(missing_ok=True)
class Handler(BaseHTTPRequestHandler):
 def reply(self,status,content,content_type="application/json"):
  if not isinstance(content,bytes):content=json.dumps(content,ensure_ascii=False).encode("utf-8")
  self.send_response(status);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(content)));self.end_headers();self.wfile.write(content)
 def do_GET(self):
  if self.path=="/":return self.reply(200,(ROOT/"index.html").read_bytes(),"text/html; charset=utf-8")
  if self.path=="/brand.svg":return self.reply(200,(ROOT/"brand.svg").read_bytes(),"image/svg+xml")
  if self.path=="/history":return self.reply(200,{"items":get_history()})
  if self.path.startswith("/history/thumb/"):
   key=self.path.rsplit("/",1)[-1]
   if not any(x["id"]==key for x in get_history()):return self.reply(404,{"error":"No existe"})
   p=HISTORY_DIR/(key+".jpg")
   return self.reply(200,p.read_bytes(),"image/jpeg") if p.is_file() else self.reply(404,{"error":"Sin vista previa"})
  if self.path=="/status":return self.reply(200,{"version":updater.VERSION,"ia":ENGINE.exists(),"name":"Zompix"})
  if self.path=="/update/check":
   try:return self.reply(200,updater.check())
   except Exception as e:return self.reply(200,{"available":False,"message":str(e)})
  if self.path.startswith("/job/"):
   j=self.path.rsplit("/",1)[-1]
   with LOCK:
    item=JOBS.get(j)
    data={k:v for k,v in item.items() if k not in ("proc","cancel")} if item else None
   return self.reply(200,data) if data else self.reply(404,{"error":"No encontrado"})
  if self.path.startswith("/preview/"):
   j=self.path.rsplit("/",1)[-1].split("?")[0]
   if j not in JOBS:return self.reply(404,{"error":"No encontrado"})
   p=WORK/(j+"_preview.png")
   if not p.exists():return self.reply(404,{"error":"No disponible"})
   return self.reply(200,p.read_bytes(),"image/png")
  if self.path.startswith("/export/"):
   j=self.path.rsplit("/",1)[-1]
   if j not in JOBS or JOBS[j]["state"]!="done":return self.reply(404,{"error":"Resultado no disponible"})
   p=WORK/(j+"_full.png")
   if not p.exists():return self.reply(404,{"error":"Resultado temporal no disponible"})
   self.send_response(200);self.send_header("Content-Type","image/png")
   self.send_header("Content-Disposition",'attachment; filename="Zompix_'+j[:8]+'.png"')
   self.send_header("Content-Length",str(p.stat().st_size));self.end_headers()
   with p.open("rb") as infile:shutil.copyfileobj(infile,self.wfile,1024*1024)
   return
  return self.reply(404,{"error":"No encontrado"})
 def do_POST(self):
  try:
   if self.path.startswith("/history/delete/"):
    key=self.path.rsplit("/",1)[-1]
    with LOCK:
     rows=get_history()
     if key=="all":
      ids=[r["id"] for r in rows];save_history([])
     else:
      ids=[key];save_history([r for r in rows if r["id"]!=key])
     for ident in ids:(HISTORY_DIR/(ident+".jpg")).unlink(missing_ok=True)
    return self.reply(200,{"ok":True})
   if self.path=="/update/install":
    with LOCK:
     if any(i["state"]=="running" for i in JOBS.values()):raise ValueError("Terminá el procesamiento antes de actualizar")
    info=updater.check()
    if not info.get("available"):raise ValueError(info.get("message","No hay actualización"))
    updater.install(info,sys.executable)
    self.reply(200,{"ok":True});threading.Timer(1.5,lambda:os._exit(0)).start();return
   if self.path.startswith("/cancel/"):
    j=self.path.rsplit("/",1)[-1]
    with LOCK:
     item=JOBS.get(j)
     if not item:return self.reply(404,{"error":"No encontrado"})
     item["cancel"]=True
     proc=item.get("proc")
     if proc and proc.poll() is None:proc.kill()
    return self.reply(200,{"ok":True})
   if self.path.startswith("/discard/"):
    j=self.path.rsplit("/",1)[-1]
    with LOCK:
     item=JOBS.get(j)
     if not item or item["state"]=="running":raise ValueError("El trabajo no está finalizado")
     JOBS.pop(j)
    for suffix in ("_full.png","_preview.png"):
     (WORK/(j+suffix)).unlink(missing_ok=True)
    return self.reply(200,{"ok":True})
   if self.path!="/process":return self.reply(404,{"error":"No encontrado"})
   length=int(self.headers.get("Content-Length",0))
   if length<=0:raise ValueError("No se recibió imagen")
   scale=int(self.headers.get("X-Scale","4"))
   mode=self.headers.get("X-Mode","fiel")
   model=self.headers.get("X-Model","foto")
   intensity=self.headers.get("X-Intensity","normal")
   priority=self.headers.get("X-Priority","equilibrado")
   if scale not in (2,4,8,16,32) or mode not in ("fiel","ia") or model not in ("foto","ilustracion") or intensity not in ("suave","normal","fuerte") or priority not in ("detalles","equilibrado","suave"):raise ValueError("Opciones incorrectas")
   settings={"scale":scale,"mode":mode,"model":model,"intensity":intensity,"priority":priority,"name":self.headers.get("X-Filename","Imagen")[:120],"kind":self.headers.get("X-Kind","poster"),"dpi":self.headers.get("X-Dpi","150"),"sample":self.headers.get("X-Sample","false")=="true"}
   raw=self.rfile.read(length)
   j=uuid.uuid4().hex
   with LOCK:JOBS[j]={"state":"running","pct":0,"stage":"Iniciando","cancel":False,"proc":None,"tiles_done":0,"tiles_total":0,"log":[],"last_activity":time.time()}
   threading.Thread(target=run_job,args=(j,raw,scale,mode,model,intensity,priority,settings),daemon=True).start()
   return self.reply(200,{"job":j})
  except Exception as e:return self.reply(400,{"error":str(e)})
 def log_message(self,*args):pass
if __name__=="__main__":
 import atexit
 atexit.register(lambda:shutil.rmtree(WORK,ignore_errors=True))
 http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
 threading.Timer(0.6,lambda:webbrowser.open("http://127.0.0.1:"+str(http.server_port)+"/")).start()
 http.serve_forever()
