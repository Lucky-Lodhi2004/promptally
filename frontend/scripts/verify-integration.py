"""Build and smoke-test Next/FastAPI using a disposable database and local ports 8045/3055."""
import os,sys,tempfile,shutil,subprocess,time,json,hashlib,base64
from urllib.parse import urlsplit, parse_qs
from pathlib import Path
import httpx
repo=Path(__file__).resolve().parents[2]
root=Path(tempfile.mkdtemp(prefix='promptally-full-integration-'))
frontend=root/'frontend'
shutil.copytree(repo/'frontend',frontend,ignore=shutil.ignore_patterns('node_modules','.next','.env','.env.local','*.tsbuildinfo'))
(frontend/'node_modules').symlink_to(repo/'frontend/node_modules',target_is_directory=True)
python=str(repo/'backend/venv/bin/python')
env=os.environ.copy()
env.update(DATABASE_URL=f'sqlite:///{root}/test.db',UPLOAD_DIR=str(root/'uploads'),PRIVATE_STORAGE_DIR=str(root/'private'),
 ENVIRONMENT='development',SITE_URL='http://127.0.0.1:3055',RATE_LIMIT_READ_PER_MINUTE='1000',RATE_LIMIT_PER_MINUTE='1000',
 API_INTERNAL_URL='http://127.0.0.1:8045/api/v1',NEXT_PUBLIC_SITE_URL='http://127.0.0.1:3055',NEXT_TELEMETRY_DISABLED='1',
 PYTHONPATH=str(repo), RATE_LIMIT_ENABLED='false', REDIS_URL='')
seed=r'''
from backend.app.db.session import Base,engine,SessionLocal
from backend.app.models import User,Asset,Section,Category
from backend.app.models.enums import UserTier,AssetType
from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from pathlib import Path
Base.metadata.create_all(engine)
with SessionLocal() as db:
 user=User(id='integration-admin',email='integration@example.com',username='integration',name='Integration',tier=UserTier.ADMIN,email_verification_required=False,google_sub='mock-integration-google-subject')
 section=Section(id='section',slug='prompts',name='Prompts',description='Test prompts')
 category=Category(id='category',section_id='section',slug='system',name='System')
 db.add_all([user,section,category]);db.flush()
 for paid,slug,content in [(False,'free-blueprint','FREE_BLUEPRINT_SOURCE'),(True,'paid-blueprint','PROTECTED_PAID_SOURCE')]:
  db.add(Asset(id=slug,slug=slug,seo_title=f'{slug} title',short_description='An integration description',asset_type=AssetType.PROMPT,
   raw_content=content,file_name=slug+'.md',file_extension='.md',author_id=user.id,section_id='section',category_id='category',
   is_paid=paid,price_cents=500 if paid else 0,media_preview_url='/uploads/media/preview.png'))
 db.commit()
 print(create_access_token(user.id))
media=settings.UPLOAD_DIR/'media';media.mkdir(parents=True,exist_ok=True);(media/'preview.png').write_bytes(b'integration-media')
'''
token=subprocess.check_output([python,'-c',seed],env=env,cwd=repo,text=True).strip()
print('Building isolated frontend:',frontend,flush=True)
subprocess.run(['npm','run','build'],cwd=frontend,env=env,check=True)
logs=[];processes=[]
def launch(args,cwd,name):
 log=open(root/(name+'.log'),'w');logs.append(log)
 process=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(process)
def wait(client,url):
 for _ in range(100):
  try:
   response=client.get(url)
   if response.status_code < 500:return
  except httpx.HTTPError:pass
  time.sleep(.2)
 raise RuntimeError('Service failed to start: '+url)
