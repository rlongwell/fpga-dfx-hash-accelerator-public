#!/usr/bin/env python3
"""Explicit physical acceptance through the running local dashboard API."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--transport', choices=('usb-uart','ssh-wired','ssh-wifi'), default='usb-uart')
    args = parser.parse_args()

    def request(path, body=None, **headers):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(args.url + '/api/' + path, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    token = request('bootstrap')['token']
    auth = {'X-Demo-Token': token}
    report = dict(kind='physical-dashboard-api-acceptance', hardware_tested=True,
                  started_utc=datetime.now(timezone.utc).isoformat(), jobs=[])

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')

    def run(payload, cancel=False):
        file = request('files', payload, **auth, **{'X-File-Name':"test%20%27%3B%24.dat"})
        ident = request('jobs', {'file_id':file['id'], 'transport':args.transport, 'algorithms':['sha3','sha256','blake2s']}, **auth)['id']
        deadline = time.monotonic() + 240
        previous, cancelled = None, False
        while time.monotonic() < deadline:
            job = request('jobs/' + ident)
            if job['stage'] != previous:
                print(len(payload), job['stage'], flush=True); previous = job['stage']
            if cancel and not cancelled and job.get('bytes_sent', 0) > 0:
                request('cancel', {}, **auth); cancelled = True
            if job['state'] != 'running': break
            time.sleep(.2)
        else:
            request('cancel', {}, **auth)
            raise TimeoutError('Physical demo acceptance timed out.')
        report['jobs'].append(job); save()
        if cancel:
            assert cancelled and job['state'] == 'cancelled', job
            return
        assert job['state'] == 'passed', job
        assert job['restored_sha3'] and job['upload_verified']
        assert len(job['results']) == 3
        for result in job['results']:
            reference = {'sha3':hashlib.sha3_256,'sha256':hashlib.sha256,'blake2s':hashlib.blake2s}[result['algorithm']](payload).hexdigest()
            assert result['digest'] == reference == result['reference_digest']
            assert result['backend'] == 'physical-fpga-dma'
            assert result['dma_transfers'] == (len(payload)+1048575)//1048576
        assert job['results'][1]['manager_load_ns'] > 0
        assert job['results'][2]['manager_load_ns'] > 0
        assert job['board']['profile_env_sha256'] == '9dc14825fb83ef1fe366b1a2a9451395d67a966a0800ad4a4a9289dc612f46fc'

    try:
        run(bytes(range(256))*1024, cancel=True)
        for length in (0, 137, 1048593):
            run((bytes(range(256))*((length+255)//256))[:length])
        report['passed'] = True
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
        raise
    finally:
        report['completed_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print('PASS: cancellation recovery, empty/boundary/multi-buffer inputs, all engines, SHA3/service restoration.', flush=True)


if __name__ == '__main__': main()
