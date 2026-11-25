"""Key-authenticated, bounded SSH transport; uses the user's pinned host aliases."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import shlex
import subprocess
import time

from uart import Cancelled


class SSHConsole:
    def __init__(self, log, transport='ssh-wired'):
        hosts = {'ssh-wired': 'zybo-wired', 'ssh-wifi': 'zybo-wifi'}
        self.transport, self.log = transport, log
        self.args = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                     '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
                     '-o', 'ServerAliveCountMax=3', hosts[transport]]

    def __enter__(self):
        self.command('true')
        return self

    def __exit__(self, *_):
        pass

    def command(self, command, timeout=30):
        result = subprocess.run(self.args + [command], capture_output=True, timeout=timeout)
        self.log.write(result.stdout + result.stderr); self.log.flush()
        if result.returncode:
            raise RuntimeError('Board command failed: ' + result.stderr.decode(errors='replace')[-1200:])
        return result.stdout.decode()

    def upload(self, source, destination, progress=lambda *_: None, cancelled=lambda: False):
        if cancelled():
            raise Cancelled('Cancelled before SSH transfer.')
        data = Path(source).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        # The board checks the bytes before atomically publishing a fresh file.
        code = ('import hashlib,os,sys,tempfile;from pathlib import Path;'
                f'p=Path({destination!r});d=sys.stdin.buffer.read();'
                f'assert hashlib.sha256(d).hexdigest()=={digest!r};'
                'assert not p.exists();fd,t=tempfile.mkstemp(dir=p.parent);'
                'f=os.fdopen(fd,"wb");f.write(d);f.close();'
                'os.link(t,p);os.unlink(t);print(hashlib.sha256(d).hexdigest())')
        result = subprocess.run(self.args + ['python3 -c ' + shlex.quote(code)],
                                input=data, capture_output=True, timeout=90)
        self.log.write(result.stdout + result.stderr); self.log.flush()
        if result.returncode or result.stdout.decode().strip() != digest:
            raise RuntimeError('SSH upload failed its board-side checksum check.')
        progress(len(data), len(data))
        return digest

    def stream(self, command, line, timeout=180):
        process = subprocess.Popen(self.args + [command], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        pending = bytearray(); deadline = time.monotonic() + timeout
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Board SSH job exceeded its bounded deadline.')
                    if not selector.select(min(remaining, 1)):
                        continue
                    block = os.read(process.stdout.fileno(), 65536)
                    if not block:
                        break
                    self.log.write(block); self.log.flush(); pending.extend(block)
                    while b'\n' in pending:
                        value, _, pending = pending.partition(b'\n')
                        line(value.decode(errors='replace'))
                    if len(pending) > 1024 * 1024:
                        raise RuntimeError('Unexpectedly large board response line.')
            if pending:
                line(pending.decode(errors='replace'))
            if process.wait(timeout=5):
                raise RuntimeError('The physical board job failed; inspect its saved SSH log.')
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()

    def agent(self, path, arguments, event):
        state = {'done': False, 'error': None}
        def receive(line):
            if not line.startswith('@ZYBO_DEMO '): return
            message = json.loads(line[len('@ZYBO_DEMO '):]); event(message)
            if message['event'] in ('done', 'error'):
                state['done'] = True
                if message['event'] == 'error': state['error'] = message['message']
        self.stream('ZYBO_DEMO_TRANSPORT=' + self.transport + ' python3 -u ' +
                    shlex.quote(path) + ' ' + arguments, receive)
        if not state['done'] or state['error']:
            raise RuntimeError(state['error'] or 'Board agent did not complete.')
