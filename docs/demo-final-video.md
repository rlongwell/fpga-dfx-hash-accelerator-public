# Final SHA3-256 comparison demo

[Watch the full video](media/sha3-comparison-final.mp4) · [Review evidence](../results/demo-final-20261116/README.md)

The resource section now says **“Both hash cores use zero BRAMs”** and shows a
single **BRAMs** row: **Oxide Quartz 0**, **Compact 0**. It does not distinguish
BRAM block sizes. These are the routed hash-partition counts; the shared replay
memory remains identified separately. The matching report also supplies the
unchanged LUT and flip-flop totals.

The new resource paragraph retains Jarnathan / Eleven v4, stability 0.62,
similarity 0.75, clone strength 0 and the pitch-preserving 1.06× pace. The other
accepted voice passages remain, including “acksee” and “shah.” Cyber Runner
continues throughout. The full video is approximately **4:08**, with the added
resource sentence extending the previous edition by 3.23 seconds.

The architecture, refinements, real sweep, 2.4× results and credits are retained.
This is a presentation revision using the same physical job
`e0ac322556182145dce29990`; no new benchmark or hardware change is claimed.

To rebuild, render the resource chapter with `demo/render_resource_chapter.py`
using `--edit demo/video-final-edit.json --work WORK --output FRESH_PATH`.
Bind that output's path and SHA-256 in a copy of the edit plan, then assemble
with `demo/render_video_full_sweep.py --edit PLAN --music MUSIC --work WORK --output OUTPUT`.
Use fresh output paths to preserve earlier exports.

The preceding [AXI edition](demo-axi-video.md) remains available. Its mutable
renderer source hashes resolve at `ac506610bb062c77442d6dacef4d6164e5bc5991`.
Original Oxide source, license notices, credit and the AI-assistance disclosure
remain intact.
