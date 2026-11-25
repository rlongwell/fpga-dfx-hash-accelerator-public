# Repair one routed RM without rerunning accepted static or other RM placement.
if {[llength $argv] < 2 || [llength $argv] > 3} { error "Usage: gem_postroute.tcl ROOT oxide|sha256|blake2s ?DIRECTIVE?" }
lassign $argv root name directive
if {$directive eq ""} { set directive Explore }
if {$directive ni {Explore AggressiveExplore AlternateReplication}} { error "Unsupported repair directive" }
set root [file normalize $root]
if {$name ni {oxide sha256 blake2s}} { error "The accepted compact/static layout must be retained" }
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
source [file join $root scripts vivado net_checks.tcl]
source [file join $root scripts vivado net_rm_cache.tcl]
set build [file join $root build gem-direct]
set dfx [file join $build dfx]
set out [file join $build postroute-$name-$directive]
if {[file exists $out]} { error "Use a fresh repair directory" }
puts [exec sha256sum --check [file join $build system static_sources.sha256]]
foreach core {compact oxide sha256 blake2s} {
    foreach {path expected} [dict get $cache_inputs $core] {
        if {[lindex [exec sha256sum [file join $root $path]] 0] ne $expected} {
            error "Core source changed: $path"
        }
    }
}
file mkdir $out
file copy [file join $dfx $name routed.dcp] [file join $out input.dcp]
set script [file join $root scripts vivado gem_postroute.tcl]
set script_hash [lindex [exec sha256sum $script] 0]
open_checkpoint [file join $out input.dcp]
require_routing [file join $out input_route_status.rpt]
report_timing -max_paths 30 -slack_lesser_than 0 -file [file join $out input_failing_paths.rpt]
phys_opt_design -directive $directive
if {[catch {require_routing [file join $out after_physopt_route_status.rpt]}]} {
    route_design -directive Explore
}
write_checkpoint -force [file join $out routed.dcp]
require_routing [file join $out route_status.rpt]
require_clean_drc [file join $out routed_drc.rpt]
require_timing [file join $out routed_timing.rpt]
report_utilization -hierarchical -file [file join $out routed_utilization.rpt]
close_project
pr_verify -full_check -file [file join $out pr_verify.rpt] \
    [file join $dfx compact routed.dcp] [file join $out routed.dcp]
if {[lindex [exec sha256sum $script] 0] ne $script_hash} { error "Repair script changed during execution" }
puts [exec sha256sum --check [file join $build system static_sources.sha256]]
foreach file {routed.dcp route_status.rpt routed_drc.rpt routed_timing.rpt routed_utilization.rpt} {
    file copy -force [file join $out $file] [file join $dfx $name $file]
}
set f [open [file join $out ACCEPTED.sha256] w]
foreach path [concat [list $script] [glob [file join $out *.dcp] [file join $out *.rpt]]] {
    puts $f [exec sha256sum $path]
}
close $f
puts "NET_POSTROUTE_PASS $name"
exit
