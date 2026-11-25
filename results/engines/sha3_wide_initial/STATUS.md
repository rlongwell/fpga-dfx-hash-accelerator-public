# Incomplete initial wide-absorption synthesis

The initial source passed all 79 hashlib vectors in both traffic modes. Its eight indexed byte writes into the full state produced an expensive synthesis optimization problem. The Vivado job was stopped after roughly six minutes, including several minutes in timing optimization, to replace that structure with one masked 128-bit alignment network and static per-lane enables.

`source.sv` and `incomplete_synthesis.log` retain the attempted implementation. No completed synthesis utilization, routed timing, or area claim exists for this version. The current `sha3_wide` measurement and source use the revised, independently retested structure.
