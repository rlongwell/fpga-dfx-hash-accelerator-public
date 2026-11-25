# Caption cleanup — 2026-11-15

[Watch the updated 3:23 video](../../docs/media/sha3-comparison-charcoal-clean.mp4).

Removed the recurring diagram/board-results disclaimer, the recorded-physical-
measurements caption in the timing chapter, and the physical-Zybo/scripted-
cursor footer from the live segment, as requested. The three regions are bound
by frame and input checksum in the edit list.
The presentation and live assembler also omit these lines for future captures.

The previous charcoal movie and its evidence remain unchanged. This is a picture
edit of that recording, not a new board run. Actual measurements, limitations,
Oxide attribution, AI-assistance credit, and the full live capture are retained.

Validation: 1920×1080, 30 fps, 6,090 frames, 203 seconds, ten unchanged chapters.
The copied AAC packet stream has the same SHA-256 in both movies, preserving
all narration and continuous music exactly. The full video decodes successfully.
SSIM against the source with only the three specified removals is 0.999775.
All ten chapters were reviewed in a contact sheet, with full-size checks of the
opening, timing chapter, live results and ending. Python and JavaScript syntax
checks pass. See [validation.json](validation.json) for file and audio checksums.

Reproduce with `python3 demo/clean_video_captions.py --output build/demo/clean-copy.mp4`
from the repository root. The renderer refuses to overwrite an existing movie.
