# SHA3 comparison video

The latest [charcoal edition](demo-explained-video.md) makes the SHA3-256 comparison
with Oxide Quartz explicit, uses spoken “sha” and decimal megabytes, and reveals
each diagram with the narration. Its [3:37 video](media/sha3-comparison-explained.mp4)
explains why small messages can favor Quartz and retains continuous music and
the complete physical demo. Earlier editions documented
below remain unchanged.

[Watch the complete narrated video](media/sha3-comparison-v3.mp4) · [Edit evidence](../results/demo-audio-v3-20261115/README.md)

The complete 3:37 cut opens with architecture animations, explains the routed
resources and recorded physical hashing times, credits Oxide, and ends with the
recorded physical GUI request to the connected Zybo. ElevenLabs narration and
**Cyber Runner by 2050** accompany the video. Music continues throughout,
including the live demo, with lower levels during speech. The final movie has
no browser debugging banner or Codex pointer.

Two full voice takes were generated using the owner's existing **David – Deep,
Warm, and Steady** voice and **Eleven Multilingual v2** settings. Speed 1.04,
stability 87%, similarity 64%, style 50%, and speaker boost remained unchanged.
Take 1 was selected for its steadier measured level (3.2 LU loudness range versus
5.9 LU); automated transcripts preserve the key numbers in both. This is signal
and transcript review, not a claimed subjective listening comparison. Both
original downloads are retained: take 1,
take 2.

The input adds seven short SSML pauses without changing the narration words.
The chosen v2 model supports these [pause tags](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-can-i-add-pauses).
The editor cuts at pauses and positions complete phrases around the pictures;
it does not change the generated voice's pitch or speech rate. A few illustrative
chapters run longer. The full 40-second physical capture plays at 1×, followed
by a two-second hold of its final frame. The board was not rerun for this audio edit.

Run `./dashboard.sh` and open `http://127.0.0.1:8765/comparison.html` to replay
or record the editable HTML/SVG presentation. All assets and fonts are local.

## Video chapters

| Start | Chapter |
| --- | --- |
| 00:00 | Two ways to feed SHA3 |
| 00:10 | Quartz: overlap two byte-fed blocks |
| 00:34 | Compact: absorb directly into the state |
| 01:00 | Simpler padding and framing |
| 01:22 | Routed partition resource usage |
| 01:43 | The same physical testbench |
| 02:01 | Measured on-board hashing time |
| 02:26 | Where the improvement applies |
| 02:42 | Sources and credit |
| 02:55 | Live board verification |

The original silent presentation lasts 2:48. Its nine chapters and the final live
segment share one storyboard with the narration.
The v3 edit decisions specify the final 3:37 timing,
every narration cut, music insert, and input checksum.
The [v2 recording evidence](../results/demo-recording-v2-20261115/README.md)
binds the captures, real board jobs, action timeline, sources, and export.

## Claims and source mapping

| Video content | Primary repository source |
| --- | --- |
| 16 MiB, 100 MHz, seven samples, DMA/API scopes | [Physical comparison](../results/sha3-performance-20261115/comparison.md), individual samples in the linked physical JSON reports |
| Primary chart values | [Sealed summary](../results/sha3-performance-20261115/summary.json), loaded by `/api/bootstrap` |
| Quartz double buffers, byte input, 24 rounds, separate digest register | [Unchanged pinned VHDL](../reference/oxide/hdl/ip/vhd/sha3/sha3_256.vhd), [upstream architecture notes](../reference/oxide/hdl/ip/vhd/sha3/docs/sha3_256.adoc) |
| Full-rate byte adapter | [Local elastic adapter](../rtl/sha3/oxide_compare/axis_bytes_elastic.sv), [double-buffer wrapper](../rtl/sha3/oxide_compare/sha3_oxide_core.vhd) |
| Compact 64-bit buffer, direct XOR, held-state digest, registered errors | [Compact SystemVerilog](../rtl/sha3/experiments/hash_sha3_compact.sv) |
| Static padding across 17 rate lanes | Compact RTL `PAD` case compared with [earlier wide/framing revision](../rtl/sha3/experiments/hash_sha3_fast.sv) |
| 5,664 to 4,498 standalone LUTs, equal simulated throughput | Core-only table in the physical comparison; these are distinct from the routed DFX partition totals |
| Credits and license boundaries | [Third-party notices](../THIRD_PARTY_NOTICES.md), [pinned source inventory](../reference/oxide/SOURCE.json) |

The animation's clock progression is illustrative and slowed for readability.
It does not replay captured internal signals. During a Keccak round the complete
state updates, so the compact diagram highlights all 25 lanes. Its input example
shows capture and absorption as separate phases; eight bytes per absorption
event is not a claim of eight bytes per system clock indefinitely. The startup
schedule omits the steady-state benefit of one prefetched beat during permutation.

The resource explanation identifies architectural storage differences. It does
not assign every synthesized LUT or flip-flop to a single source change. The
padding refinement compares two project variants, not Quartz padding against
ours. Primary resource figures cover comparable routed hash partitions including
adapters. The region reservation, partial-image size and power are not claimed
to improve.

## Recording and pointer choreography

