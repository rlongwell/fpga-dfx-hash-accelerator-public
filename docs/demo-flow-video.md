# Closing narration and highlight timing

[Watch the 4:12 revision](media/sha3-comparison-flow.mp4) · [Architecture and measurement guide](demo-architecture-video.md) · [Edit evidence](../results/demo-flow-20261116/README.md)

The closing GUI walkthrough now follows the original spoken cadence. The final
five sentences come from one continuous section of the selected voice take,
instead of being separated by fixed waits for each result box. Earlier pauses
in the live narration are also shortened. Voice, words, pronunciation and the
1.06× playback rate are unchanged; no new voice generation was needed.

The GUI section still starts at **3:21**. It now lasts 51 seconds. The complete
physical board operation through 31.1 seconds of the capture remains in order
at normal speed; the recorded job finished at 30.561 seconds. Only subsequent
idle result holds are cut. The left time, right time, digests and summary are
highlighted as their narration begins. All displayed measurements come from
the same accepted physical recording. The board was not accessed for this edit.

The architecture picture before 3:21 is copied from the previous master.
Cyber Runner continues through the full revision, with its closing musical
cue moved to the new digest highlight and a short final fade. The earlier
[4:36 edition](media/sha3-comparison-architecture.mp4) and original 75-second
capture remain available with their sealed evidence.

Reproduce with the existing media dependencies and matching local music:

```sh
python3 demo/render_video_flow.py \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/flow-reproduction \
  --output build/demo/flow-reproduced.mp4
```

The edit list records the source hashes,
frame-accurate picture cuts, narration positions and music edits. The renderer
rejects cuts that would shorten the actual board operation and preserves
previous output files.
