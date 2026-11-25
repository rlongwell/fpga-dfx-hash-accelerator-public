# SHA3 throughput and resource profiling

The original installed SHA3 design absorbed one byte per cycle. The new variants
absorb up to eight bytes at a time, while retaining one Keccak round per cycle,
the same 100 MHz clock, static DMA system, driver and application ABI.

Two improvements are retained separately:

- `sha3_fast` registers framing validation, removing the AXI keep/length checks
  from the state-register write enable. Invalid beats fail before absorption.
- `sha3_compact` additionally decodes padding across only the 17 rate lanes.
  This removes a dynamic read/modify/write mux over all 25 state lanes. It has
  identical simulation cycle counts to `sha3_fast`, with fewer LUTs.

The [physical comparison and resource tables](../results/sha3-performance-20261115/comparison.md)
separate measured board throughput, routed FPGA utilization, and core-only
simulation estimates. All individual timing samples and hardware counters are
retained. The headline comparison uses SHA3-256 on both sides; the SHA-256 and
BLAKE2s measurements are reported separately.

Oxide's pinned VHDL source remains unchanged, with double buffering enabled.
The local wrapper connects its byte stream to the same DMA/static interface.
An elastic adapter permits one byte per clock without introducing an extra
pause between AXI beats. The original-adapter run is also retained. Oxide's
upstream interface cannot encode an empty message; our variants handle empty
padding in hardware and are tested for it.

The installed image measures **233.66 MB/s through DMA** and **155.91 MB/s through
the local PS API** for 16 MiB inputs. The corresponding full-rate Oxide results
are 99.14 and 81.81 MB/s. The comparable routed partitions use 4,531 versus 5,856
LUTs and 1,774 versus 4,222 FFs. Small inputs remain dominated by setup overhead;
the measured speedup applies to large buffers.

## Reproduce the builds

These dated incremental commands require the retained accepted original static
checkpoint and its three compatible configurations, including the exact original
full-image hash. A new build from source creates a new artifact identity; see
[reproduction limits](review-guide.md#build-and-deployment-limits). The following commands rebuild only the selected
partition, preserving the original baseline artifacts:

```sh
./build.sh sha3-variant compact
OXIDE_ELASTIC=1 OXIDE_ELASTIC_PLACE=medium OXIDE_ELASTIC_POSTROUTE=1 \
  ./build.sh sha3-variant oxide
```

`COMPACT_SPREAD=1` selects the alternate placement for the compact variant.
`OXIDE_SPREAD=1` selects alternate placement with the original byte adapter;
`OXIDE_ELASTIC=1` selects both the elastic adapter and alternate placement.
`OXIDE_ELASTIC_PLACE=medium` selects medium spreading; the default is high.
`OXIDE_ELASTIC_POSTROUTE=1` with medium spreading applies physical optimization
and an Explore routing pass to the completed route. The first route and any
timing failure remain retained. The exporter verifies both source ledgers.
The attempted native-core placement reuse was rejected by LUT packing conflicts
and produced no programming image.
The accepted implementation JSON identifies the actual source paths and flow.
The earlier fast candidate remains reproducible with `./build.sh sha3-variant fast`.

Every image must pass routed setup, hold and pulse-width timing, complete
routing, DRC, and `pr_verify -full_check` against all three original configurations.
A passing standalone core route alone is insufficient for deployment. Images
and checkpoints remain under `build/sha3-profile`; compact reports and manifests
are retained under `results/sha3-performance-20261115`.

For standalone core measurements under the same constraints as Oxide:

```sh
./scripts/build_engines.sh sha3_compact
```

The base `./build.sh system all` flow remains available to reproduce the original
byte-absorption system. The variant target is the incremental upgrade path.

## Reproduce physical profiling

Use the checksum-verifying UART uploader to stage the manifest, compressed
partial image and scripts under `benchmarks/sha3_profile`. `stage_board.py`
checks the installed full image, decompresses to a temporary file, verifies
the partial's SHA-256, then publishes it without replacing an existing file.

`run_board.py` takes `--manifest`, `--label`, and `--output`; use `--oxide` for
the upstream empty-message limitation. Stop the shared service and load
`hash_accel` before running it. `run_variant.sh` is the dated shared-card wrapper
used in this run; it always switches back to the production manifest and
restarts the service when the benchmark exits.

After promotion, the retained `oxide_elastic/runtime_manifest.json` binds the
comparison partial to the currently installed compact full image. Its
`runtime_compatibility.json` records that both variants passed full compatibility
checks against the same original locked static design. The production manifest
continues to select the compact partial.

The benchmark deliberately switches to SHA-256 before loading each SHA3
variant. All SHA3 variants expose algorithm ID 1, so that ID alone does not
identify a particular implementation. Changing a manifest while ID 1 is
already active does not force a load. Use the benchmark's forced transition
or boot the corresponding full image.

The benchmark checks correctness before timing, warms each method once, then
records seven samples. It measures both prefilled coherent-DDR DMA and the
local API including application-memory copies. Reference hashing, allocation,
configuration, disk I/O and UART output are outside the hardware timers. The
ARM reference is timed separately. Small requests remain dominated by software
and DMA setup costs.
The board's wall clock is unsynchronized; use the host UTC timestamps in
`uart.log` for chronology. Timed durations use the monotonic performance clock.

On the original workstation with the retained build artifacts, regenerate the
comparison and chart with an isolated plotting environment. A source-only clone
can verify the existing report using `audit_results.py` without these artifacts:

```sh
python3 -m venv build/profile-plot-venv
build/profile-plot-venv/bin/python -m pip install \
  -r results/sha3-performance-20261115/plot-requirements.txt
build/profile-plot-venv/bin/python benchmarks/sha3_profile/report.py \
  --variant compact --baseline oxide_elastic
```

The report generator checks that the physical runs used the same benchmark,
kernel, buffer size and sampling policy, and that each tested partial matches
its routed implementation record. Matplotlib is needed only for this chart.

## Packaging and rollback

The original accepted manifest and build record remain unchanged as a baseline.
The upgraded boot image and matching runtime manifest are identified by
`results/sha3-performance-20261115/promoted_manifest.json` after acceptance.
The original SHA-256/BLAKE2s partials, device tree, kernel and driver remain
compatible because the static route and partition boundary are unchanged.

After post-boot acceptance, stage a complete shared payload with:

```sh
python3 benchmarks/sha3_profile/stage_bundle.py \
  build/sha3-profile/accepted-rootfs build/sha3-profile/accepted-boot
```

The staging command validates the physical acceptance record, build source
hashes and compatibility reports. It starts from the original accepted shared
payload, adds the new partial, and selects the new full image and manifest.
It writes only the named directories and produces updated per-file checksums.
The two host reporting tools that changed during profiling retain their original,
checksum-verified copies from the accepted embedded rootfs in this runtime bundle.
Their updated sources and reports remain in this repository.

For a newly built standalone SD image, explicitly select the upgraded manifest:

```sh
HASH_MANIFEST="$PWD/results/sha3-performance-20261115/promoted_manifest.json" \
  ./build.sh embedded package
```

On the physical card, promotion retains the original `system.bit`, `system.dtb`,
`SHA256SUMS`, runtime manifest and original payload inventory under
`/boot/profiles/hash/before-sha3-fast-20261115/`. To restore that version, stop
the hash service, restore those three boot files and the saved manifest to
`/opt/zybo/hash/dfx_manifest.json`, restore `payload.json` to `/opt/zybo/hash/payload.json`, sync, and reboot the hash profile. The rescue
profile and shared SD data are retained.
