#!/usr/bin/env python3
import csv, json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
result_prefix = sys.argv[2]
core_source = pathlib.Path(sys.argv[3])
results = []

def resources(path):
    text = path.read_text()
    values = {}
    for key, label in [('lut', 'Slice LUTs'), ('ff', 'Slice Registers'), ('bram_tile', 'Block RAM Tile'), ('dsp', 'DSPs')]:
        match = re.search(r'^\|\s*' + re.escape(label) + r'\*?\s*\|\s*([\d.]+)\s*\|', text, re.M)
        if not match:
            raise RuntimeError(f'Missing {label} in {path}')
        values[key] = float(match.group(1)) if '.' in match.group(1) else int(match.group(1))
    return values

for buffering in ('false', 'true'):
    prefix = root / 'results' / f'{result_prefix}_db_{buffering}'
    summary = dict(csv.reader(pathlib.Path(str(prefix) + '_summary.tsv').open(), delimiter='\t'))
    summary['double_buffer'] = buffering == 'true'
    for key in ('period_ns', 'input_delay_ns', 'output_delay_ns', 'setup_wns_ns', 'hold_whs_ns',
                'register_setup_wns_ns', 'register_data_path_delay_ns'):
        summary[key] = float(summary[key])
    summary['synthesis'] = resources(pathlib.Path(str(prefix) + '_synthesis_utilization.rpt'))
    summary['routed'] = resources(pathlib.Path(str(prefix) + '_routed_utilization.rpt'))
    summary['estimated_register_fmax_mhz'] = round(1000 / (summary['period_ns'] - summary['register_setup_wns_ns']), 3)
    route_text = pathlib.Path(str(prefix) + '_route_status.rpt').read_text()
    summary['route_error_nets'] = int(re.search(r'nets with routing errors[^:]*:\s*(\d+)', route_text).group(1))
    drc_text = pathlib.Path(str(prefix) + '_routed_drc.rpt').read_text()
    summary['drc_errors'] = len(re.findall(r'^\|[^|]+\|\s*(?:Error|Critical Warning)\s*\|', drc_text, re.M))
    summary['timing_met'] = summary['setup_wns_ns'] >= 0 and summary['hold_whs_ns'] >= 0
    results.append(summary)
    print(f"DOUBLE_BUFFER={buffering}: {summary['routed']}, setup WNS {summary['setup_wns_ns']} ns, hold {summary['hold_whs_ns']} ns")
(root / 'results' / f'{result_prefix}_implementation.json').write_text(json.dumps({
    'source_revision': 'c0ccf08525f30c43f4c773c2295dabe80f97cd0e',
    'variant': result_prefix, 'core_source': str(core_source.relative_to(root)),
    'core_sha256': __import__('hashlib').sha256(core_source.read_bytes()).hexdigest(),
    'scope': 'Standalone flattened-port core OOC synthesis, placement and routing. No PS, DMA, DFX partition or board I/O.',
    'options': 'Vivado 2024.2; rebuilt hierarchy; default synth/opt/place/phys_opt/route; maxThreads=4; HD.CLK_SRC=BUFGCTRL_X0Y0',
    'boundary_timing': 'OOC signal ports have no physical partition-pin placement; I/O budgets omit external routing. Register timing is the standalone core comparison.',
    'reset_timing': 'External asynchronous reset is false-pathed; deassertion synchronization belongs to system integration.',
    'frequency_estimate': '1000/(10ns-register setup slack), an estimate from one routed run, not a validated maximum operating frequency.',
    'configurations': results}, indent=2) + '\n')
if not all(result['timing_met'] and not result['drc_errors'] and not result['route_error_nets'] for result in results):
    raise SystemExit('A baseline configuration did not close timing at 100 MHz; see reports.')
