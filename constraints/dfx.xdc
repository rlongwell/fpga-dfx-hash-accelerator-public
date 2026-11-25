# Right-hand upper two clock regions of xc7z020clg400-1.
# Explicit resource ranges are required for 7-series DFX; CLOCKREGION ranges
# alone are not a valid substitute with SNAPPING_MODE.
create_pblock pblock_hash
add_cells_to_pblock [get_pblocks pblock_hash] [get_cells u_hash]
resize_pblock [get_pblocks pblock_hash] -add {SLICE_X50Y50:SLICE_X113Y149 RAMB18_X3Y20:RAMB18_X5Y59 RAMB36_X3Y10:RAMB36_X5Y29 DSP48_X3Y20:DSP48_X4Y59}
set_property SNAPPING_MODE ON [get_pblocks pblock_hash]
set_property RESET_AFTER_RECONFIG true [get_pblocks pblock_hash]
set_property CONTAIN_ROUTING true [get_pblocks pblock_hash]
set_property EXCLUDE_PLACEMENT true [get_pblocks pblock_hash]
