# TimingLens on the real Zybo DFX design

The original tool reproduced Vivado's overall timing correctly but failed to parse the extra DFX report columns. All 3,572 captured arc delays were unavailable, and a critical reset connection was absent. Its “Exact” source label overstated what a surviving Vivado line tag proves.

The repaired version reads the DFX columns, restores the missing connection, shows measured-detail coverage, provides raw paths in the GUI/HTML, and uses module-level path navigation with explicitly qualified per-cell source hints. Routing findings now name the slowest measured branches and their physical sites, load counts, and DONT_TOUCH status. Arithmetic findings include measured carry-cell delay.

A fresh Vivado read of the unchanged checkpoint reproduced WNS −0.011 ns, TNS −0.138 ns, and 18 failing endpoints. All 18 failing paths now have complete measured detail. Across 200 collected paths, 3,672/3,672 links are captured and 3,658 delays are assigned. Fourteen delays remain unknown on eight passing paths because Vivado hides resource names; the tool warns instead of guessing.

The real critical path runs from shell reset control through masked TKEEP, byte counting, and input-length validation to the remaining-byte register enable. It is not BLAKE2s compression arithmetic. Routing accounts for 6.523 ns of the 9.549 ns datapath; the eight carry cells account for 1.348 ns. The 1.058 ns partition-boundary TKEEP branch and 1.052 ns reset branch are now visible directly.

The passing SHA-256 control still yields zero findings. The updated suite passed 34 tests; six optional example rebuild tests were deselected. Four previously routed non-DFX examples were re-imported with complete detailed-delay coverage. Both GUI themes were rendered and inspected. These are implementation-analysis and software-test results, not new physical-board measurements.

The tool is now useful for narrowing and reviewing a timing failure. It remains a diagnostic assistant: recommendations are rule-based hypotheses, source tags do not prove causal RTL expressions, and timing closure still requires an implemented change plus functional validation. For this failure, it supports a BLAKE2s-only placement experiment while retaining the locked static design and passing configurations.

`evaluation.json` records the measurements and tool source hashes. Full captures, HTML, screenshots, a before/after source patch, and test output are local under `build/timinglens-evaluation/`. The input checkpoint was unchanged.

The targeted placement experiment subsequently passed: BLAKE2s setup slack improved to **+0.110 ns**, hold remained **+0.016 ns**, and full `pr_verify` confirmed static compatibility. Hash RTL and constraints were unchanged. The [retained reports](repair/routed_timing.rpt) record this implementation result. Physical deployment/acceptance is tracked in the parent evidence report.

## Project-aware extension and presentation

The completed extension accepts RTL, literal Tcl/BD, XDC and timing reports together, with no AI service or Tcl execution. It supplies exact Vivado 2024.2 experiment recipes; a targeted comparison-to-enable RTL hypothesis; gated interface slice/FIFO reviews; and exception audits based on explicit design intent. False paths are never inferred from negative slack alone. Optional constraint templates remain commented and require functional/CDC validation.

The desktop has an issue list beside one candidate, numbered next steps, and separate change/evidence/Tcl-and-validation tabs. Dark and light views were inspected, including a 980×740 window. Tcl copying does not execute commands. The final offline suite passes 48 tests; two new live DCP reads retain the original failure and confirm the repaired result has +0.110 ns setup, +0.016 ns hold and zero findings. These are implementation-report results, not physical throughput measurements.

[Project-review evidence and exact source hashes](project-review.json) and the [complete patch against the pre-repair local tool snapshot](timinglens-project-upgrade.patch) are retained here. Usage and limits are documented in the sibling TimingLens repository's `docs/project-analysis.md`. TimingLens remains a deterministic, limited-pattern recommender; it does not prove arbitrary RTL transformations or CDC exceptions safe.

[Recommendation view, dark theme](fixes-dark.png) · [Light theme](fixes-light.png).
