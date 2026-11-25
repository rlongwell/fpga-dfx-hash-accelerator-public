# Hash data generated on the processing system

The existing FPGA design already supports direct ARM-to-FPGA hashing. Ethernet
is an optional input source. `software/hash_local.py` exposes the same hardware
through a local Python API and CLI:

```text
ARM application / file / stdin
          ↓
1 MiB coherent DDR buffer → AXI DMA → selected PL hash engine
          ↑                              ↓
       Linux driver ← digest and hardware cycle count
```

This is a software interface to the existing hash profile, so it needs no new
bitstream, device tree, kernel, or SD image. It supports SHA3-256 (`sha3`),
SHA-256 (`sha256`) and unkeyed BLAKE2s-256 (`blake2s`). Algorithm changes load the
matching partial image through the existing driver and FPGA Manager.

## Run on the shared SD card

Boot the `hash` profile. The local interface and TCP service share one exclusive
device, so stop the service before using the direct interface. Stopping the
shared service also unloads its module; reload it for local use:

```sh
/opt/zybo/hash/start.sh stop
modprobe hash_accel

python3 /opt/zybo/hash/software/hash_local.py --text abc --algorithm sha256 --verify
printf abc | python3 /opt/zybo/hash/software/hash_local.py - --length 3 --algorithm sha3 --verify
python3 /opt/zybo/hash/software/hash_local.py /root/input.bin --algorithm blake2s --verify

# After closing all direct clients, restore the TCP service:
/opt/zybo/hash/start.sh start
```

These commands run on the Zybo's ARM processor, for example in its UART shell.
The file example requires your own existing input file. Text is encoded as
UTF-8; `--text ''` hashes an empty message. Files and stdin accept arbitrary
binary bytes. stdin needs its exact byte length because the hardware uses the
declared message length to finalize the digest.

The JSON result includes the digest, actual algorithm ID, core cycles, completed
DMA submission count, and FPGA Manager load time. An already selected algorithm
has zero load time. Manager time includes firmware retrieval and configuration;
it is not a measurement of PCAP bus transfer alone. `--verify` independently
checks the FPGA digest with Python `hashlib`. It includes that reference work in
`local_hash_ns`, as flagged in the result. Leave verification off for normal
application hashing. There is no software hash fallback when hardware fails.

## Call from your ARM application

Put `/opt/zybo/hash/software` on `PYTHONPATH`, or add that directory to your
application's module search path:

```python
from hash_local import LocalHasher

with LocalHasher() as accelerator:
    result = accelerator.hash_bytes(b"data produced by my ARM application", "sha256")
    print(result["digest"])
    # Reuses the owner and switches the physical partition when necessary.
    result = accelerator.hash_bytes(bytearray(range(256)), "blake2s")
```

`hash_bytes` accepts contiguous bytes, bytearrays and memoryviews. `hash_file`
accepts a regular-file path. `hash_stream(reader, length, algorithm)` accepts a
blocking binary reader with `readinto()`. It tolerates short reads, consumes
exactly the declared length, and leaves any trailing input for the next job.
Premature EOF or a reader/DMA error aborts the job before reuse. A blocking
reader must eventually produce data or EOF; this API imposes no reader timeout.

Input memory and files must remain unchanged until the call returns. A single
`LocalHasher` serializes calls and owns the device until `close()` or context
exit. Multiple independent owners are rejected with a busy error. The helper
copies one chunk at a time into the coherent buffer and waits for each DMA
submission to complete before reusing it. Memory use is bounded independently
of stream/file size. An empty input needs no DMA submission.

## Reproduce verification

Host checks use an explicit mock backend and do not claim physical FPGA results:

```sh
./scripts/test_software.sh
```

The separate physical harness requires the installed helper, the matching
hash profile, and an idle device. Run it on the Zybo with the service stopped
and module loaded:

```sh
python3 software/tests/board_local.py --output /root/local-ps-results.json
```

It compares memory, file, pipe and text digests with independent references;
checks empty, hash-block and 1 MiB DMA boundaries; verifies real algorithm IDs,
cycle counts and switching away/back; and tests recovery after a truncated
multi-buffer stream. The API portion forbids socket creation, and the harness
requires the TCP service to be absent. CLI subprocesses use the same direct
device code. It restores the SHA3 personality; restart the service afterward.
The retained [physical evidence](../results/local-ps-20261115/physical.json) is
separate from [host unit-test output](../results/local-ps-20261115/host-tests.log).

The historical standalone `sdcard.img` is not rebuilt by installing this
helper. A subsequent `./build.sh embedded package` includes it in the
normal software payload. Shared-SD assembly also accepts the helper using its
source-hashed physical validation receipt. Existing full/partial images,
kernel, driver and boot selection stay unchanged.
