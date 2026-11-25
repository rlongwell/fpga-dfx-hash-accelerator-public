# Targeted physical repair of the unchanged Quartz buffer-enable net.
# Retains the accepted compact/static layout and checks full PR compatibility.
if {[llength $argv] != 1} { error "Usage: gem_oxide_fanout.tcl ROOT" }
set root [file normalize [lindex $argv 0]]
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
source [file join $root scripts vivado net_checks.tcl]
source [file join $root scripts vivado net_rm_cache.tcl]
puts [exec sha256sum --check [file join $root build gem-direct system static_sources.sha256]]
foreach {path expected} [dict get $cache_inputs oxide] {
    if {[lindex [exec sha256sum [file join $root $path]] 0] ne $expected} {
        error "Quartz source changed: $path"
    }
}
set out [file join $root build gem-direct oxide-fanout]
if {[file exists $out]} { error "Use a fresh fanout-repair directory" }
file mkdir $out
set dfx [file join $root build gem-direct dfx]
file copy [file join $dfx oxide routed.dcp] [file join $out input.dcp]
set script [file join $root scripts vivado gem_oxide_fanout.tcl]
set script_hash [lindex [exec sha256sum $script] 0]
open_checkpoint [file join $out input.dcp]
set enable_net {}
# NAME filters interpret bracketed bus indices as patterns, even with ==.
foreach candidate [get_nets -hierarchical -filter {NAME =~ *feed_reg*1087*}] {
    if {[string equal [get_property NAME $candidate] {u_hash/core/core/feed_reg[buf][1][1087]_i_1_n_0}]} {
        lappend enable_net $candidate
    }
}
if {[llength $enable_net] != 1} { error "Expected diagnosed buffer-enable net is absent" }
phys_opt_design -directive Explore
# Post-route physical optimization can leave a fully routed result. Do not
# discard that routing and repeat a global router pass unless nets need it.
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
puts [exec sha256sum --check [file join $root build gem-direct system static_sources.sha256]]
foreach name {routed.dcp route_status.rpt routed_drc.rpt routed_timing.rpt routed_utilization.rpt} {
    file copy -force [file join $out $name] [file join $dfx oxide $name]
}
set f [open [file join $out ACCEPTED.sha256] w]
foreach path [concat [list $script] [glob [file join $out *.dcp] [file join $out *.rpt]]] {
    puts $f [exec sha256sum $path]
}
close $f
puts "NET_OXIDE_FANOUT_PASS"
exit
