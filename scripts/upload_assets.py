"""One-time Direct Upload with a short-lived project JWT, received on hidden stdin."""
import base64,getpass,hashlib,json,mimetypes
from pathlib import Path
import requests
root=Path(__file__).resolve().parents[1]
jwt=getpass.getpass('Pages upload token (hidden): ')
assets=[];manifest={}
for p in sorted((root/'dist').iterdir()):
    if not p.is_file() or p.name.startswith('_'):continue
    raw=p.read_bytes();key=hashlib.sha256(raw+p.suffix.encode()).hexdigest()[:32]
    manifest['/'+p.name]=key
    assets.append(dict(key=key,value=base64.b64encode(raw).decode(),base64=True,metadata={'contentType':mimetypes.guess_type(p.name)[0] or 'application/octet-stream'}))
r=requests.post('https://api.cloudflare.com/client/v4/pages/assets/upload',json=assets,headers={'Authorization':'Bearer '+jwt},timeout=120)
d=r.json()
if not d.get('success'): raise RuntimeError(str({'status':r.status_code,'errors':d.get('errors')}))
(root/'deployment-manifest.json').write_text(json.dumps(manifest))
print('Uploaded',len(assets),'assets successfully')
