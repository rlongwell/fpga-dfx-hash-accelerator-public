# Re-place one unchanged RM against the accepted, locked static design.
if {[llength $argv] != 3} { error "Usage: gem_reimplement.tcl ROOT oxide|sha256|blake2s DIRECTIVE" }
lassign $argv root name directive
set root [file normalize $root]
if {$name ni {oxide sha256 blake2s}} { error "Retain the accepted compact/static layout" }
if {$directive ni {Explore ExtraTimingOpt}} { error "Unsupported placement directive" }
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
source [file join $root scripts vivado net_checks.tcl]
source [file join $root scripts vivado net_rm_cache.tcl]
set build [file join $root build gem-direct]
set dfx [file join $build dfx]
set out [file join $build reimplement-$name-$directive]
if {[file exists $out]} { error "Use a fresh repair directory" }
puts [exec sha256sum --check [file join $build system static_sources.sha256]]
set expected_synth [dict create oxide 8c70ab4404a217215fbeb3f4957a3e1b8c7ba80754692dbe8c0d8c6f5223e841 \
    sha256 54c749690850f12461de483b962dbc54c44dbff62f0de845236b1b6bf3d266dd \
    blake2s d909ba4eefd0b74317fe82cfec4c046eaffc407507704f7fdda366cf0ec5284b]
if {[lindex [exec sha256sum [file join $dfx $name rm_synth.dcp]] 0] ne [dict get $expected_synth $name]} {
    error "RM synthesis checkpoint does not match the verified cache"
}
foreach core {compact oxide sha256 blake2s} {
    foreach {path expected} [dict get $cache_inputs $core] {
        if {[lindex [exec sha256sum [file join $root $path]] 0] ne $expected} { error "Core source changed: $path" }
    }
}
file mkdir $out
set ledger [file join $out inputs.sha256]
set f [open $ledger w]
foreach path [list [file join $root scripts vivado gem_reimplement.tcl] \
    [file join $root scripts vivado net_checks.tcl] [file join $root scripts vivado net_rm_cache.tcl] \
    [file join $dfx static_locked.dcp] [file join $dfx $name rm_synth.dcp]] {
    puts $f [exec sha256sum $path]
}
close $f
file copy [file join $dfx $name routed.dcp] [file join $out previous_routed.dcp]
open_checkpoint [file join $dfx static_locked.dcp]
read_checkpoint -strict -cell u_hash [file join $dfx $name rm_synth.dcp]
require_clean_drc [file join $out floorplan_drc.rpt] [get_drc_checks HDPR*]
opt_design
place_design -directive $directive
phys_opt_design -directive Explore
route_design -directive Explore
set worst [get_property SLACK [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]]
if {$worst < 0.0} {
    phys_opt_design -directive AggressiveExplore
    if {[catch {require_routing [file join $out after_physopt_route_status.rpt]}]} { route_design -directive Explore }
}
write_checkpoint -force [file join $out routed.dcp]
require_routing [file join $out route_status.rpt]
require_clean_drc [file join $out routed_drc.rpt]
require_timing [file join $out routed_timing.rpt]
report_utilization -hierarchical -file [file join $out routed_utilization.rpt]
close_project
pr_verify -full_check -file [file join $out pr_verify.rpt] \
    [file join $dfx compact routed.dcp] [file join $out routed.dcp]
puts [exec sha256sum --check $ledger]
puts [exec sha256sum --check [file join $build system static_sources.sha256]]
foreach file {routed.dcp route_status.rpt routed_drc.rpt routed_timing.rpt routed_utilization.rpt} {
    file copy -force [file join $out $file] [file join $dfx $name $file]
}
set f [open [file join $out ACCEPTED.sha256] w]
set input [open $ledger r]
puts $f [string trim [read $input]]
close $input
foreach path [concat [list $ledger] [glob [file join $out *.dcp] [file join $out *.rpt]]] {
    puts $f [exec sha256sum $path]
}
close $f
puts "NET_REIMPLEMENT_PASS $name $directive"
exit
