# Standalone custom IP

The workspace audit extracted the reusable blocks below using **Core Forge**. Each repository contains its own public interface, namespaced original RTL, functional regression, dashboard and versioned Vivado package. The source links below open the original RTL for each block in this repository.

| IP | Original RTL |
| --- | --- |
| SHA-256 IP | [`rtl/sha256/hash_sha256.sv`](../rtl/sha256/hash_sha256.sv) |
| SHA3-256 IP | [`rtl/sha3/hash_sha3.sv`](../rtl/sha3/hash_sha3.sv) |
| BLAKE2s-256 IP | [`rtl/blake2s/hash_blake2s.sv`](../rtl/blake2s/hash_blake2s.sv) |
| SHA3-256 Wide IP | [`rtl/sha3/experiments/hash_sha3_wide.sv`](../rtl/sha3/experiments/hash_sha3_wide.sv) |
| SHA3-256 Serial IP | [`rtl/sha3/experiments/hash_sha3_serial.sv`](../rtl/sha3/experiments/hash_sha3_serial.sv) |
| AXI Stream Byte Unpacker | [`rtl/common/axis_bytes.sv`](../rtl/common/axis_bytes.sv) |

The parent project continues to build from its existing source tree. Extraction preserves algorithm logic; private module names prevent collisions between packaged IPs. Each standalone repo records the parent commit, exact source hashes, regression scope and package checksums in its provenance and release manifests.

The wide and serialized SHA3 designs are explicitly labeled architecture experiments. The MPL-2.0 Oxide baseline and digest-storage comparison remain here with their attribution. The static shell, DMA/control registers and DFX wrappers remain part of this system.

Standalone verification covers real RTL simulation, Core Forge release snapshots, Vivado IP Catalog import and out-of-context synthesis. It does not imply placed/routed timing closure or physical board validation. The workspace audit and package manifests record the publication and verification evidence.
