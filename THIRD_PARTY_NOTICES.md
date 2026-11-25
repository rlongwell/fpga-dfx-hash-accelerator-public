# Attribution and license boundaries

## Oxide Computer Company and Quartz contributors

This project credits [Oxide Computer Company's Quartz project](https://github.com/oxidecomputer/quartz)
for the SHA3-256 reference implementation and the practical hardware baseline
that informed this study. The upstream SHA3 work was introduced by
[@nathanaelhuffman](https://github.com/nathanaelhuffman) in
[Quartz PR #516](https://github.com/oxidecomputer/quartz/pull/516), with review and
contributions recorded in that project. The upstream history remains the
authority for authorship. These acknowledgments do not replace its notices.

The exact reference revision is
[`c0ccf08525f30c43f4c773c2295dabe80f97cd0e`](https://github.com/oxidecomputer/quartz/tree/c0ccf08525f30c43f4c773c2295dabe80f97cd0e).
The vendored source is byte-for-byte unchanged. Its VHDL-2019 port-view spelling
includes the later [PR #538](https://github.com/oxidecomputer/quartz/pull/538).
The [source inventory](reference/oxide/SOURCE.json) records exact retrieval URLs
and SHA-256 hashes, including the core, Keccak package, AXI interface package,
utility package, and documentation.

| Files | Provenance and license |
| --- | --- |
| `reference/oxide/` | Unchanged Quartz reference; **MPL-2.0**. Original source notices and the [full license text](reference/oxide/MPL-2.0.txt) are retained. |
| `rtl/sha3/oxide_no_digest/sha3_256.vhd` | Separately marked **MPL-2.0 derivative** of the pinned core. The [modification record](rtl/sha3/oxide_no_digest/SOURCE.json) describes the digest-register removal and records both hashes. This is not the compact SystemVerilog design or the headline comparison baseline. |
| `rtl/sha3/oxide_compare/`, `rtl/rm/sha3_oxide.sv` | Project integration wrappers and adapter, MIT. They compile the unchanged upstream core with double buffering enabled; they do not replace its license. |
| `rtl/sha3/hash_sha3.sv`, `rtl/sha3/experiments/` | Project SystemVerilog implementations of SHA3-256, MIT. They are kept separate from the vendored VHDL and the explicitly marked MPL derivative. The architecture and comparison credit Quartz as prior work; no clean-room provenance claim is made. |
| `software/linux/hash_accel.c` | Project Linux driver, **GPL-2.0-only**; [license text](software/linux/COPYING). |
| `software/embedded/xilinx-dma-terminate-error.patch` | Linux-derived patch, **GPL-2.0-or-later**, retaining the upstream file's license. |
| Other original project files | MIT unless a file or component specifies otherwise; see [LICENSE](LICENSE). |

## Benchmark attribution and scope

The published comparison is this project's integration and measurement of a
pinned Quartz core on a Zybo Z7-20. Oxide did not perform or endorse this study.
Its upstream work targets host-image hashing using SPI-NOR and a byte-stream
interface. This project targets wider PS DDR-to-PL DMA input. The result is an
architectural/workload comparison, not a measurement of an Oxide production
system or a claim that its original design is universally inferior.

Both sides run SHA3-256 at 100 MHz through the same static shell and DMA setup.
The primary baseline uses the upstream double-buffer configuration and a
project elastic adapter that preserves its one-byte-per-clock input rate.
The [review guide](docs/review-guide.md) gives the exact claim and limitations.

## Source availability with generated artifacts

The MPL-covered source, local modification, notices, and license text are
included in this repository. The project MIT license does not relicense those
files. When distributing a generated comparison image, provide its recipients
the corresponding source revision and these notices with access to the
MPL-covered source. A private repository link alone is insufficient for a
recipient who cannot access it. Mozilla's [MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)
and the retained license explain source and executable distribution separately.

Kernel, U-Boot, Buildroot, toolchain, vendor IP, and rootfs packages retain their
own terms. The embedded build retains source archives and Buildroot legal-info;
see [software deployment](docs/software.md). This source push does not publish
the ignored binary images or third-party tool installations.

## Presentation pointer

The demo pointer derives from Lucide’s `mouse-pointer-2.svg`, pinned at
`55782beff3a0133df79c417eb68f96e8f19e2404`. The unchanged original, upstream
license text (ISC for Lucide and retained MIT notice for Feather-derived work),
download URLs, and SHA-256 hashes are in
[`demo/web/assets/lucide`](demo/web/assets/lucide/SOURCE.json).
Copyright and attribution are retained in the [license](demo/web/assets/lucide/LICENSE).

`demo/web/assets/presentation-pointer.svg` changes only the fill, stroke color,
and stroke width. The scripted motion and actual dashboard interactions are
project code. Lucide is credited for the graphic; it does not endorse this demo.

## Demo audio

The v3 demo soundtrack is **Cyber Runner by 2050**, from **Artlist**, supplied
as the repository owner's existing `2050 - Cyber Runner.mp3` download. The
source file's metadata identifies Artlist and retains an all-rights-reserved
notice. The soundtrack is credited on the movie's sources slide and in its
metadata. Its checksum and edit positions are recorded in
`demo/video-v3-edit.json`. The original music file is
kept locally, not committed as a standalone asset.

The project MIT license does **not** relicense the music embedded in
`docs/media/sha3-comparison-v3.mp4`. Its use remains subject to the owner's
applicable Artlist license; this repository's provenance record does not certify
that license's scope. The earlier silent masters remain available separately.
The same soundtrack and rights boundary apply to
`docs/media/sha3-comparison-neutral.mp4`.

The two narration takes in `docs/media/voiceover-take-{1,2}.mp3` were generated
through the owner's ElevenLabs account using its selected David voice and
Multilingual v2 model. They are generated media, not a recording of the project
author speaking. The project supplies the original narration text and does not
claim ownership of the voice model or grant rights to that model. Voice settings,
source hashes, take selection and mix checks are retained in the
[audio evidence](results/demo-audio-v3-20261115/README.md).

The neutral edition's `docs/media/voiceover-neutral-take-{1,2}.mp3` files use
the owner's subsequently selected **Jarnathan – Confident and Versatile** voice
with **Eleven v4**. The same generated-media and model-ownership boundaries apply.
The narration acknowledges AI assistance and uses neutral descriptions of the
design and measurements. Its [evidence](results/demo-neutral-20261115/README.md)
records the unchanged generation controls, explicit S.H.A. pronunciation input,
downloads, level balancing and final edit.

The charcoal editions (`docs/media/sha3-comparison-charcoal.mp4` and
`docs/media/sha3-comparison-charcoal-clean.mp4`) use the same
Cyber Runner soundtrack and rights boundary. The retained
`docs/media/voiceover-charcoal-take-{1,2}.mp3` files use Jarnathan / Eleven v4
with the owner's selected controls; the final voice has a pitch-preserving
1.06× pace adjustment. [Evidence](results/demo-charcoal-20261115/README.md)
records pronunciation, word timing, source hashes, and the new physical run.
Automated acoustic QA uses Meta/Facebook's Apache-2.0
[`wav2vec2-lv-60-espeak-cv-ft`](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft)
phoneme model; no model weights are redistributed in this repository.

The small-message explanation edition (`docs/media/sha3-comparison-explained.mp4`)
retains the charcoal soundtrack, voice, and rights boundaries. The replacement
chapter's two downloads are `docs/media/voiceover-small-messages-take-{1,2}.mp3`;
take 1 is used at the same pitch-preserving 1.06× pace. Its script, edit plan,
and validation are linked from [the edition guide](docs/demo-explained-video.md).
