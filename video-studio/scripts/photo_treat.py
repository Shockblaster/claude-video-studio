#!/usr/bin/env python3
"""The 'photo never looks flat' recipe from chrismoran__: fringe blur, film dust, vignette; slow zoom happens in the composition. usage: photo_treat.py IN OUT.jpg [--w 1296 --h 2304] [--tone warm|cool|mono] (system python)
Also writes OUT_dust_N.png: dust and scratch overlays to flip through at 12 fps with screen blend. Overscan by 20% so the camera can push."""
import argparse,os,numpy as np,cv2
from PIL import Image
a=argparse.ArgumentParser();a.add_argument('inp');a.add_argument('out');a.add_argument('--w',type=int,default=1296);a.add_argument('--h',type=int,default=2304);a.add_argument('--tone',default='warm');a.add_argument('--focus',default='.5,.45');a.add_argument('--dust',type=int,default=8);x=a.parse_args()
R=np.random.default_rng(5);im=cv2.imread(x.inp).astype(np.float32);H,W=im.shape[:2];s=max(x.w/W,x.h/H);im=cv2.resize(im,(int(W*s)+1,int(H*s)+1),interpolation=cv2.INTER_LANCZOS4)
fx,fy=[float(v) for v in x.focus.split(',')];H,W=im.shape[:2];l=int((W-x.w)*fx);t=int((H-x.h)*fy);im=im[t:t+x.h,l:l+x.w]
y,xx=np.mgrid[0:x.h,0:x.w];d=np.hypot((xx-x.w*fx)/(x.w*.5),(y-x.h*fy)/(x.h*.5))
# fringe blur: sharp subject, soft frame, blend widens with distance
m=np.clip((d-.45)/.7,0,1)[...,None]**1.4;bl=cv2.GaussianBlur(im,(0,0),max(x.w,x.h)*.012);o=im*(1-m)+bl*m
# grade
g=o.mean(2,keepdims=True);T={'warm':(.92,1.0,1.08),'cool':(1.08,1.0,.93),'mono':(1,1,1)}[x.tone];sat=0 if x.tone=='mono' else .85;o=(g+(o-g)*sat)*np.array(T,np.float32)[None,None];o=np.clip((o-128)*1.12+128,0,255)
# vignette, then fine grain
o=o*(1-.55*np.clip(d-.55,0,1.2)[...,None]**1.6);o=o+R.normal(0,3.2,o.shape[:2]+(1,));cv2.imwrite(x.out,np.clip(o,0,255).astype(np.uint8),[cv2.IMWRITE_JPEG_QUALITY,92])
base=os.path.splitext(x.out)[0]
for k in range(x.dust):
    L=np.zeros((x.h//2,x.w//2),np.float32)
    for _ in range(R.integers(25,70)):
        px=(int(R.integers(0,x.w//2)),int(R.integers(0,x.h//2)));cv2.circle(L,px,int(R.integers(1,3)),float(R.uniform(.25,.9)),-1,cv2.LINE_AA)
    for _ in range(R.integers(2,6)):
        a0=(int(R.integers(0,x.w//2)),int(R.integers(0,x.h//2)));pts=[a0]
        for _i in range(R.integers(3,8)):pts.append((pts[-1][0]+int(R.normal(0,14)),pts[-1][1]+int(R.normal(0,14))))
        cv2.polylines(L,[np.array(pts,np.int32)],False,float(R.uniform(.3,.8)),1,cv2.LINE_AA)
    if R.random()<.5:
        c=int(R.integers(0,x.w//2));cv2.line(L,(c,0),(c+int(R.normal(0,6)),x.h//2),float(R.uniform(.1,.3)),1,cv2.LINE_AA)
    L=cv2.GaussianBlur(L,(0,0),.7);rgba=np.dstack([np.full(L.shape,235,np.uint8)]*3+[(L*255).astype(np.uint8)])
    Image.fromarray(rgba,'RGBA').resize((x.w,x.h),Image.BILINEAR).save(f'{base}_dust_{k}.png')
print(x.out)
