# Shared stream input and clearer compact refinements

[Watch the updated full video](media/sha3-comparison-stream.mp4) · [Review evidence](../results/demo-stream-20261116/README.md)

This 4:12 edition keeps the physical sweep and expands the architecture explanation.
The core-facing input is labeled **64-bit AXI Stream**. An opening diagram shows
three upstream paths: PS software through AXI DMA, GEM RX buffers read by PL,
and FPGA block RAM replay. The onboard Ethernet controller remains the PS GEM;
the generic input block does not imply a direct connection from the PHY to PL.

The existing comparison still shows Quartz's local byte adapter and double
buffers against compact's captured stream word, direct state absorption and
held-state digest view. The two compact refinements now have separate scenes:

1. **Padding:** a before/after view contrasts the earlier wide core's variable
   lane selector with local enables across the 17 rate lanes. An example marks
   the message-end lane and final rate lane. All eight capacity lanes remain in
   the state; padding does not modify them.
2. **Framing validation:** the earlier control path is compared with capturing
   data and the fault result together. The following cycle rejects an invalid
   buffered word before absorption. The animation stops that word on the wire;
   the hash state remains unchanged.

These refinements compare this project's earlier wide core with compact. They
are distinct from the Quartz comparison. The algorithm, 24-round permutation
and simulated cycle count are unchanged. The separate historical standalone
LUT experiment has been removed from this edition's narration to keep the
resource comparison focused on the matching routed partitions at the end.

The displayed and spoken replay gain is **about 2.4×**. That is one-decimal
rounding of the same measured **2.385965×** ratio. The 1 GiB times remain
10.73741926 seconds for Quartz and 4.50024163 seconds for compact. No physical
samples or graph coordinates were changed.

## Recording and audio

The control clicks, real progress and labeled 32× wait come from the previous
complete physical job `e0ac322556182145dce29990`. The results page was recaptured
from that same saved job after changing only its displayed precision. This
edition does not claim another hardware sweep or new performance measurements.
The original [400-hash evidence](../results/demo-full-sweep-20261116/README.md)
remains unchanged.

Two updated voiceover takes were generated and transcribed with the existing
Jarnathan / Eleven v4 configuration: stability 0.62, similarity 0.75, clone
strength 0. Take 1 provides clearer pauses between the two refinements. Every
voice stem retains the pitch-preserving 1.06× pace adjustment. The final mixed
movie is transcribed chapter by chapter to verify the changed words and cuts.

Cyber Runner by 2050 / Artlist continues throughout. Six bars extend the existing
170 BPM arrangement to cover the longer explanation; the original 120 ms
crossfades and speech ducking remain. Music is checked for continuity, and the
final AAC is measured for loudness and true peak.

The diagrams and dashboard share `demo/web/comparison.js`. The frame exporter
and renderer recreate the animation without browser chrome or an automation
cursor. The raw results capture retains its original bytes; startup frames and
the far-right scrollbar are excluded from the final picture. No measured value
is hidden or replaced.

## Rebuild

Generate the diagrams to a fresh path, then bind that output's SHA-256 in a copy
of the edit plan before assembling a fresh movie:

```sh
python demo/render_stream_diagrams.py --node /path/to/node \
  --work build/stream-diagrams --output build/stream-diagrams.mp4
python - <<'PY'
import hashlib, json
from pathlib import Path
plan = json.loads(Path('demo/video-stream-edit.json').read_text())
movie = Path('build/stream-diagrams.mp4')
plan['sources']['architecture'] = {
    'path': str(movie), 'sha256': hashlib.sha256(movie.read_bytes()).hexdigest()
}
Path('build/stream-edit.json').write_text(json.dumps(plan, indent=2) + '\n')
PY
python demo/render_video_full_sweep.py --edit build/stream-edit.json \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/stream-movie --output build/stream-movie.mp4
```

Dependencies are NumPy, CairoSVG, FFmpeg and Node. Rendering refuses to overwrite
an existing export. Source hashes, both voice takes, final transcripts, stills
and media checks are retained in the new evidence directory. Earlier media and
sealed results remain available; source hashes for the prior edition resolve
at commit `55fbfe0cf38e2c249e519c6406352db0d281353c`.

Oxide Computer Company and the Quartz contributors remain credited in the
movie and [third-party notices](../THIRD_PARTY_NOTICES.md). Original source and
license notices remain intact, and the video retains the AI-assistance credit.
