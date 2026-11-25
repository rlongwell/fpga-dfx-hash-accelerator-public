# Analyze the SAME physical route under a slower clock. This does not reroute.
if {[llength $argv] != 3} { error "usage: engine_clock_analysis.tcl <root> <engine> <period_ns>" }
set root [file normalize [lindex $argv 0]]
set engine [lindex $argv 1]
set period [lindex $argv 2]
if {$engine ni {sha3 sha256 blake2s sha3_wide sha3_serial}} { error "Unknown engine" }
if {![string is double -strict $period] || $period < 10.0} { error "Use a period >= 10 ns" }
set_param general.maxThreads 2
open_checkpoint $root/build/engines/$engine/routed.dcp
create_clock -name core_clk -period $period [get_ports aclk]
set_property HD.CLK_SRC BUFGCTRL_X0Y0 [get_ports aclk]
set_input_delay 2.000 -clock core_clk [get_ports -filter {DIRECTION == IN && NAME != aclk && NAME != aresetn}]
set_output_delay 2.000 -clock core_clk [all_outputs]
set_false_path -from [get_ports aresetn]
report_clocks -file clocks.rpt
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file routed_timing.rpt
report_timing -from [all_registers -clock core_clk] -to [all_registers -clock core_clk] \
    -max_paths 10 -file routed_register_timing.rpt
check_timing -verbose -file clock_coverage.rpt
report_utilization -file routed_utilization.rpt
report_route_status -file route_status.rpt
set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
set reg_setup [get_timing_paths -delay_type max -from [all_registers -clock core_clk] \
    -to [all_registers -clock core_clk] -max_paths 1]
if {[llength $setup] == 0 || [llength $hold] == 0 || [llength $reg_setup] == 0} {
    error "No constrained paths"
}
set fp [open summary.tsv w]
puts $fp "engine\t$engine"
puts $fp "analysis_type\tclock reanalysis of unchanged 100 MHz physical route"
puts $fp "part\txc7z020clg400-1"
puts $fp "vivado\t[version -short]"
puts $fp "period_ns\t$period"
puts $fp "input_delay_ns\t2.0"
puts $fp "output_delay_ns\t2.0"
puts $fp "setup_wns_ns\t[get_property SLACK $setup]"
puts $fp "hold_whs_ns\t[get_property SLACK $hold]"
puts $fp "register_setup_wns_ns\t[get_property SLACK $reg_setup]"
puts $fp "register_data_path_delay_ns\t[get_property DATAPATH_DELAY $reg_setup]"
close $fp
write_checkpoint -force clock_reanalysis.dcp
if {[get_property SLACK $setup] < 0 || [get_property SLACK $hold] < 0} {
    error "Timing failed at requested analysis clock; inspect saved reports"
}
exit