On the live dashboard, **Record guided demo** enters presentation mode and opens
the browser’s tab-capture prompt. Select only this tab. The smooth pointer moves
to **Check board**, **Use an 8 KiB sample**, and **Hash on the FPGA**, then activates
their actual click handlers. These handlers use the authenticated local API and
physical UART/DMA backend. The sequence waits for real successful job responses;
no digest, timing, or success state is inserted for the video.

The final result remains visible before recording stops. **Export cursor log**
saves click times and matching backend job IDs. An unavailable or failed board
operation stops the guided take, and the exporter rejects unsuccessful or
incomplete takes. Cancelling recording does not interrupt a running board job’s
bounded cleanup. A slow take must be retimed, not clipped to fake completion.

The pointer graphic is adapted from [Lucide](https://github.com/lucide-icons/lucide),
with its pinned original and license retained under
[`demo/web/assets/lucide`](../demo/web/assets/lucide/SOURCE.json).
Its easing and click pulses are presentation effects. The native capture cursor
is disabled, and the automation overlay is hidden during capture. Browser chrome,
including the debugging notice, is outside the captured tab. The v2 frames were
reviewed for both the notice and the unwanted pointer.

The browser saves a WebM locally with `getDisplayMedia` and `MediaRecorder`.
No camera, microphone, desktop, or cloud recording service is used. The
presentation stops automatically at its end; the guided live sequence has a
40-second target. Raw takes and review frames are retained locally in ignored
`build/demo/video-v2/`. No actual displayed result is changed in editing.

Reproduce the 1080p / 30 fps H.264 master at a fresh path:

```sh
python3 demo/render_video_v2.py build/demo/video-v2/comparison-raw.webm \
  build/demo/video-v2/live-raw.webm build/demo/video-v2/cursor-log.json \
  build/demo/video-v2/reproduced.mp4
```

The exporter preserves real-time playback, adds chapter metadata and a caption
identifying the scripted pointer and physical check, and verifies the exact
208-second / 6,240-frame output. It handles capture-surface resize without
reinitializing the concat graph. The final static hold may require up to one
second of repeated frames because the browser skips unchanged capture frames;
the cursor receipt still records the full 40 seconds. FFmpeg and ffprobe are required.

## Reproduce the complete audio edit

The soundtrack's repeating rhythmic phrases support a 170 BPM editorial grid
(85 BPM half-time). The first automatic tracker chose an approximately 113 BPM
metrical alias; onset autocorrelation and phrase spacing were checked before
editing. Three bar-aligned joins extend the 2:23 source across 3:37. The music
build reaches the resource section near 01:22, a strong arrangement change
opens the speed chapter near 02:02, and a final lift follows the live digest
match near 03:21. Short crossfades smooth the joins. Quiet music passages remain
present; the music is never gated off beneath narration.

The final AAC mix measures −15.99 LUFS integrated and −1.83 dBTP. The separate
music stem has nonzero audio in every one-second interval. Voice cuts preserve
all 417 words recognized in the original take; ASR is imperfect for names and
binary unit pronunciation, so the source text and visible KiB/MiB labels remain
authoritative. The complete MP4 was decoded and its chapter and live-result
frames reviewed.

Use Python with NumPy, FFmpeg and ffprobe. The soundtrack is the owner's local
download and is not distributed as a standalone repository asset. Supply that
exact file; the exporter verifies its checksum before rendering.

```sh
python3 demo/render_video_v3.py \
  --video docs/media/sha3-comparison-v2.mp4 \
  --voice docs/media/voiceover-take-1.mp3 \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/video-v3-reproduction \
  --output build/demo/sha3-comparison-v3-reproduced.mp4
```

The renderer retains separate narration/music stems, its mix measurements and
picture chapters under the work directory. It refuses to replace an existing
output or accept source files whose checksums differ from the edit decisions.
See [media attribution](../THIRD_PARTY_NOTICES.md#demo-audio) for the soundtrack
and narration boundaries.

## Earlier per-chapter voiceover helper

Generate one narration clip for each section of the timed script.
Name them `01.wav` through `10.wav` (MP3, M4A, OGG and FLAC are also accepted),
and put them in a local directory such as `build/demo/voiceover/`. Each clip must
fit its chapter. The script adds silence to shorter clips and rejects overlong
clips instead of speeding up speech or cutting words.

```sh
python3 demo/add_voiceover.py docs/media/sha3-comparison-v2.mp4 \
  build/demo/voiceover build/demo/video-v2/narrated.mp4
```

Video is copied without re-encoding; narration becomes stereo AAC at 48 kHz.
This helper targets the silent v2 master, not the longer finished v3 edit.
A synthetic tone fixture validated this older muxing pipeline; the v3 evidence
instead checks the actual generated narration and continuous music mix.

## Preserved earlier cut

The [3:28 silent v2 master](media/sha3-comparison-v2.mp4), the [3:18 first cut](media/sha3-comparison.mp4), their
[sealed recording evidence](../results/demo-recording-20261115/README.md), and
`demo/render_video.py` remain unchanged. The first cut uses a different chapter
order and includes the earlier pointer. Use **version 3** for the complete narrated video.

The physical comparison remains the dated accepted experiment. Replaying the
presentation does not rerun it. The fresh 8 KiB GUI check is a separate request
and is not used to calculate the Quartz speedup.
