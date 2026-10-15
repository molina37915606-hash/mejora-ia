"""Genera una biblioteca de demostración local sin conexión.
Si biblioteca_original.zip existe junto al proyecto, incluye las 10 imágenes
originales en su lugar. No se usan imágenes externas en tiempo de ejecución.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import json, math, random, zipfile, io

ROOT=Path(__file__).resolve().parent
DEST=ROOT/"biblioteca_incluida"
MANIFEST=[
 ("portrait","Retrato natural","Fotografía","foto"),
 ("landscape","Paisaje alpino","Fotografía","foto"),
 ("night","Fotografía nocturna","Fotografía","foto"),
 ("animeface","Retrato anime","Anime","ilustracion"),
 ("animescene","Escena anime","Anime","ilustracion"),
 ("branding","Logo y tipografía","Diseño","ilustracion"),
 ("movieposter","Póster cinematográfico","Póster","foto"),
 ("illustratedposter","Póster ilustrado","Póster","ilustracion"),
 ("fabrics","Telas y fibras","Texturas","foto"),
 ("architecture","Arquitectura y materiales","Texturas","foto")
]
def make_image(index):
 random.seed(500+index)
 w,h=1024,1024
 base_colors=[(114,96,100),(37,107,124),(27,23,47),(182,137,181),(83,96,159),(237,240,245),(43,42,56),(117,83,131),(134,95,91),(153,102,82)]
 image=Image.new("RGB",(w,h),base_colors[index]); d=ImageDraw.Draw(image)
 if index==0:
  d.ellipse((210,70,820,850),fill=(219,168,139),outline=(80,47,46),width=14)
  for x,y in [(370,420),(644,420)]:d.ellipse((x-48,y-32,x+48,y+32),fill=(251,251,251));d.ellipse((x-21,y-29,x+21,y+29),fill=(45,72,76))
  d.arc((365,485,660,715),10,170,fill=(129,58,72),width=10)
  for i in range(750):
   x=random.randint(250,780);y=random.randint(145,755)
   if ((x-515)/300)**2+((y-450)/370)**2<1:d.point((x,y),fill=(188,117,107))
 elif index in (1,2,4,6,7):
  for i in range(8):
   y=int(180+i*75)
   points=[(0,y)]+[(x,y+random.randint(-150,140)) for x in range(0,w+80,80)]+[(w,h),(0,h)]
   col=tuple(min(255,max(0,c+(i-3)*10)) for c in base_colors[index])
   d.polygon(points,fill=col)
  for i in range(250):
   x=random.randrange(w);y=random.randrange(h)
   color=(255,200,115) if index in (2,6,7) else (38,85,59)
   d.line((x,y,x+random.randrange(-16,16),y-random.randrange(5,45)),fill=color,width=random.randint(1,4))
 elif index==3:
  d.ellipse((210,90,810,820),fill=(243,205,183),outline=(61,36,86),width=22)
  d.polygon([(200,400),(250,90),(550,130),(850,60),(780,350),(630,290)],fill=(195,210,243))
  for x in (380,634):
   d.ellipse((x-82,388,x+82,480),fill=(251,251,254))
   d.ellipse((x-29,390,x+29,474),fill=(72,93,176))
  d.arc((420,530,610,680),0,180,fill=(170,74,121),width=13)
 elif index==5:
  d.rectangle((85,85,939,939),fill=(248,249,252),outline=(24,54,95),width=5)
  d.polygon([(155,320),(250,145),(335,320),(250,270)],fill=(30,95,229))
  d.text((370,206),"ZOMPIX LAB",fill=(23,45,80),font=ImageFont.load_default())
  for i in range(20):
   y=370+i*22;d.line((130,y,870,y),fill=((37,78,120) if i%3 else (70,155,240)),width=i%4+1)
  for i in range(8):
   d.rectangle((160+i*83,800,194+i*83,845),fill=(i*25,90+i*10,215-i*23))
 elif index==8:
  for i in range(700):
   x=random.randrange(w);y=random.randrange(h);length=random.randrange(20,130)
   col=random.choice([(53,92,148),(210,192,174),(217,142,91),(132,45,69)])
   d.line((x,y,x+length,y+random.randrange(-15,15)),fill=col,width=random.randrange(1,11))
 elif index==9:
  for y in range(0,h,65):
   for x in range(-70 if y//65%2 else 0,w,145):
    d.rectangle((x+3,y+3,x+140,y+60),fill=(165+random.randrange(-20,20),82+random.randrange(-20,20),54),outline=(83,63,51),width=4)
  d.rectangle((550,110,920,880),fill=(52,113,106),outline=(38,42,44),width=20)
  for i in range(110):
   x=random.randrange(550,920);y=random.randrange(110,880)
   d.line((x,y,x+random.randrange(-25,25),y+random.randrange(5,40)),fill=(159,150,115),width=random.randrange(1,5))
 return image

DEST.mkdir(exist_ok=True)
src=ROOT/"biblioteca_original.zip"
if src.exists():
 with zipfile.ZipFile(src) as archive:
  archive.extractall(DEST)
 print("Imágenes originales incluidas")
else:
 for i,(ident,title,category,model) in enumerate(MANIFEST):
  folder=DEST/ident;folder.mkdir(exist_ok=True)
  original=make_image(i)
  for name,pixels in [("original",1024),("medium",512),("low",256),("thumb",160)]:
   im=original.copy()
   im.thumbnail((pixels,pixels),Image.Resampling.LANCZOS)
   im.save(folder/(name+".jpg"),quality=88,optimize=True)
 (DEST/"manifest.json").write_text(json.dumps({"version":1,"items":[{"id":i,"title":n,"category":c,"model":m} for i,n,c,m in MANIFEST]},ensure_ascii=False),encoding="utf-8")
 print("Biblioteca de referencia generada; reemplazable por biblioteca_original.zip")
