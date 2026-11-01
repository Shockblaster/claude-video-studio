#!/usr/bin/env python
"""See how a reel moves: frame cadence, camera moves, easing, transitions, stillness, plus motion images.
usage: study_motion.py VIDEO OUTDIR   (run with ~/video-studio/venv/bin/python -I)"""
import sys,os,json,warnings;warnings.filterwarnings('ignore')
import numpy as np,cv2
vid,out=sys.argv[1:3];os.makedirs(out,exist_ok=True)
cap=cv2.VideoCapture(vid);fps=cap.get(5) or 30;W0,H0=int(cap.get(3)),int(cap.get(4))
W=180;Hh=int(round(W*H0/W0/2))*2
dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
ys,xs=np.mgrid[6:Hh-6:8,6:W-6:8];pts=np.stack([xs.ravel(),ys.ravel()],1).astype(np.float32)
TX,TY=6,10;tile_h=Hh//TY;tile_w=W//TX
rows=[];slit_v=[];slit_h=[];prev=None;tile_change=[];G=[]
i=0
while True:
    ok,f=cap.read()
    if not ok:break
    g=cv2.cvtColor(cv2.resize(f,(W,Hh),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2GRAY)
    slit_v.append(cv2.resize(f,(W,Hh),interpolation=cv2.INTER_AREA)[:,W//2].copy());slit_h.append(cv2.resize(f,(W,Hh),interpolation=cv2.INTER_AREA)[Hh//2,:].copy())
    r={'lum':float(g.mean())};G.append(g)
    if prev is not None:
        d=np.abs(g.astype(np.int16)-prev.astype(np.int16))
        r['change']=float((d>10).mean());r['mad']=float(d.mean())
        tiles=np.array([[d[y*tile_h:(y+1)*tile_h,x*tile_w:(x+1)*tile_w].mean() for x in range(TX)] for y in range(TY)]);tile_change.append(tiles)
        fl=dis.calc(prev,g,None)
        dx=fl[...,0][pts[:,1].astype(int),pts[:,0].astype(int)];dy=fl[...,1][pts[:,1].astype(int),pts[:,0].astype(int)]
        M,inl=cv2.estimateAffinePartial2D(pts,pts+np.stack([dx,dy],1),method=cv2.RANSAC,ransacReprojThreshold=1.0,maxIters=120,refineIters=2)
        if M is not None:
            sc=float(np.hypot(M[0,0],M[1,0]));rot=float(np.arctan2(M[1,0],M[0,0]));cx,cy=W/2,Hh/2
            tx=float(M[0,0]*cx+M[0,1]*cy+M[0,2]-cx);ty=float(M[1,0]*cx+M[1,1]*cy+M[1,2]-cy);inr=float(inl.mean()) if inl is not None else 0
            # warp error after the camera move tells a real move from a cut
            warp=cv2.warpAffine(prev,M,(W,Hh),borderMode=cv2.BORDER_REPLICATE);res=np.abs(g.astype(np.int16)-warp.astype(np.int16))
            r.update(zoom=sc-1,rot=rot,tx=tx,ty=ty,inlier=inr,warp_err=float(res.mean()),move_frac=float((res>12).mean()))
        else:r.update(zoom=0,rot=0,tx=0,ty=0,inlier=0,warp_err=float(d.mean()),move_frac=float((d>12).mean()))
        mag=np.hypot(fl[...,0],fl[...,1]);mv=mag>.5;r['resid_p90']=float(np.percentile(np.hypot(dx-(M[0,0]*pts[:,0]+M[0,1]*pts[:,1]+M[0,2]-pts[:,0]),dy-(M[1,0]*pts[:,0]+M[1,1]*pts[:,1]+M[1,2]-pts[:,1])),90)) if M is not None else 0.;r['ex']=float(np.median(fl[...,0][mv])) if mv.sum()>30 else 0.;r['ey']=float(np.median(fl[...,1][mv])) if mv.sum()>30 else 0.;r['flow_med']=float(np.median(mag));r['flow_p95']=float(np.percentile(mag,95))
        lap=cv2.Laplacian(g,cv2.CV_32F);r['sharp']=float(lap.var())
    prev=g;rows.append(r);i+=1
cap.release()
n=len(rows);T=np.arange(n)/fps
A=lambda k:np.array([rows[j].get(k,0.) for j in range(n)])
ch,mad,zoom,tx,ty,inl,werr,mf,lum,fm,fp,sh,ex,ey,rp=[A(k) for k in ('change','mad','zoom','tx','ty','inlier','warp_err','move_frac','lum','flow_med','flow_p95','sharp','ex','ey','resid_p90')]
res={'fps':round(fps,2),'dur':round(n/fps,2),'w':W0,'h':H0}
# ---- scene changes: the picture 10 frames later is a different picture, then read how that change happened
GG=np.stack(G).astype(np.int16);L=5
Dw=np.zeros(n)
for k in range(L,n-L):
    Dw[k]=float((np.abs(GG[k+L]-GG[k-L])>22).mean())
# a hard cut is one frame that changes most of the picture while its neighbours do not
CUT_CORR=float(os.environ.get('CUT_CORR','.72'))
hard=[]
for k in range(1,n-1):
    if ch[k]>.3 and ch[k]>2.5*max(ch[k-1],ch[k+1],.02) and werr[k]>6:
        # a real cut replaces the picture; a stepped animation frame moves parts of the same picture
        A_,B_=GG[k-1].astype(np.float32).ravel(),GG[k].astype(np.float32).ravel()
        if float(np.corrcoef(A_,B_)[0,1])<CUT_CORR:hard.append(k)
pk=[]
for k in range(L,n-L):
    if any(abs(k-h)<=L+1 for h in hard):continue
    if Dw[k]>=.42 and Dw[k]==Dw[max(0,k-L):k+L+1].max():
        if not pk or k-pk[-1]>2*L:pk.append(k)
def classify(k):
    # the whole change is the run of frames around k where something happens
    a=k;b=k
    th=max(1.0,float(np.median(mad))*2.5)
    while a>max(1,k-int(.6*fps)) and mad[a]>th:a-=1
    while b<min(n-1,k+int(.6*fps)) and mad[b]>th:b+=1
    if b<=a:b=a+1
    seg=mad[a:b+1];tot=seg.sum()+1e-6;top=seg.max()/tot;length=(b-a)/fps
    if top>.62 or length<=2/fps:return 'hard cut',k if seg.argmax() is None else a+int(seg.argmax()),length
    lw=lum[a:b+1];ref=(lum[max(0,a-3)]+lum[min(n-1,b+3)])/2
    if lw.min()<min(14,ref*.35):return 'via black',k,length
    if lw.max()>max(232,ref*1.5):return 'flash or white',k,length
    gm=float(np.median(np.hypot(tx[a:b+1],ty[a:b+1])+np.abs(zoom[a:b+1])*W*.5));f95=float(np.median(fp[a:b+1]))
    if inl[a:b+1].mean()>.45 and gm>2.5:return 'whip or zoom',k,length
    if f95>10:return 'push or whip',k,length
    return 'dissolve or wipe',k,length
tr=[classify(k) for k in pk]+[('hard cut',h,1/fps) for h in hard]
tr=sorted(tr,key=lambda x:x[1])
# fade out and fade in around black are one transition
mg=[]
for t in tr:
    if mg and t[0] in('via black','flash or white') and mg[-1][0]==t[0] and t[1]-mg[-1][1]<int(.8*fps):continue
    mg.append(t)
tr=mg
cut=sorted({t[1] for t in tr if t[0]=='hard cut'})
res['cuts']=[round(k/fps,3) for k in cut];res['cuts_per_10s']=round(len(cut)/(n/fps)*10,1)
all_changes=sorted(t[1] for t in tr);sh_=np.diff(np.r_[0,all_changes,n])/fps;sh_=sh_[sh_>0]
res['shot_median_s']=round(float(np.median(sh_)),2);res['shot_p10_s']=round(float(np.percentile(sh_,10)),2);res['shot_p90_s']=round(float(np.percentile(sh_,90)),2)
res['shot_variety']=round(float(np.std(np.log(sh_+.03))),2)
# ---- cadence: how often the moving picture truly updates, tile by tile (animation on ones, twos, threes)
tc=np.array(tile_change);tc=np.concatenate([np.zeros((1,)+tc.shape[1:]),tc]);noise=np.percentile(tc,20,axis=0,keepdims=True)
active=tc>np.maximum(noise*2.5,.9)
# a tile is in motion in a window if at least 25% of its frames changed. Inside such windows, measure the runs of held frames
hist={}
fastf=np.convolve((fp>1.0).astype(float),np.ones(int(fps/2)|1),'same')>.15
for y in range(TY):
    for x in range(TX):
        a=active[:,y,x];m=np.convolve(a.astype(float),np.ones(9)/9,'same')>.2
        e=np.flatnonzero(a&m&fastf)
        if len(e)<8:continue
        gaps=np.diff(e);gaps=gaps[gaps<=8]
        for v,c in zip(*np.unique(gaps,return_counts=True)):hist[int(v)]=hist.get(int(v),0)+int(c)
tot=sum(hist.values()) or 1;res['cadence_hist_pct']={k:round(hist[k]/tot*100,1) for k in sorted(hist)};res['cadence_samples']=sum(hist.values())
mean_step=sum(k*v for k,v in hist.items())/tot if hist else 1;res['effective_fps']=round(fps/mean_step,1) if sum(hist.values())>=40 else None
res['on_ones_pct']=round(hist.get(1,0)/tot*100,1);res['on_twos_or_more_pct']=round(100-hist.get(1,0)/tot*100,1)
# whole-picture holds: frames where nothing at all changed
res['frozen_frames_pct']=round(float((mad[1:]<.25).mean()*100),1)
# ---- stillness and camera drift
moving=(fm>.04)|(mf>.01);res['dead_still_pct']=round(float((~moving[1:]).mean()*100),1)
camz=np.abs(zoom)>.0004;camt=np.hypot(tx,ty)>.08;good=inl>.5
res['camera_moving_pct']=round(float(((camz|camt)&good)[1:].mean()*100),1)
res['camera_zoom_pct']=round(float((camz&good)[1:].mean()*100),1)
res['zoom_in_vs_out']=round(float((zoom[camz&good]>0).mean()),2) if (camz&good).any() else None
# ---- moves: continuous camera or element moves, speed profile, easing class
sp=np.hypot(tx,ty)+np.abs(zoom)*W*.5
sp_el=fp.copy()
cutset=set(cut)
def segs(v,th,minf):
    m=v>th;e=np.flatnonzero(np.diff(np.r_[0,m.astype(int),0]));return [(e[i],e[i+1]) for i in range(0,len(e),2) if e[i+1]-e[i]>=minf]
def shape(v):
    """Where the speed peaks and how the end behaves. Time and speed scaled 0..1."""
    v=np.convolve(v,[.25,.5,.25],'same');pk=int(v.argmax());L=len(v);tp=pk/(L-1) if L>1 else 0
    area=np.cumsum(v)/(v.sum()+1e-9);t50=int(np.searchsorted(area,.5))/(L-1) if L>1 else .5
    return tp,t50
moves=[];src=fp if False else sp
th=max(.25,float(np.percentile(fp,60)))
for a,b in segs(fp,th,4):
    if any(a<=c<=b for c in cut):continue
    if b-a>int(2.5*fps):continue
    v=fp[a:b];tp,t50=shape(v)
    # did the picture go past and come back? velocity sign reversal in the dominant direction near the end
    ux,uy=float(np.median(ex[a:b])),float(np.median(ey[a:b]));nn=np.hypot(ux,uy)+1e-6;ux,uy=ux/nn,uy/nn
    pr=ex[b:min(n,b+14)]*ux+ey[b:min(n,b+14)]*uy;over=bool((pr<-.25).sum()>=2)
    flat=float(np.convolve(v,[.25,.5,.25],'same').mean()/(v.max()+1e-6))
    cls='ease-out' if t50<.38 else ('ease-in' if t50>.62 else ('linear' if flat>.75 else 'ease-in-out'))
    moves.append({'t':round(a/fps,2),'dur':round((b-a)/fps,3),'peak':round(float(v.max()),2),'t50':round(t50,2),'flat':round(flat,2),'class':cls,'overshoot':over})
res['moves']=moves;res['moves_per_10s']=round(len(moves)/(n/fps)*10,1)
if moves:
    from collections import Counter
    c=Counter(m['class'] for m in moves);res['ease_mix_pct']={k:round(v/len(moves)*100) for k,v in c.items()}
    res['move_dur_median_s']=round(float(np.median([m['dur'] for m in moves])),3);res['move_t50_median']=round(float(np.median([m['t50'] for m in moves])),2);res['overshoot_pct']=round(float(np.mean([m['overshoot'] for m in moves])*100),1)
from collections import Counter
res['transitions']=[{'t':round(t[1]/fps,3),'kind':t[0],'len':round(float(t[2]),3)} for t in tr]
res['transition_mix']=dict(Counter(t[0] for t in tr));res['transitions_per_10s']=round(len(tr)/(n/fps)*10,1)
res['transition_median_len_s']=round(float(np.median([t[2] for t in tr if t[0]!='hard cut'])),2) if any(t[0]!='hard cut' for t in tr) else None
# motion blur: sharpness while fast vs while slow, same shot
fast=fp>np.percentile(fp,80);slow=fp<np.percentile(fp,40)
ok=np.ones(n,bool);ok[[c for c in cut if c<n]]=False
if (fast&ok).sum()>5 and (slow&ok).sum()>5:res['sharp_fast_vs_slow']=round(float(np.median(sh[fast&ok])/(np.median(sh[slow&ok])+1e-6)),2)
# energy over time, for the reel's arc
sec=int(n/fps);res['motion_arc']=[round(float(np.median(fp[int(s*fps):int((s+1)*fps)])),2) for s in range(sec)]
res['energy_first3s_vs_rest']=round(float(fp[:int(3*fps)].mean()/(fp[int(3*fps):].mean()+1e-6)),2)
# ---- images I can read: time slices. Time runs left to right, rows are the centre column of the frame.
sv=np.stack(slit_v,1);S=cv2.resize(sv,(min(2400,n*3),Hh*2),interpolation=cv2.INTER_NEAREST);cv2.imwrite(f'{out}/slice_vertical.jpg',S,[cv2.IMWRITE_JPEG_QUALITY,82])
np.savez_compressed(f'{out}/motion_env.npz',fp=fp.astype(np.float32),fm=fm.astype(np.float32),change=ch.astype(np.float32),zoom=zoom.astype(np.float32),tx=tx.astype(np.float32),ty=ty.astype(np.float32),lum=lum.astype(np.float32),werr=werr.astype(np.float32),mad=mad.astype(np.float32),resid=rp.astype(np.float32),inlier=inl.astype(np.float32))
json.dump(res,open(f'{out}/motion.json','w'))
print('ok',os.path.basename(out),'effective',res['effective_fps'],'changes/10s',res['transitions_per_10s'],'still',res['dead_still_pct'],'cam',res['camera_moving_pct'],'ease',res.get('ease_mix_pct'))