try:
 launch([python,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8045','--no-proxy-headers'],repo,'backend')
 launch(['node',str(frontend/'node_modules/next/dist/bin/next'),'start','-p','3055','-H','127.0.0.1'],frontend,'frontend')
 with httpx.Client(timeout=20,trust_env=False) as client:
  base='http://127.0.0.1:3055'
  wait(client,'http://127.0.0.1:8045/api/v1/health');wait(client,base+'/')
  for path,content_type in [('/directory','text/html'),('/llms.txt','text/markdown'),('/sitemap.xml','application/xml'),('/.well-known/mcp.json','application/json'),('/p/free-blueprint.md','text/markdown')]:
   response=client.get(base+path)
   assert response.status_code==200,(path,response.status_code,response.text[:300])
   assert content_type in response.headers['content-type'],(path,response.headers)
   print('PASS route',path,flush=True)
  resource=base+'/api/v1/mcp'
  assert client.get(base+'/.well-known/oauth-protected-resource').json()['resource']==resource
  assert client.get(base+'/.well-known/oauth-protected-resource/api/v1/mcp').json()['resource']==resource
  metadata=client.get(base+'/.well-known/oauth-authorization-server').json()
  callback='http://127.0.0.1:8765/callback'
  registration=client.post(metadata['registration_endpoint'],json={'client_name':'Integration editor','redirect_uris':[callback]})
  assert registration.status_code==201,registration.text
  cid=registration.json()['client_id']
  verifier='v'*64
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
  response=client.get(metadata['authorization_endpoint'],params={'client_id':cid,'redirect_uri':callback,
   'response_type':'code','code_challenge':challenge,'code_challenge_method':'S256','resource':resource,'state':'smoke-test'})
  assert response.status_code==303,response.text
  consent_url=response.headers['location']
  response=client.get(consent_url)
  assert response.status_code==200 and 'Connect to Promptally' in response.text
  handle=parse_qs(urlsplit(consent_url).query)['request'][0]
  consent_api=base+'/api/v1/oauth/requests/'+handle
  assert client.get(consent_api).json()['client_name']=='Integration editor'
  response=client.post(consent_api,json={'approved':True},headers={'Authorization':'Bearer '+token})
  assert response.status_code==200,response.text
  query=parse_qs(urlsplit(response.json()['redirect_url']).query)
  assert query['state']==['smoke-test']
  response=client.post(metadata['token_endpoint'],data={'grant_type':'authorization_code','client_id':cid,
   'code':query['code'][0],'code_verifier':verifier,'redirect_uri':callback,'resource':resource})
  assert response.status_code==200,response.text
  mcp_token=response.json()['access_token']
  message={'jsonrpc':'2.0','id':1,'method':'tools/list'}
  assert client.post(resource,json=message).status_code==401
  assert client.post(resource,json=message,headers={'Authorization':'Bearer '+token}).status_code==401
  response=client.post(resource,json=message,headers={'Authorization':'Bearer '+mcp_token})
  assert response.status_code==200 and len(response.json()['result']['tools'])==3,response.text
  print('PASS MCP consent page, OAuth discovery/exchange and protected tools through Next proxy',flush=True)
  response=client.get(base+'/p/free-blueprint')
  assert response.status_code==200
  assert 'free-blueprint title' in response.text and 'FREE_BLUEPRINT_SOURCE' in response.text
  assert 'application/ld+json' in response.text and 'rel="canonical"' in response.text
  print('PASS server-rendered asset body, title, canonical and JSON-LD',flush=True)
  response=client.get(base+'/p/paid-blueprint')
  assert response.status_code==200 and 'PROTECTED_PAID_SOURCE' not in response.text
  response=client.get(base+'/p/paid-blueprint',headers={'Cookie':'access_token=Bearer '+token})
  assert response.status_code==200 and 'PROTECTED_PAID_SOURCE' in response.text
  assert 'no-store' in response.headers.get('cache-control','')
  print('PASS paid SSR paywall and authenticated no-store response',flush=True)
  response=client.get(base+'/uploads/media/preview.png')
  assert response.status_code==200 and response.content==b'integration-media'
  print('PASS uploaded media through same-origin proxy',flush=True)
  headers={'Authorization':'Bearer '+token}
  response=client.get(base+'/api/v1/assets/paid-blueprint/download?action=copy',headers=headers)
  assert response.status_code==200 and response.text=='PROTECTED_PAID_SOURCE'
  assert client.get(base+'/api/v1/assets/paid-blueprint/download').status_code==403
  print('PASS authenticated paid copy and anonymous denial through proxy',flush=True)
  response=client.post(base+'/api/v1/collections',headers=headers,data={'title':'Integration','visibility':'PUBLIC'})
  assert response.status_code==201,response.text
  collection=response.json();collection_id=collection['collection_id']
  response=client.post(base+f'/api/v1/collections/{collection_id}/items',headers=headers,data={'asset_id':'free-blueprint'})
  assert response.status_code==200,response.text
  detail=client.get(base+'/api/v1/collections/'+collection['slug'],headers=headers).json()
  assert detail['items'][0]['asset_id']=='free-blueprint'
  response=client.delete(base+f'/api/v1/collections/{collection_id}/items/free-blueprint',headers=headers)
  assert response.status_code==200,response.text
  print('PASS collection create/add/read/remove through proxy',flush=True)
 print('PASS all frontend/backend integration checks; temporary databases only.',flush=True)
finally:
 for process in processes:
  process.terminate()
 for process in processes:
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 for log in logs:log.close()
 print('Integration artifacts:',root,flush=True)
