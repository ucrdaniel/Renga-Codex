"""Deliberately stop one owned native test worker and confirm bounded cleanup."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from renga_codex_bridge.config import settings
from renga_codex_bridge.ownership import create_ownership_lease,register_worker_identity,cleanup_after_timeout
from renga_codex_bridge.session import Session
from renga_codex_bridge.safety import fingerprint
from renga_codex_bridge.audit import event
from renga_codex_bridge.runner import run_worker

def worker():
    request=json.load(sys.stdin);register_worker_identity()
    with Session(request['project']):
        Path(request['ready']).write_text('owned-native-session-ready',encoding='utf8')
        time.sleep(120)

def run():
    folder=settings().write_root/('timeout-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));folder.mkdir(parents=True)
    project=folder/'model.rnp'
    result=run_worker('apply',{'project':str(project),'new':True,'operations':json.loads((ROOT/'examples/rectangle.json').read_text(encoding='utf8'))})
    before=fingerprint(project);ready=folder/'ready.txt';lease=create_ownership_lease()
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              text=True,encoding='utf8',env={**os.environ,**lease.environment()})
    identity=lease.observe_worker(process.pid)
    process.stdin.write(json.dumps({'project':str(project),'ready':str(ready)}));process.stdin.close()
    deadline=time.monotonic()+45
    while not ready.exists() and time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError(process.stderr.read())
        time.sleep(0.1)
    if not ready.exists():
        process.kill();process.wait(timeout=5);cleanup_after_timeout(lease,identity)
        raise TimeoutError('Probe worker did not establish its owned native session')
    process.kill();process.wait(timeout=5)
    cleanup=cleanup_after_timeout(lease,identity)
    assert not cleanup['refused'] and len(cleanup['terminated'])==1 and cleanup['outcome']=='unknown'
    assert fingerprint(project)==before
    reopened=run_worker('inspect',{'project':str(project),'details':False,'limit':100})
    assert {row['uuid'] for row in result['objects']}=={row['uuid'] for row in reopened['objects']}
    report={'schema_version':1,'status':'passed','computer_use_calls':0,'checks':[
        {'check':'confirmed_owned_worker_and_renga_termination','status':'passed'},
        {'check':'source_disk_unchanged_after_timeout','status':'passed'},
        {'check':'native_reopen_after_forced_owned_session_failure','status':'passed'}]}
    event('native_timeout_cleanup_verified',outcome='unknown',cleanup=cleanup,computer_use_calls=0)
    (folder/'timeout-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    (ROOT/'runtime/latest-timeout.json').write_text(json.dumps({'evidence_directory':str(folder),'report':report},indent=2),encoding='utf8')
    print('PASS TIMEOUT confirmed own-process cleanup; source unchanged; native reopen',flush=True)
    return report

if __name__=='__main__':worker() if '--worker' in sys.argv else run()
