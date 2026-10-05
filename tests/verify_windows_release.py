"""Manual Windows integration check for the built portable ZIP (isolated backend)."""
import argparse,concurrent.futures,json,os,shutil,socket,subprocess,time,urllib.request,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--venv',action='store_true',help='Also exercise Windows venv redirector cold startup')
options=parser.parse_args()
import uuid
folder=root/'.runtime/release-verification'/('发布验证 空格 '+uuid.uuid4().hex)
folder.mkdir(parents=True)
archive=root/'.runtime/releases/PlasticityAssetTool-windows-x64.zip'
with zipfile.ZipFile(archive) as z:
 assert not any('/library/' in n or '/.runtime/' in n or '/.venv/' in n or '/node_modules/' in n for n in z.namelist())
 z.extractall(folder)
package=folder/'PlasticityAssetTool'
config=json.loads((package/'config.json').read_text(encoding='utf8'))
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
config['server']['http_port']=port
config['plasticity']['cdp_endpoints']=[]
(package/'config.json').write_text(json.dumps(config),encoding='utf8')
exe=package/'PlasticityAssetTool.exe'
python=package/'runtime/python/python.exe'
if options.venv:
 # Exercise the source checkout launcher path, with its Windows redirector
 # spawning a child Python PID. The bundled path remains the default check.
 (package/'runtime/python').rename(package/'runtime/bundled-unused')
 shutil.copytree(root/'.venv',package/'.venv',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 python=package/'.venv/Scripts/python.exe'

opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def request(path,body=None):
 data=None if body is None else json.dumps(body).encode()
 return json.load(opener.open(urllib.request.Request('http://127.0.0.1:'+str(port)+path,data=data,headers={'Content-Type':'application/json'}),timeout=5))
def launch():
 # Use only packaged Python, never the developer runtime or environment.
 env=dict(os.environ);env.pop('PYTHONPATH',None);env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
 probe=subprocess.check_output([str(python),'-c',
   'import json,sys,tornado; print(json.dumps([sys.prefix,tornado.__file__]))'],env=env,cwd=root/'.runtime')
 assert all(Path(path).resolve().is_relative_to(package.resolve()) for path in json.loads(probe))
 started=time.monotonic()
 result=subprocess.run([str(exe),'--headless'],cwd=root/'.runtime',env=env,timeout=50,creationflags=subprocess.CREATE_NO_WINDOW)
 assert result.returncode==0,(result.returncode,(package/'.runtime/launcher.log').read_text(encoding='utf-8-sig'))
 return round(time.monotonic()-started,2)
try:
 cold=launch();owner=json.loads((package/'.runtime/backend-instance.json').read_text())
 assert request('/api/health')['app']=='plasticity-asset-tool'
 assert request('/api/service')['component_count']==0
 assert request('/api/service')['tray_available']
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:repeats=list(pool.map(lambda _:launch(),range(3)))
 assert json.loads((package/'.runtime/backend-instance.json').read_text())['pid']==owner['pid']
 print(json.dumps({'cold_start_seconds':cold,'concurrent_reuse_seconds':repeats,'single_instance_pid':owner['pid'],'port':port,'packaged_runtime':not options.venv,'venv_redirector':options.venv},ensure_ascii=False))
finally:
 try:request('/api/service',{'action':'service.quit'})
 except Exception:pass
 deadline=time.monotonic()+10
 while (package/'.runtime/backend-instance.json').exists() and time.monotonic()<deadline:time.sleep(.1)
 assert not (package/'.runtime/backend-instance.json').exists(),'Test backend must exit cleanly'
