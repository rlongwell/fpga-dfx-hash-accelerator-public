#!/usr/bin/env python3
"""Stage a compatible hash bundle; never changes the SD card or demo selection."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-dtb',type=Path,required=True)
    p.add_argument('--dtc',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise RuntimeError('Use a fresh staging directory')
    archive=Path(str(args.output)+'.tar.gz')
    if archive.exists():
        raise RuntimeError('Use a fresh archive filename')
    build=ROOT/'build/gem-direct'
    subprocess.run(['sha256sum','--check',str(build/'ACCEPTED.sha256')],check=True)
    subprocess.run(['sha256sum','--check',str(build/'system/static_sources.sha256')],check=True)
    for name in ('oxide','sha256','blake2s'):
        report=(build/f'dfx/pr_verify_{name}.rpt').read_text()
        if 'compatible' not in report.lower() or 'not compatible' in report.lower():
            raise RuntimeError('Missing successful PR compatibility result: '+name)
    full=build/'dfx/compact/full.bit'
    static=sha(full)
    manifest=dict(abi=65536,part='xc7z020clg400-1',vivado='2024.2',static_sha256=static,
                  images={},initial_full_bit=str(full.relative_to(ROOT)))
    variants=dict(abi=65536,part=manifest['part'],static_sha256=static,variants={},repeats=7,warmup=1)
    out=args.output
    boot=out/'boot/profiles/hash';runtime=out/'rootfs/opt/zybo/hash'
    boot.mkdir(parents=True);(runtime/'net').mkdir(parents=True);(runtime/'software').mkdir()
    for name,algorithm in [('compact',1),('oxide',1),('sha256',2),('blake2s',3)]:
        partial=build/f'dfx/{name}/full_pblock_hash_partial.bit.bin'
        digest=sha(partial)
        filename=f'fpga-dfx-hash/net-{static[:12]}/{name}-{digest[:12]}.bin'
        dest=out/'rootfs/lib/firmware'/filename;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(partial,dest)
        image=dict(algorithm_id=algorithm,filename=filename,source=str(partial.relative_to(ROOT)),sha256=digest)
        if name!='oxide':manifest['images']['sha3' if name=='compact' else name]=image
        if name in ('oxide','compact'):
            variants['variants'][name]=dict(label='Oxide Quartz' if name=='oxide' else 'Compact core',image=image)
    shutil.copyfile(full,boot/'system.bit')
    # Append a separate ingress node to the already validated board DT.
    if sha(args.base_dtb)!='3d2809a8f625f698e720bc6254e9520ceb233d2d3c79192dcfe0933bbe6e25ed':
        raise RuntimeError('Unexpected base DT: preserve the accepted PS/DDR/SD/Ethernet configuration')
    source=subprocess.check_output([str(args.dtc),'-I','dtb','-O','dts',str(args.base_dtb)],text=True)
    source+=f'''\n/ {{ core-forge,static-sha256 = "{static}"; }};
&{{/axi}} {{
    hash-ingress@80000000 {{
        compatible = "core-forge,gem-hash-ingress-1.0";
        reg = <0x80000000 0x40000>;
        clock-frequency = <100000000>;
        core-forge,requires-exclusive-gem;
        status = "okay";
    }};
}};
'''
    (out/'system.dts').write_text(source)
    subprocess.run([str(args.dtc),'-I','dts','-O','dtb','-o',str(boot/'system.dtb'),str(out/'system.dts')],check=True)
    (boot/'SHA256SUMS').write_text(''.join(sha(boot/name)+'  '+name+'\n' for name in ('system.bit','system.dtb')))
    write_json(runtime/'dfx_manifest.json',manifest)
    write_json(runtime/'net/core_variants.json',variants)
    for name in ('hash_service.py','hash_receive.py','hash_client.py','hash_local.py'):
        shutil.copyfile(ROOT/'software'/name,runtime/'software'/name)
    shutil.copyfile(ROOT/'software/board/start.sh',runtime/'start.sh');(runtime/'start.sh').chmod(0o755)
    shutil.copyfile(ROOT/'software/net/board_run.py',runtime/'net/board_run.py')
    shutil.copyfile(build/'gem_board',runtime/'net/gem_board');(runtime/'net/gem_board').chmod(0o755)
    shutil.copyfile(ROOT/'software/net/install.py',out/'install.py')
    files={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
    write_json(out/'inventory.json',files)
    (out/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in files.items()))
    with tarfile.open(archive,'w:gz') as tar:
        for item in sorted(out.iterdir()):tar.add(item,arcname=item.name)
    print(json.dumps(dict(bundle=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,static_sha256=static),indent=2))


if __name__=='__main__':main()
