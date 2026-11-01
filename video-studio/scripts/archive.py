#!/usr/bin/env python3
"""Find and fetch images we may legally use. Every download gets a sidecar with source and licence, and an entry in the project's licences.md.
search:  archive.py search "dabbawala" [--source met,commons,loc,nasa] [--n 12]
fetch:   archive.py fetch <id from search> --out assets/img [--project DIR]
Sources: The Met (CC0), Smithsonian (CC0; set SI_API_KEY for more than the demo limit), NASA, Wikimedia Commons (only public domain or CC0), Library of Congress ('no known restrictions'). (Ported from a friend's fork 2026-11-02; Commons and LoC were blocked on that network.)
Public domain covers the image, not a real person's publicity rights: check before showing identifiable people in an ad."""
import argparse,json,os,re,sys,urllib.parse,urllib.request,hashlib,html
UA={'User-Agent':'VideoStudio/1.0 (personal research; https://VideoStudio)'}
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)));import _paths
CACHE=os.environ.get('ARCHIVE_CACHE',str(_paths.work_dir('archive-cache')));os.makedirs(CACHE,exist_ok=True)
def get(u,to=25):
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=to))
def met(q,n):
    r=get('https://collectionapi.metmuseum.org/public/collection/v1.1/search?hasImages=true&isPublicDomain=true&q='+urllib.parse.quote(q));o=[]
    for i in (r.get('objectIDs') or [])[:n*3]:
        try:d=get(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{i}')
        except Exception:continue
        if d.get('isPublicDomain') and d.get('primaryImage'):
            o.append({'id':f'met:{i}','title':d.get('title'),'creator':d.get('artistDisplayName'),'date':d.get('objectDate'),'url':d['primaryImage'],'thumb':d.get('primaryImageSmall'),'licence':'CC0 (The Met Open Access)','source':d.get('objectURL')})
        if len(o)>=n:break
    return o
OK=re.compile(r'^(public domain|pd|cc0|cc-zero|no restrictions)',re.I)
def commons(q,n):
    u='https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=%d&gsrsearch=%s&prop=imageinfo&iiprop=url|extmetadata|size|mime&iiurlwidth=800'%(n*4,urllib.parse.quote(q+' filetype:bitmap'))
    p=get(u).get('query',{}).get('pages',{});o=[]
    for x in sorted(p.values(),key=lambda v:v.get('index',0)):
        ii=(x.get('imageinfo') or [{}])[0];m=ii.get('extmetadata',{});lic=m.get('LicenseShortName',{}).get('value','');
        if not OK.match(lic) or ii.get('mime') not in('image/jpeg','image/png','image/tiff'):continue
        o.append({'id':'commons:'+x['title'].replace('File:',''),'title':x['title'],'creator':re.sub('<[^>]+>','',m.get('Artist',{}).get('value',''))[:120],'date':re.sub('<[^>]+>','',m.get('DateTimeOriginal',{}).get('value',''))[:40],'url':ii.get('url'),'thumb':ii.get('thumburl'),'licence':lic,'source':ii.get('descriptionurl'),'size':[ii.get('width'),ii.get('height')]})
        if len(o)>=n:break
    return o
def loc(q,n):
    r=get('https://www.loc.gov/photos/?fo=json&c=%d&q=%s'%(n*3,urllib.parse.quote(q)));o=[]
    for x in r.get('results',[]):
        rs=str(x.get('rights_information') or x.get('rights') or '').lower()
        if 'no known restrictions' not in rs:continue
        im=[u for u in x.get('image_url',[]) if u];
        if not im:continue
        o.append({'id':'loc:'+str(x.get('id','')).rstrip('/').split('/')[-1],'title':x.get('title'),'creator':'','date':x.get('date'),'url':im[-1],'thumb':im[0],'licence':'Library of Congress: no known restrictions','source':x.get('id')})
        if len(o)>=n:break
    return o
def nasa(q,n):
    r=get('https://images-api.nasa.gov/search?media_type=image&q='+urllib.parse.quote(q));o=[]
    for x in r.get('collection',{}).get('items',[])[:n]:
        d=x['data'][0];nid=d['nasa_id'];o.append({'id':'nasa:'+nid,'title':d.get('title'),'creator':d.get('center'),'date':d.get('date_created','')[:10],'url':f'https://images-assets.nasa.gov/image/{urllib.parse.quote(nid)}/{urllib.parse.quote(nid)}~orig.jpg','thumb':x['links'][0]['href'],'licence':'NASA media (generally not copyrighted; no endorsement implied)','source':'https://images.nasa.gov/details/'+nid})
    return o
def smithsonian(q,n):
    key=os.environ.get('SI_API_KEY','DEMO_KEY')
    r=get('https://api.si.edu/openaccess/api/v1.0/search?rows=%d&api_key=%s&q=%s'%(n*4,key,urllib.parse.quote(q+' AND online_media_type:Images')));o=[]
    for x in r.get('response',{}).get('rows',[]):
        c=x.get('content',{});dn=c.get('descriptiveNonRepeating',{});m=(dn.get('online_media') or {}).get('media') or []
        for me in m:
            if (me.get('usage') or {}).get('access')=='CC0' and me.get('type')=='Images':
                u=me.get('content');
                o.append({'id':'si:'+x['id'],'title':x.get('title'),'creator':'','date':((c.get('indexedStructured') or {}).get('date') or [''])[0],'url':u,'thumb':me.get('thumbnail'),'licence':'CC0 (Smithsonian Open Access)','source':dn.get('record_link') or dn.get('guid')});break
        if len(o)>=n:break
    return o
SRC={'met':met,'commons':commons,'loc':loc,'nasa':nasa,'si':smithsonian}
def search(a):
    all_=[]
    for s in a.source.split(','):
        try:r=SRC[s](a.query,a.n)
        except Exception as e:print(f'{s}: {e}',file=sys.stderr);r=[]
        all_+=r
    json.dump({x['id']:x for x in all_},open(CACHE+'/last_search.json','w'),indent=0)
    for x in all_:print(f"{x['id'][:70]:72} {str(x.get('date'))[:14]:15} {x['licence'][:30]:31} {str(x['title'])[:60]}")
    return 0
def fetch(a):
    S=json.load(open(CACHE+'/last_search.json'));x=S.get(a.id)
    if not x:print('id not in last search');return 1
    os.makedirs(a.out,exist_ok=True);ext=os.path.splitext(urllib.parse.urlparse(x['url']).path)[1].lower() or '.jpg';name=re.sub(r'[^\w-]+','_',a.id)[:80]+ext;p=f'{a.out}/{name}'
    data=urllib.request.urlopen(urllib.request.Request(urllib.parse.quote(x['url'],safe=':/?&='),headers=UA),timeout=120).read();open(p,'wb').write(data)
    x['sha256']=hashlib.sha256(data).hexdigest();json.dump(x,open(p+'.json','w'),indent=1)
    if a.project:
        open(a.project+'/licences.md','a').write(f"- {name}: {x['title']} ({x.get('creator') or 'unknown'}, {x.get('date') or 'n.d.'}). {x['licence']}. {x['source']}\n")
    print(p);return 0
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='cmd',required=True)
    x=sp.add_parser('search');x.add_argument('query');x.add_argument('--source',default='met,si,nasa,commons,loc');x.add_argument('--n',type=int,default=8)
    x=sp.add_parser('fetch');x.add_argument('id');x.add_argument('--out',required=True);x.add_argument('--project')
    a=ap.parse_args();sys.exit({'search':search,'fetch':fetch}[a.cmd](a))
