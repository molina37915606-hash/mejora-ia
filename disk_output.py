import mmap, struct, zlib
from pathlib import Path

class DiskImage:
 def __init__(self,path,width,height,channels):
  self.width,self.height,self.channels=width,height,channels
  self.path=Path(path);self.stride=width*channels
  self.file=self.path.open("w+b")
  self.file.truncate(self.stride*height)
  self.mm=mmap.mmap(self.file.fileno(),self.stride*height)
 def paste(self,im,x,y):
  if im.mode!=("RGB" if self.channels==3 else "RGBA"):
   im=im.convert("RGB" if self.channels==3 else "RGBA")
  pixels=im.tobytes()
  line=im.width*self.channels
  for row in range(im.height):
   start=(y+row)*self.stride+x*self.channels
   self.mm[start:start+line]=pixels[row*line:(row+1)*line]
 def save(self,path):
  def chunk(fp,kind,data):
   fp.write(struct.pack(">I",len(data)));fp.write(kind);fp.write(data)
   fp.write(struct.pack(">I",zlib.crc32(kind+data)&0xffffffff))
  with open(path,"wb") as fp:
   fp.write(b"\\x89PNG\\r\\n\\x1a\\n")
   chunk(fp,b"IHDR",struct.pack(">IIBBBBB",self.width,self.height,8,2 if self.channels==3 else 6,0,0,0))
   compress=zlib.compressobj(4);pending=bytearray()
   for row in range(self.height):
    start=row*self.stride
    pending.extend(compress.compress(b"\\x00"+self.mm[start:start+self.stride]))
    while len(pending)>1048576:
     chunk(fp,b"IDAT",bytes(pending[:1048576]))
     del pending[:1048576]
   pending.extend(compress.flush())
   while pending:
    chunk(fp,b"IDAT",bytes(pending[:1048576]))
    del pending[:1048576]
   chunk(fp,b"IEND",b"")
 def close(self):
  self.mm.close();self.file.close();self.path.unlink(missing_ok=True)
