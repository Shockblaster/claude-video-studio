#!/usr/bin/env python3
"""Download Hugging Face files safely: resumable with curl, checked against the published SHA-256, retried across sleep and network drops. A file only appears at its final name after it verifies.
usage: hf_get.py REPO DEST [path_prefix ...]   Interrupted hub downloads left corrupt files on 2026-10-30; use this for large models."""
import os,sys,json,hashlib,subprocess,time,urllib.request
repo,dest=sys.argv[1:3];want=sys.argv[3:]
def tree():
    for k in range(40):
        try:return json.load(urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/tree/main?recursive=true',timeout=30))
        except Exception as e:print('tree retry',str(e)[:80],flush=True);time.sleep(30)
    sys.exit('no tree')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<22),b''):h.update(b)
    return h.hexdigest()
fs=[x for x in tree() if x['type']=='file' and (not want or any(x['path'].startswith(w) for w in want))];bad=0
for x in sorted(fs,key=lambda v:v['size']):
    p=os.path.join(dest,x['path']);os.makedirs(os.path.dirname(p),exist_ok=True);oid=(x.get('lfs') or {}).get('oid');size=x['size']
    if os.path.exists(p) and os.path.getsize(p)==size and (not oid or sha(p)==oid):continue
    if os.path.exists(p):os.remove(p)
    t=p+'.part';u=f'https://huggingface.co/{repo}/resolve/main/{x["path"]}'
    for k in range(200):
        if os.path.exists(t) and os.path.getsize(t)>=size:break
        print(f"get {x['path']} {size/1e9:.2f} GB have {(os.path.getsize(t) if os.path.exists(t) else 0)/1e9:.2f}",flush=True)
        subprocess.run(['curl','-sSL','--fail','-C','-','--connect-timeout','30','--speed-time','90','--speed-limit','5000','-o',t,u]);time.sleep(5)
    if oid and sha(t)!=oid:print('SHA MISMATCH',x['path'],flush=True);os.remove(t);bad+=1;continue
    os.replace(t,p);print('ok',x['path'],flush=True)
print('HF_DONE' if not bad else f'HF_BAD {bad}',flush=True)
