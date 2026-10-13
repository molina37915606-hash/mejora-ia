import io, os, sys, uuid, tempfile, subprocess, threading, webbrowser, json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageOps
ROOT=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
BASE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"MejoraIA"/"Resultados"
BASE.mkdir(parents=True,exist_ok=True)
ENGINE=ROOT/"engine"/"realesrgan-ncnn-vulkan.exe"
MODELS=ROOT/"engine"/"models"
Image.MAX_IMAGE_PIXELS=200_000_000
class Handler(BaseHTTPRequestHandler):
 def send(self,code,body,typ="application/json"):
  if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode("utf-8")
  self.send_response(code);self.send_header("Content-Type",typ);self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path=="/":return self.send(200,(ROOT/"index.html").read_bytes(),"text/html; charset=utf-8")
  if self.path=="/status":return self.send(200,{"ia":ENGINE.is_file() and MODELS.is_dir(),"destino":str(BASE)})
  if self.path.startswith("/download/"):
   name=self.path.split("/")[-1]
   p=BASE/name
   if not name.startswith("mejora_") or not name.endswith(".png") or not p.is_file():return self.send(404,{"error":"No encontrado"})
   return self.send(200,p.read_bytes(),"image/png")
  return self.send(404,{"error":"No encontrado"})
 def do_POST(self):
  try:
   if self.path!="/process":return self.send(404,{"error":"No encontrado"})
   sz=int(self.headers.get("Content-Length",0))
   if sz<1 or sz>40*1024*1024:raise ValueError("Imagen máxima: 40 MB")
   scale=int(self.headers.get("X-Scale","4"));mode=self.headers.get("X-Mode","fiel")
   model=self.headers.get("X-Model","foto")
   if scale not in (2,4,8,16,32) or mode not in ("fiel","ia") or model not in ("foto","ilustracion"):raise ValueError("Opción no válida")
   raw=self.rfile.read(sz)
   with Image.open(io.BytesIO(raw)) as source:
    im=ImageOps.exif_transpose(source)
    im.load()
   target=(im.width*scale,im.height*scale)
   if target[0]>24000 or target[1]>24000 or target[0]*target[1]>40_000_000:raise ValueError("El resultado es demasiado grande para esta PC de 4 GB. Elegí una escala menor.")
   if im.mode not in ("RGB","RGBA"):im=im.convert("RGBA" if "A" in im.getbands() else "RGB")
   with tempfile.TemporaryDirectory() as tmp:
    if mode=="ia":
     if not ENGINE.is_file():raise ValueError("Motor de IA no incluido")
     src=Path(tmp)/"entrada.png";im.save(src)
     name="realesrgan-x4plus" if model=="foto" else "realesrgan-x4plus-anime"
     # Each 4x step can be costly: on 4 GB RAM, deliberately cap final output.
     steps=1 if scale<=4 else (2 if scale<=16 else 3)
     for step in range(steps):
      dst=Path(tmp)/f"paso_{step}.png"
      command=[str(ENGINE),"-i",str(src),"-o",str(dst),"-n",name,"-m",str(MODELS),"-s","4","-t","32","-f","png"]
      p=subprocess.run(command,cwd=str(ENGINE.parent),capture_output=True,text=True,timeout=3600,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
      if p.returncode!=0 or not dst.is_file():raise RuntimeError("Falló IA (posible falta de Vulkan o memoria): "+(p.stderr or p.stdout)[-400:])
      src=dst
     with Image.open(src) as processed:im=processed.copy()
    im=im.resize(target,Image.Resampling.LANCZOS)
    filename="mejora_"+uuid.uuid4().hex[:12]+".png"
    im.save(BASE/filename)
   return self.send(200,{"url":"/download/"+filename,"size":list(target)})
  except Exception as e:return self.send(400,{"error":str(e)})
 def log_message(self,*args):pass
if __name__=="__main__":
 server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
 port=server.server_port
 threading.Timer(0.6,lambda:webbrowser.open(f"http://127.0.0.1:{port}/")).start()
 server.serve_forever()
