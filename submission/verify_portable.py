# SPDX-License-Identifier: MIT
"""Exercise the built portable executable with no Python available on PATH."""
import base64
from hashlib import sha256
import io
import zipfile
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from robustband import __version__
from robustband.storage import write_json_atomic
from robustband.decision import EXAMPLE, EXAMPLE_MAPPING, EXAMPLE_PLAN


def main():
    name='robustband-%s-windows-x64'%__version__
    with tempfile.TemporaryDirectory(prefix='robustband-portable-') as location:
        base=Path(location)/'中文 路径'; base.mkdir()
        folder=base/name; shutil.copytree(ROOT/'dist'/name,folder)
        exe=folder/(name+'.exe')
        env=dict(os.environ,PATH=os.environ['SystemRoot']+'\\System32',PYTHONPATH='',PYTHONHOME='')
        def run(*args):
            result=subprocess.run([str(exe)]+list(args),cwd=base,env=env,capture_output=True,timeout=30)
            assert result.returncode==0,result.stderr.decode('utf-8','replace')
            return result.stdout.decode('utf-8','replace')
        start=time.perf_counter(); assert run('--version').strip()==__version__
        cold=time.perf_counter()-start
        checked=['version in path containing Unicode and spaces; system-only PATH']
        fixtures=base/'fixtures'
        prepared=subprocess.run([sys.executable,'-S',str(ROOT/'experiments/import_fixtures.py'),str(fixtures)],capture_output=True)
        assert prepared.returncode==0, prepared.stderr.decode('utf-8','replace')
        import_cases=json.loads((fixtures/'cases.json').read_text(encoding='utf-8'))
        for domain in ('text','scores','segmentation'):
            run('demo','--domain',domain,'--output',domain)
            run('verify',domain+'/report.json')
            checked.append(domain+' demo and exact replay')
        for filename,value in [('paired.csv',EXAMPLE),('mapping.json',json.dumps(EXAMPLE_MAPPING)),('plan.json',json.dumps(EXAMPLE_PLAN))]:
            (base/filename).write_text(value,encoding='utf-8')
        run('decision','paired.csv','--plan','plan.json','--mapping','mapping.json','--output','decision')
        run('verify','decision/report.json')
        run('convert','paired.csv','--domain','scores','--mapping','mapping.json','--output','standard.jsonl')
        assert json.loads((base/'standard.jsonl.manifest.json').read_text(encoding='utf-8'))['roundtrip_verified']
        (base/'models.csv').write_text('sample_id,model,gold,output\ns,a,42,42\ns,b,42,7\n',encoding='utf-8')
        run('matrix','models.csv','--output','ranking'); run('verify','ranking/report.json')
        checked+=['adoption check and replay','validated conversion and manifest','ranking and replay']
        for edition in ('professional','generalized'):
            process=subprocess.Popen([str(exe),'--edition',edition,'ui','--no-browser'],cwd=base,env=env,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                launch=process.stdout.readline().decode('utf-8').strip()
                match=re.search(r'127\.0\.0\.1:(\d+)/#(\S+)',launch); assert match,launch
                port=int(match[1]); token=match[2]
                def request(route,payload=None):
                    client=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                    headers={'X-Robustband-Token':token,'Content-Type':'application/json'}
                    client.request('GET' if payload is None else 'POST',route,None if payload is None else json.dumps(payload),headers)
                    response=client.getresponse(); body=response.read(); assert response.status==200,(route,body)
                    client.close(); return body
                options=json.loads(request('/api/options'))
                assert options['edition']==edition
                assert len(options['domains'])==(1 if edition=='professional' else 3)
                for page in ('/','/decision','/matrix'): assert b'<!doctype html>' in request(page)
                example=json.loads(request('/api/decision/example'))
                payload=dict(text=example['text'],format=example['format'],mapping=example['mapping'],plan=example['plan'])
                assert json.loads(request('/api/decision/audit',payload))['report']['schema']=='robustband.decision/v1'
                for case in import_cases:
                    files=[{'name':Path(filename).name,'data':base64.b64encode(Path(filename).read_bytes()).decode('ascii')} for filename in case['files']]
                    imported=json.loads(request('/api/import',{'files':files}))
                    report=imported['report']
                    band=report['pairs'][0]['exact_band'] if case.get('matrix') else report['result']['exact_band']
                    assert report['result']['n_items']==case['n'] and band==case['band'],case['name']
                    with zipfile.ZipFile(io.BytesIO(base64.b64decode(imported['bundle_base64']))) as archive:
                        assert archive.read('report.json').decode('utf-8')==imported['json']
                        assert sha256(archive.read('report.json')).hexdigest()==imported['manifest']['report_json_sha256']
                    checked.append(edition+' portable import and replay bundle: '+case['name'])
                assert json.loads(request('/api/stop',{}))['stopped']
                assert process.wait(timeout=5)==0
                checked.append(edition+' HTTP pages, isolation, exact decision and clean stop')
            finally:
                if process.poll() is None: process.kill(); process.wait()
    receipt={'schema':'robustband.portable_acceptance/v1','version':__version__,'checks':checked,'passed':len(checked),
        'first_version_command_seconds':round(cold,4),'python_on_PATH':False,'unicode_and_space_path':True,
        'executable_sha256':sha256((ROOT/'dist'/name/(name+'.exe')).read_bytes()).hexdigest(),
        'source_sha256_lf':{str(p.relative_to(ROOT)).replace('\\','/'):sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for p in (Path(__file__),ROOT/'submission/build_portable.py',ROOT/'submission/portable_entry.py')},
        'scope':'Executed portable core with system-only PATH on this Windows host. Not a virtual machine or a separate physical host.'}
    write_json_atomic(ROOT/'results'/('portable_acceptance_%s.json'%__version__), receipt)
    print('PASS: %d portable checks, no Python on PATH'%len(checked))


if __name__=='__main__': main()
