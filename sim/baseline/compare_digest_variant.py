#!/usr/bin/env python3
"""Compare completed reference and direct-state-digest implementation reports."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
results = root / 'results'
baseline = json.loads((results / 'baseline_implementation.json').read_text())
variant = json.loads((results / 'oxide_no_digest_implementation.json').read_text())
comparison = []
for original, derived in zip(baseline['configurations'], variant['configurations'], strict=True):
    for field in ('double_buffer', 'part', 'vivado', 'period_ns', 'input_delay_ns', 'output_delay_ns'):
        if original[field] != derived[field]:
            raise SystemExit(f'Comparison conditions differ: {field}')
    comparison.append({
        'double_buffer': original['double_buffer'],
        'routed_lut_change': derived['routed']['lut'] - original['routed']['lut'],
        'routed_ff_change': derived['routed']['ff'] - original['routed']['ff'],
        'setup_slack_change_ns': round(derived['setup_wns_ns'] - original['setup_wns_ns'], 3),
        'hold_slack_change_ns': round(derived['hold_whs_ns'] - original['hold_whs_ns'], 3),
        'baseline': original['routed'],
        'derived': derived['routed'],
        'derived_timing_met': derived['timing_met'],
    })
cycle_checks = []
for buffering in ('false', 'true'):
    for gaps in ('false', 'true'):
        suffix = f'db_{buffering}_gaps_{gaps}_cycles.csv'
        same = (results / ('baseline_' + suffix)).read_bytes() == (results / ('oxide_no_digest_' + suffix)).read_bytes()
        if not same:
            raise SystemExit(f'Control-cycle measurements differ: {suffix}')
        cycle_checks.append(suffix)
report = {
    'change': 'Remove duplicate digest register; output held sponge-state digest while valid, zero while invalid.',
    'source': variant['core_source'], 'source_sha256': variant['core_sha256'],
    'identical_cycle_csvs': cycle_checks,
    'scope': 'Same 100 MHz OOC methodology as baseline; standalone core only.',
    'configurations': comparison,
}
(results / 'oxide_no_digest_comparison.json').write_text(json.dumps(report, indent=2) + '\n')
for row in comparison:
    print(f"DOUBLE_BUFFER={row['double_buffer']}: LUT change {row['routed_lut_change']:+d}, FF change {row['routed_ff_change']:+d}, setup slack change {row['setup_slack_change_ns']:+.3f} ns")
