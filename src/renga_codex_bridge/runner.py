"""Bounded synchronous supervisor used by CLI and reproducible native tests."""
import json
import os
import subprocess
import sys
from .ownership import create_ownership_lease,command_timeout_seconds,cleanup_after_timeout
from .audit import event

def run_worker(command,arguments,*,timeout=None):
    limit=command_timeout_seconds(timeout)
    lease=create_ownership_lease()
    process=subprocess.Popen([sys.executable,'-m','renga_codex_bridge.worker'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        text=True,encoding='utf8',env={**os.environ,**lease.environment(),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    try:identity=lease.observe_worker(process.pid)
    except BaseException:
        process.kill();process.wait(timeout=5);raise
    try:
        out,err=process.communicate(json.dumps({'command':command,'arguments':arguments},ensure_ascii=False),
                                    timeout=limit)
    except subprocess.TimeoutExpired:
        process.kill()
        try:process.communicate(timeout=5)
        except subprocess.TimeoutExpired:pass
        cleanup=cleanup_after_timeout(lease,identity)
        event('worker_timeout',status='error',command=command,cleanup=cleanup,outcome='unknown')
        raise TimeoutError('Native worker timed out; saved outcome is unknown. Inspect local logs/backups and reopen the model before retrying.')
    if process.returncode:raise RuntimeError(err)
    return json.loads(out)['result']
