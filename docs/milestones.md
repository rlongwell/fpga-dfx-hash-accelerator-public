# Acceptance criteria

Stages proceed in this order. A failed check must be corrected before relying on that stage. The [current evidence guide](review-guide.md) records which criteria have physical results and which still require external equipment; offline checks do not substitute for board acceptance.

1. **Architecture:** documented PS/PL split, real RP boundary, interface, register map, clocks, DMA framing, dependencies and source provenance. Inspect installed tools and board preset.
2. **Oxide simulation:** pinned unchanged reference, reproducible independent compile/elaboration and hashlib agreement for nonempty messages, stalls/repeated operations/reset. Explicitly document the empty-input limitation and any compatibility adapter.
3. **Oxide synthesis:** reproducible 2024.2 synthesis for the actual Zynq part; resource and timing reports for both DOUBLE_BUFFER settings; identify measurement scope and timing constraint.
4. **Static interface:** self-checking simulation of length framing, arbitrary chunk TLAST, backpressure, error handling, reset/abort, result stability and isolation.
5. **DMA integration:** generated PS7/DMA block design validates, synthesizes, has assigned addresses and HP DDR connectivity. Actual DDR transfer acceptance requires the board.
6. **Additional algorithms:** common-interface SHA-256 and BLAKE2s pass independent hashlib vectors, protocol stress, and synthesizability checks.
7. **DFX build:** implemented static design and three RMs; routed timing and DRC reviewed; pr_verify passes; full and partial bitstreams emitted with sizes and hashes in a build manifest.
8. **Runtime switching:** software sequence and failure behavior implemented and tested where possible; board test must hash before/after actual PCAP switching while Ethernet stays operational.
9. **Ethernet streaming:** bounded-memory PS receive/DMA flow and host client, protocol/error tests offline; large-file Ethernet correctness and performance require hardware.
10. **SHA3 optimization:** direct-state digest, reduced buffering, narrower round datapath and wider input variants verified; compare measured results under identical tool constraints. Negative results are retained.
11. **Release evidence:** reproducible commands, actual results, attribution, loading instructions, limitations, no generated artifacts in source paths, and a status matrix separating simulation/synthesis/implementation/hardware.
