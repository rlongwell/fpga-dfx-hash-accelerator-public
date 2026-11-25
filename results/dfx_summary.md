# DFX implementation results

Vivado 2024.2, xc7z020clg400-1, 100 MHz. These are routed implementation results; no board was connected.

| Configuration | Total LUT / FF | Static LUT / FF | RP LUT / FF | WNS (ns) | WHS (ns) | Full .bit bytes | Partial .bit bytes | PCAP .bin bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sha3 | 7193 / 4281 | 2177 / 2495 | 5016 / 1786 | 0.262 | 0.044 | 4045670 | 2400587 | 2400480 |
| sha256 | 3953 / 3744 | 2177 / 2495 | 1776 / 1249 | 0.229 | 0.044 | 4045670 | 2400587 | 2400480 |
| blake2s | 6338 / 4161 | 2177 / 2495 | 4161 / 1666 | 0.101 | 0.044 | 4045670 | 2400587 | 2400480 |

Static counts are total routed usage minus the u_hash hierarchy. They can include implementation-added cells; the separate static synthesis counts precede implementation.

All routable nets are routed with zero routing errors. Routed setup, hold, and pulse-width timing pass. Implementation DRC has no errors or critical warnings. The initial configuration's static placement/routing is reused for every alternate. Compact reports, pr_verify results, source/artifact identities, and evidence.sha256 are preserved in results/dfx/; large checkpoints and programming images remain under build/vivado/dfx/.

Full reports, resource-type counts, and the machine-readable summary are in [dfx_summary.json](dfx_summary.json). Runtime image identities are in [dfx_manifest.json](dfx_manifest.json).
