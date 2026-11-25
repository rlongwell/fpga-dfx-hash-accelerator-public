# Resume an interrupted measurement from its verified synthesis checkpoint.
if {[llength $argv] != 2} { error "usage: engine_resume.tcl <root> <engine>" }
set root [file normalize [lindex $argv 0]]
set engine [lindex $argv 1]
if {$engine ni {sha3 sha256 blake2s sha3_wide sha3_serial sha3_fast sha3_compact}} { error "Unknown engine" }
if {![string match "2024.2*" [version -short]]} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
open_checkpoint $root/build/engines/$engine/synthesized.dcp
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
