# Routing congestion evidence

Standalone OOC comparisons; not whole-system DFX routing. Post-placement region dimensions are Vivado estimates, not congested-device percentages. Global routing utilization is separate from local congestion and final route correctness.

Each direction reports global/short region size exactly as printed by Vivado's post-placement estimator. Routing utilization uses the final reported global resource percentages. A completed route with zero overlaps is a correctness check, not a claim of zero congestion.

| Implementation | North | South | East | West | Vertical use, % | Horizontal use, % |
| --- | --- | --- | --- | --- | ---: | ---: |
| baseline, double_buffer=false | 1x1/2x2 | 1x1/1x1 | 2x2/4x4 | 1x1/1x1 | 2.475 | 3.600 |
| baseline, double_buffer=true | 1x1/2x2 | 1x1/4x4 | 4x4/8x8 | 1x1/1x1 | 3.376 | 4.663 |
| oxide_no_digest, double_buffer=false | 1x1/1x1 | 1x1/1x1 | 8x8/4x4 | 1x1/1x1 | 2.233 | 3.610 |
| oxide_no_digest, double_buffer=true | 1x1/4x4 | 1x1/4x4 | 8x8/8x8 | 1x1/2x2 | 3.402 | 4.615 |
| sha3 | 1x1/2x2 | 1x1/1x1 | 4x4/8x8 | 1x1/1x1 | 3.077 | 4.379 |
| sha256 | 1x1/2x2 | 1x1/1x1 | 1x1/1x1 | 1x1/1x1 | 0.502 | 0.626 |
| blake2s | 1x1/1x1 | 1x1/1x1 | 1x1/4x4 | 1x1/1x1 | 2.040 | 2.597 |
| sha3_wide | 2x2/2x2 | 8x8/16x16 | 8x8/16x16 | 4x4/8x8 | 6.075 | 6.653 |
| sha3_serial | 1x1/2x2 | 1x1/1x1 | 1x1/4x4 | 1x1/1x1 | 3.301 | 4.358 |

The JSON record identifies the completed route log, its retained copy and SHA-256. Interrupted logs cannot supply a final utilization result. Regenerate with `python3 benchmarks/congestion.py` after routing finishes.
