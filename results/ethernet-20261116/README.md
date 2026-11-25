# Physical TCP Ethernet baseline — 2026-11-16

The physical Zybo Z7-20 and PC negotiated 1000 Mb/s, full duplex. The isolated
link uses PC `10.77.78.1/30` and board `10.77.78.2/30`, without gateway or DNS.
The PC's pre-existing `10.77.77.1/30` connection and peer were preserved.

The input is the same 1,073,741,824-byte random-text file generated on the board
for the [SD experiment](../sha3-text-1gib-20261116/README.md). A one-time Ethernet
copy to the PC was independently checked against both recorded digests; that
copy is excluded from every hashing measurement. Payload data was not sent
over UART.

| TCP receive mode | SHA3-256 implementation | Median seconds | Decimal MB/s | Observed seconds |
| --- | --- | ---: | ---: | --- |
| Direct into DMA mapping | Oxide Quartz, full-rate adapter | 13.732343 | 78.191 | 13.618182–13.865640 |
| Direct into DMA mapping | Compact | 12.210009 | 87.939 | 12.043424–12.225680 |
| Cached prefetch thread | Oxide Quartz, full-rate adapter | 15.859448 | 67.704 | 15.849027–16.021942 |
| Cached prefetch thread | Compact | 15.750965 | 68.170 | 15.694273–15.926205 |

Each median uses three physical trials, with interleaved order and a 16 MiB
warmup before every measured file. All 12 full-file and 12 warmup digests
matched software references. Each selection forced SHA-256 ID 2 before loading
the requested SHA3 partial and observing ID 1. The unchanged static image and
partial checksums are recorded in the board report.

The direct TCP path shows a **1.125×** median end-to-end speed ratio on this run.
The cached prefetch experiment regressed; the installed default was returned to
`direct`. These results include PC file access, TCP, Linux receive processing,
DMA and hashing. They are not direct-GEM/FPGA-memory or pure-core measurements.
The latter design is documented [separately](../../docs/gem-direct.md).

- [Client samples and timing scope](comparison-host.json)
- [Board samples, image identities, counters and successful compact restoration](comparison-board.json)
- [Input-copy and independent digest checks](input-check.json)
- [Final service/profile confirmation](baseline-finish.log)

Oxide attribution and integration boundaries remain in
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md). This is a benchmark of
the pinned Quartz SHA3 core in this Zynq integration, not Oxide's production system.
