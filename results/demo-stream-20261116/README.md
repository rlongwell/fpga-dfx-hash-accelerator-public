# Shared stream and refinements video evidence

[Updated 4:12 movie](../../docs/media/sha3-comparison-stream.mp4) · [Guide](../../docs/demo-stream-video.md)

This is a presentation revision of the preceding full demo. No new physical
benchmark was run. Job `e0ac322556182145dce29990` still supplies all 400 verified
hashes, including 350 measured samples, and its unchanged [physical evidence](../demo-full-sweep-20261116/README.md)
retains the complete plan, raw rows, core identities, recovery and software checks.

The core-facing input is a generic 64-bit AXI Stream interface. The new opening
shows PS/DMA, GEM RX buffers read by PL, and FPGA block RAM replay as upstream
sources. The input selection is checked against `rtl/net/net_system_top.sv`
and `rtl/net/gem_ingress.sv`; the core port is checked against
`rtl/sha3/experiments/hash_sha3_compact.sv`.

Padding and framing validation have separate before/after scenes, comparing
this project's earlier wide core with compact. Padding enables only the 17 rate
lanes while retaining all 25 state lanes. An invalid captured word stops before
absorption on the following cycle. These diagrams describe source structure,
not captured internal waveforms. They do not claim new RTL or timing results.

The headline and spoken gain are **2.4×**, rounded to one decimal from
**2.385965×**. Exact cycles, measured seconds, and graph data are unchanged.
`results-cursor-log.json` explicitly identifies the results-only recapture of the
same completed job. The full real sweep, controls, progress and labeled 32× wait
are reused from the earlier recording. Startup overlay frames and the far-right
scrollbar are excluded; no measurement is concealed.

`take-1-transcript.json` and `take-2-transcript.json` contain word-level recognition
of both newly generated takes. `production.json` records the unchanged selected
voice/configuration, chosen take, and cut positions. `final-mix-transcript.json`
checks the final mixed movie chapter by chapter; pronunciation checks and audio
level/continuity reports accompany it. Recognition may normalize acronyms and
number formatting, so the source script and word timestamps are also retained.

The final frame stills include the shared-source overview, both core paths,
padding, registered validation, the 2.4× results and resource/credit ending.
The renderers use the same SVG scene code as the dashboard. `source-map.json`
binds the RTL, scene code, narration inputs and unchanged physical samples.

Oxide Computer Company and the Quartz contributors remain credited. Their pinned
reference source, license notices and the project's AI-assistance disclosure are
unchanged. Cyber Runner by 2050 / Artlist plays throughout; six bars extend the
existing arrangement for the longer explanation. Original standalone music is
not copied into the repository.

Earlier videos and sealed evidence remain untouched. Their mutable source-file
hashes resolve at commit `55fbfe0cf38e2c249e519c6406352db0d281353c`. This edition's
own files and source dependencies are bound by `SHA256SUMS`:

```sh
sha256sum -c results/demo-stream-20261116/SHA256SUMS
```
