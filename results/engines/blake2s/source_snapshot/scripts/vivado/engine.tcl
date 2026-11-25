# Common OOC measurement flow. Mirrors baseline.tcl constraints/methodology.
if {[llength $argv] != 2} { error "usage: engine.tcl <project_root> <engine>" }
set project_root [file normalize [lindex $argv 0]]
set engine [lindex $argv 1]
if {![string match "2024.2*" [version -short]]} { error "Vivado 2024.2 required" }
switch $engine {
    sha3 { set source rtl/sha3/hash_sha3.sv }
    sha256 { set source rtl/sha256/hash_sha256.sv }
    blake2s { set source rtl/blake2s/hash_blake2s.sv }
    sha3_wide - sha3_serial { set source rtl/sha3/experiments/hash_${engine}.sv }
    default { error "Unknown engine $engine" }
}
set_param general.maxThreads 2
read_verilog -sv [list $project_root/rtl/common/axis_bytes.sv \
    $project_root/$source $project_root/rtl/rm/${engine}.sv]
set fp [open engine.xdc w]
puts $fp {create_clock -name core_clk -period 10.000 [get_ports aclk]}
puts $fp {set_property HD.CLK_SRC BUFGCTRL_X0Y0 [get_ports aclk]}
puts $fp {set_input_delay 2.000 -clock core_clk [get_ports -filter {DIRECTION == IN && NAME != aclk && NAME != aresetn}]}
puts $fp {set_output_delay 2.000 -clock core_clk [all_outputs]}
puts $fp {set_false_path -from [get_ports aresetn]}
close $fp
read_xdc engine.xdc
synth_design -top hash_rm -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt
report_utilization -file synthesis_utilization.rpt
report_timing_summary -file synthesis_timing.rpt
write_checkpoint -force synthesized.dcp
opt_design
place_design
phys_opt_design
route_design
report_utilization -file routed_utilization.rpt
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file routed_timing.rpt
report_timing -from [all_registers -clock core_clk] -to [all_registers -clock core_clk] \
    -max_paths 10 -file routed_register_timing.rpt
report_drc -file routed_drc.rpt
report_route_status -file route_status.rpt
report_design_analysis -congestion -file congestion.rpt
write_checkpoint -force routed.dcp
set worst_setup [get_timing_paths -delay_type max -max_paths 1]
set worst_hold [get_timing_paths -delay_type min -max_paths 1]
set register_setup [get_timing_paths -delay_type max -from [all_registers -clock core_clk] \
    -to [all_registers -clock core_clk] -max_paths 1]
if {[llength $worst_setup] == 0 || [llength $register_setup] == 0} {
    error "No constrained timing paths found"
}
set fp [open summary.tsv w]
puts $fp "engine\t$engine"
puts $fp "part\txc7z020clg400-1"
puts $fp "vivado\t[version -short]"
puts $fp "period_ns\t10.0"
puts $fp "input_delay_ns\t2.0"
puts $fp "output_delay_ns\t2.0"
puts $fp "setup_wns_ns\t[get_property SLACK $worst_setup]"
puts $fp "hold_whs_ns\t[get_property SLACK $worst_hold]"
puts $fp "register_setup_wns_ns\t[get_property SLACK $register_setup]"
puts $fp "register_data_path_delay_ns\t[get_property DATAPATH_DELAY $register_setup]"
close $fp
exit
