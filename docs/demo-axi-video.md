# AXI stream narration update

[Watch the updated full video](media/sha3-comparison-axi.mp4) · [Review evidence](../results/demo-axi-20261116/README.md)

The opening now says, “A sixty-four-bit AXI stream feeds each core.” The
ElevenLabs input spells AXI as **acksee** to produce the requested pronunciation.
On-screen labels retain the standard **AXI Stream** spelling. The diagram starts
with one generic input and progressively reveals the Quartz adapter, buffers,
state and digest register. Upstream sources are not enumerated in this section.
Block RAM replay is introduced later, when the experiment is explained.

The full video is about **4:05**. Removing the source enumeration shortens the
opening by 7.7 seconds. The remaining architecture explanation, two refinements,
physical sweep, results, **2.4×** gain, resource counts and credits are retained.
The same saved physical job supplies the measurements; this revision does not
run another benchmark or change the hardware.

Two new opening takes were generated using the existing Jarnathan / Eleven v4
settings: stability 0.62, similarity 0.75 and clone strength 0. Take 1 was selected
after transcription and phoneme recognition. Only that paragraph is replaced;
the other accepted voice stems and pitch-preserving 1.06× pace remain.
Final AAC checks cover the pronunciation, edited words, loudness and true peak.
Cyber Runner remains continuous, with the shortened arrangement retaining its
170 BPM grid and 120 ms crossfades.

The diagram uses the same scene code as the interactive dashboard. Rebuild
with `demo/render_stream_diagrams.py`, which reads `demo/web/story-axi.json`,
then bind the generated architecture movie's path and checksum in a copy of
`demo/video-axi-edit.json`. Assemble that plan with
`demo/render_video_full_sweep.py --edit PATH --music MUSIC --work WORK --output OUTPUT`.
Use fresh output paths to preserve existing exports. Dependencies and the
checksum-binding example are in the [preceding guide](demo-stream-video.md#rebuild).

The previous 4:12 edition remains available. Its scene and renderer source
hashes resolve at commit `83d351ec96deec0fcdb53fc14e1d0b3464c7463c`.
Oxide attribution, original source/license notices and AI-assistance credit
remain intact.
