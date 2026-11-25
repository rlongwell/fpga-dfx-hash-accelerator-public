# Invoked by scripts/build_baseline.sh; all generated files stay in build/.
if {[llength $argv] ni {2 3}} { error "usage: baseline.tcl <project_root> <false|true> ?core_source?" }
set project_root [file normalize [lindex $argv 0]]
set buffering [lindex $argv 1]
if {$buffering ni {false true}} { error "invalid DOUBLE_BUFFER setting" }
if {![string match "2024.2*" [version -short]]} { error "This comparison is pinned to Vivado 2024.2" }
set out_dir [pwd]
set reference [file join $project_root reference oxide hdl ip vhd]
set core_source [file join $reference sha3 sha3_256.vhd]
if {[llength $argv] == 3} { set core_source [file normalize [lindex $argv 2]] }
set_param general.maxThreads 4
read_vhdl -vhdl2019 [list \
    [file join $reference axi_blocks axist_if_2k19_pkg.vhd] \
    [file join $reference common utils calc_pkg.vhd] \
    [file join $reference sha3 keccak_pkg.vhd] \
    $core_source \
    [file join $project_root sim baseline baseline_wrapper.vhd]]
set constraint_file [open [file join $out_dir baseline.xdc] w]
puts $constraint_file {create_clock -name core_clk -period 10.000 [get_ports clk]}
puts $constraint_file {set_property HD.CLK_SRC BUFGCTRL_X0Y0 [get_ports clk]}
puts $constraint_file {set_input_delay 2.000 -clock core_clk [get_ports -filter {DIRECTION == IN && NAME != clk && NAME != reset}]}
puts $constraint_file {set_output_delay 2.000 -clock core_clk [all_outputs]}
puts $constraint_file {set_false_path -from [get_ports reset]}
close $constraint_file
read_xdc [file join $out_dir baseline.xdc]
synth_design -top baseline_wrapper -part xc7z020clg400-1 -mode out_of_context \
    -flatten_hierarchy rebuilt -generic DOUBLE_BUFFER=$buffering
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
write_checkpoint -force routed.dcp
set worst_setup [get_timing_paths -delay_type max -max_paths 1]
set worst_hold [get_timing_paths -delay_type min -max_paths 1]
set register_setup [get_timing_paths -delay_type max -from [all_registers -clock core_clk] \
    -to [all_registers -clock core_clk] -max_paths 1]
if {[llength $worst_setup] == 0 || [llength $register_setup] == 0} {
    error "No constrained timing paths found"
}
set summary [open summary.tsv w]
puts $summary "double_buffer\t$buffering"
puts $summary "part\txc7z020clg400-1"
puts $summary "vivado\t[version -short]"
puts $summary "period_ns\t10.0"
puts $summary "input_delay_ns\t2.0"
puts $summary "output_delay_ns\t2.0"
puts $summary "setup_wns_ns\t[get_property SLACK $worst_setup]"
puts $summary "hold_whs_ns\t[get_property SLACK $worst_hold]"
puts $summary "register_setup_wns_ns\t[get_property SLACK $register_setup]"
puts $summary "register_data_path_delay_ns\t[get_property DATAPATH_DELAY $register_setup]"
close $summary
exit
