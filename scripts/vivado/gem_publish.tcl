# Publish only a complete, rechecked set of already routed configurations.
if {[llength $argv] != 1} { error "Usage: gem_publish.tcl ROOT" }
set root [file normalize [lindex $argv 0]]
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
source [file join $root scripts vivado net_checks.tcl]
source [file join $root scripts vivado net_rm_cache.tcl]
set build [file join $root build gem-direct]
set out [file join $build dfx]
file delete -force [file join $build ACCEPTED.sha256]
set ledger [file join $build publish_inputs.sha256]
set f [open $ledger w]
foreach core {compact oxide sha256 blake2s} {
    foreach {path expected} [dict get $cache_inputs $core] {
        set actual [exec sha256sum [file join $root $path]]
        if {[lindex $actual 0] ne $expected} { error "Implemented core source changed: $path" }
        puts $f $actual
    }
    puts $f [exec sha256sum [file join $out $core routed.dcp]]
}
foreach path [list [file join $root scripts vivado gem_publish.tcl] \
                  [file join $root scripts build_gem_direct.sh] [file join $out static_locked.dcp]] {
    puts $f [exec sha256sum $path]
}
close $f
set records [concat [list [file join $build system static_sources.sha256] $ledger] \
    [glob -nocomplain [file join $build postroute-* ACCEPTED.sha256] [file join $build reimplement-* ACCEPTED.sha256]]]
foreach record $records { puts [exec sha256sum --check $record] }
foreach name {compact oxide sha256 blake2s} {
    set dir [file join $out $name]
    open_checkpoint [file join $dir routed.dcp]
    require_routing [file join $dir published_route_status.rpt]
    require_clean_drc [file join $dir published_drc.rpt]
    require_timing [file join $dir published_timing.rpt]
    report_utilization -hierarchical -file [file join $dir published_utilization.rpt]
    close_project
}
foreach name {oxide sha256 blake2s} {
    pr_verify -full_check -file [file join $out pr_verify_${name}.rpt] \
        [file join $out compact routed.dcp] [file join $out $name routed.dcp]
}
foreach record $records { puts [exec sha256sum --check $record] }
foreach name {compact oxide sha256 blake2s} {
    set dir [file join $out $name]
    open_checkpoint [file join $dir routed.dcp]
    write_bitstream -force [file join $dir full.bit]
    close_project
    set f [open [file join $dir partial.bif] w]
    puts $f "all:\n\{\n  \"[file join $dir full_pblock_hash_partial.bit]\"\n\}"
    close $f
    puts [exec /opt/amd/xilinx/Vivado/2024.2/bin/bootgen -arch zynq \
        -image [file join $dir partial.bif] -process_bitstream bin -w on 2>@1]
}
foreach record $records { puts [exec sha256sum --check $record] }
set seal [file join $build ACCEPTED.sha256]
set f [open ${seal}.pending w]
foreach record $records {
    set input [open $record r]
    puts $f [string trim [read $input]]
    close $input
    puts $f [exec sha256sum $record]
}
foreach path [concat [list [file join $build system static_synth.dcp]] \
    [glob [file join $out * *.dcp] [file join $out * *.bit] [file join $out * *.bin] \
    [file join $out * *.rpt] [file join $out pr_verify_*.rpt]]] {
    puts $f [exec sha256sum $path]
}
close $f
file rename -force ${seal}.pending $seal
puts "NET_IMPLEMENTATION_PASS"
exit
