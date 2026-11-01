#!/usr/bin/env python3
"""Shorten long pauses in a voice take without touching the words. usage: tighten_vo.py IN OUT --max .22 [--keep-last .6] (system python)"""
import argparse,numpy as np,soundfile as sf
from scipy.ndimage import uniform_filter1d
a=argparse.ArgumentParser();a.add_argument('inp');a.add_argument('out');a.add_argument('--max',type=float,default=.22);a.add_argument('--keep-last',type=float,default=.6);x=a.parse_args()
y,sr=sf.read(x.inp,dtype='float32');y=y.mean(1) if y.ndim>1 else y;e=uniform_filter1d(np.abs(y),int(.02*sr));q=e<max(.006,np.percentile(e,90)*.03);d=np.diff(np.r_[0,q.astype(int),0]);S=np.flatnonzero(d==1);E=np.flatnonzero(d==-1);keep=[];p=0;G=[(s,t) for s,t in zip(S,E) if (t-s)/sr>x.max]
for i,(s,t) in enumerate(G):
    m=x.keep_last if i==len(G)-2 else x.max;n=int(m*sr)
    if t-s<=n:continue
    keep.append(y[p:s+n//2]);p=t-(n-n//2)
keep.append(y[p:]);o=np.concatenate(keep)
sf.write(x.out,o,sr);print(round(len(y)/sr,1),'->',round(len(o)/sr,1))
