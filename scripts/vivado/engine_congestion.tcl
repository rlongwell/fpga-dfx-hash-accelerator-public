# Reopen completed OOC routes to collect congestion diagnostics without rebuilding.
if {[llength $argv] < 2} { error "usage: engine_congestion.tcl <root> <engine> ..." }
set root [file normalize [lindex $argv 0]]
set_param general.maxThreads 2
foreach engine [lrange $argv 1 end] {
    if {$engine ni {sha3 sha256 blake2s sha3_wide sha3_serial}} { error "Unknown engine $engine" }
    open_checkpoint $root/build/engines/$engine/routed.dcp
    report_design_analysis -congestion -file $root/results/engines/$engine/congestion.rpt
    close_design
}
exit
