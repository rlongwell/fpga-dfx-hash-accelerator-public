# Finish the two remaining RMs after the separately verified Quartz physical
# repair. No static synthesis, compact placement or Quartz RTL is repeated.
if {[llength $argv] != 1} { error "Usage: gem_finish.tcl ROOT" }
set root [file normalize [lindex $argv 0]]
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
source [file join $root scripts vivado net_checks.tcl]
source [file join $root scripts vivado net_rm_cache.tcl]
set build [file join $root build gem-direct]
set out [file join $build dfx]
puts [exec sha256sum --check [file join $build system static_sources.sha256]]
puts [exec sha256sum --check [file join $build oxide-fanout ACCEPTED.sha256]]
file delete -force [file join $build ACCEPTED.sha256]
foreach old [glob -nocomplain [file join $out * *.bit] [file join $out * *.bin]] { file delete -force $old }
set sources [file join $build remaining_sources.sha256]
set f [open $sources w]
foreach name {compact oxide sha256 blake2s} {
    foreach {path expected} [dict get $cache_inputs $name] {
        puts $f [exec sha256sum [file join $root $path]]
        if {$name in {compact oxide} && [lindex [exec sha256sum [file join $root $path]] 0] ne $expected} {
            error "Already implemented core source changed: $path"
        }
    }
}
foreach path [list [file join $root scripts vivado gem_finish.tcl] [file join $root scripts build_gem_direct.sh]] {
    puts $f [exec sha256sum $path]
}
close $f
foreach name {compact oxide} {
    set dir [file join $out $name]
    open_checkpoint [file join $dir routed.dcp]
    require_routing [file join $dir resume_route_status.rpt]
    require_clean_drc [file join $dir resume_drc.rpt]
    require_timing [file join $dir resume_timing.rpt]
    close_project
}
set caches [dict create \
    sha256 {build/vivado/dfx/sha256/rm_synth.dcp 54c749690850f12461de483b962dbc54c44dbff62f0de845236b1b6bf3d266dd} \
    blake2s {build/vivado/dfx/blake2s/rm_synth.dcp d909ba4eefd0b74317fe82cfec4c046eaffc407507704f7fdda366cf0ec5284b}]
foreach name {sha256 blake2s} {
    set dir [file join $out $name]
    file mkdir $dir
    lassign [dict get $caches $name] cache expected
    set cache [file join $root $cache]
    set sources_match 1
    foreach {path expected_source} [dict get $cache_inputs $name] {
        if {[lindex [exec sha256sum [file join $root $path]] 0] ne $expected_source} { set sources_match 0 }
    }
    if {$sources_match && [file exists $cache] && [lindex [exec sha256sum $cache] 0] eq $expected} {
        file copy -force $cache [file join $dir rm_synth.dcp]
        puts "NET_REUSE_UNCHANGED_RM $name sha256=$expected"
    } else {
        create_project -in_memory -part xc7z020clg400-1
        read_verilog -sv [list [file join $root rtl common axis_bytes.sv] \
            [file join $root rtl $name hash_${name}.sv] [file join $root rtl rm ${name}.sv]]
        set f [open [file join $dir clock.xdc] w]
        puts $f {create_clock -name aclk -period 10.000 [get_ports aclk]}
        close $f
        read_xdc [file join $dir clock.xdc]
        set_property USED_IN {synthesis implementation out_of_context} [get_files *.xdc]
        synth_design -top hash_rm -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt
        write_checkpoint -force [file join $dir rm_synth.dcp]
        close_project
    }
    open_checkpoint [file join $out static_locked.dcp]
    read_checkpoint -strict -cell u_hash [file join $dir rm_synth.dcp]
    require_clean_drc [file join $dir floorplan_drc.rpt] [get_drc_checks HDPR*]
    opt_design
    place_design -directive AltSpreadLogic_medium
    phys_opt_design
    route_design
    write_checkpoint -force [file join $dir routed.dcp]
    if {[get_property SLACK [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]] < 0.0} {
        phys_opt_design -directive AggressiveExplore
        route_design
        write_checkpoint -force [file join $dir routed.dcp]
    }
    require_routing [file join $dir route_status.rpt]
    require_clean_drc [file join $dir routed_drc.rpt]
    require_timing [file join $dir routed_timing.rpt]
    report_utilization -hierarchical -file [file join $dir routed_utilization.rpt]
    close_project
}
foreach name {oxide sha256 blake2s} {
    pr_verify -full_check -file [file join $out pr_verify_${name}.rpt] \
        [file join $out compact routed.dcp] [file join $out $name routed.dcp]
}
foreach record [list [file join $build system static_sources.sha256] $sources \
                    [file join $build oxide-fanout ACCEPTED.sha256]] {
    puts [exec sha256sum --check $record]
}
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
set seal [file join $build ACCEPTED.sha256]
set f [open ${seal}.pending w]
foreach record [list [file join $build system static_sources.sha256] $sources \
                    [file join $build oxide-fanout ACCEPTED.sha256]] {
    set input [open $record r]
    puts $f [string trim [read $input]]
    close $input
    puts $f [exec sha256sum $record]
}
foreach path [concat [list [file join $build system static_synth.dcp] [file join $out static_locked.dcp]] \
    [glob [file join $out * *.dcp] [file join $out * *.bit] [file join $out * *.bin] \
    [file join $out * *.rpt] [file join $out pr_verify_*.rpt]]] {
    puts $f [exec sha256sum $path]
}
close $f
file rename -force ${seal}.pending $seal
puts "NET_IMPLEMENTATION_PASS"
exit
