import urllib.request
from compression import zstd
u="https://huggingface.co/datasets/linrock/bullet-training-data/resolve/main/S2/test77nov-unfilt-test79-maraprmay-v6-dd.skip-see-ge0.wdl-pdist.iter-1.bullet.bin.zst"
N=64*1024*1024
raw=urllib.request.urlopen(urllib.request.Request(u,headers={"Range":f"bytes=0-{N-1}"})).read()
d=zstd.ZstdDecompressor(); out=d.decompress(raw)
out=out[:len(out)//32*32]
open("s2_prefix.bin","wb").write(out)
print(len(raw),len(out),len(out)//32)
