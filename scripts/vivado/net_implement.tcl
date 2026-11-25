# Separate static build: old and new partial bitstreams must NEVER be mixed.
if {[llength $argv] != 1} { error "Usage: net_implement.tcl ROOT" }
set root [file normalize [lindex $argv 0]]
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
source [file join $root scripts vivado net_checks.tcl]
set out [file join $root build gem-direct dfx]
file mkdir $out
file delete -force [file join $root build gem-direct ACCEPTED.sha256]
foreach old [glob -nocomplain [file join $out * *.bit] [file join $out * *.bin]] {
    file delete -force $old
}
set static [file join $root build gem-direct system static_synth.dcp]
puts [exec sha256sum --check [file join $root build gem-direct system static_sources.sha256]]
set caches [dict create \
    compact {build/sha3-profile/compact/rm_synth.dcp a40ca69240c5bc48e100b59a4d1aa4b747119fb2a206f038f03c18eab1567a1d} \
    oxide {build/sha3-profile/oxide-elastic-medium/rm_synth.dcp 8c70ab4404a217215fbeb3f4957a3e1b8c7ba80754692dbe8c0d8c6f5223e841} \
    sha256 {build/vivado/dfx/sha256/rm_synth.dcp 54c749690850f12461de483b962dbc54c44dbff62f0de845236b1b6bf3d266dd} \
    blake2s {build/vivado/dfx/blake2s/rm_synth.dcp d909ba4eefd0b74317fe82cfec4c046eaffc407507704f7fdda366cf0ec5284b}]
source [file join $root scripts vivado net_rm_cache.tcl]
set first 1
foreach name {compact oxide sha256 blake2s} {
    set dir [file join $out $name]
    file mkdir $dir
    lassign [dict get $caches $name] cache expected
    set cache [file join $root $cache]
    set sources_match 1
    foreach {path expected_source} [dict get $cache_inputs $name] {
        if {![file exists [file join $root $path]] || [lindex [exec sha256sum [file join $root $path]] 0] ne $expected_source} {
            set sources_match 0
        }
    }
    if {$sources_match && [file exists $cache] && [lindex [exec sha256sum $cache] 0] eq $expected} {
        file copy -force $cache [file join $dir rm_synth.dcp]
        puts "NET_REUSE_UNCHANGED_RM $name sha256=$expected"
    } else {
        create_project -in_memory -part xc7z020clg400-1
        if {$name eq "oxide"} {
            set ref [file join $root reference oxide hdl ip vhd]
            read_vhdl -vhdl2019 [list [file join $ref axi_blocks axist_if_2k19_pkg.vhd] \
                [file join $ref common utils calc_pkg.vhd] [file join $ref sha3 keccak_pkg.vhd] \
                [file join $ref sha3 sha3_256.vhd] [file join $root rtl sha3 oxide_compare sha3_oxide_core.vhd]]
            read_verilog -sv [list [file join $root rtl sha3 oxide_compare axis_bytes_elastic.sv] \
                [file join $root rtl rm sha3_oxide.sv]]
        } elseif {$name eq "compact"} {
            read_verilog -sv [list [file join $root rtl common axis_bytes.sv] \
                [file join $root rtl sha3 experiments hash_sha3_compact.sv] [file join $root rtl rm sha3_compact.sv]]
        } else {
            read_verilog -sv [list [file join $root rtl common axis_bytes.sv] \
                [file join $root rtl $name hash_${name}.sv] [file join $root rtl rm ${name}.sv]]
        }
        set f [open [file join $dir clock.xdc] w]
        puts $f {create_clock -name aclk -period 10.000 [get_ports aclk]}
        close $f
        read_xdc [file join $dir clock.xdc]
        set_property USED_IN {synthesis implementation out_of_context} [get_files *.xdc]
        synth_design -top hash_rm -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt
        write_checkpoint -force [file join $dir rm_synth.dcp]
        close_project
    }
    if {$first} {
        open_checkpoint $static
        set_property HD.RECONFIGURABLE true [get_cells u_hash]
        read_xdc [file join $root constraints dfx.xdc]
    } else { open_checkpoint [file join $out static_locked.dcp] }
    read_checkpoint -strict -cell u_hash [file join $dir rm_synth.dcp]
    require_clean_drc [file join $dir floorplan_drc.rpt] [get_drc_checks HDPR*]
    opt_design
    place_design -directive AltSpreadLogic_medium
    phys_opt_design
    route_design
    write_checkpoint -force [file join $dir routed.dcp]
    set worst [get_property SLACK [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]]
    if {$worst < 0.0} {
        phys_opt_design -directive AggressiveExplore
        route_design
        write_checkpoint -force [file join $dir routed.dcp]
    }
    require_routing [file join $dir route_status.rpt]
    require_clean_drc [file join $dir routed_drc.rpt]
    require_timing [file join $dir routed_timing.rpt]
    report_utilization -hierarchical -file [file join $dir routed_utilization.rpt]
    if {$first} {
        update_design -cell u_hash -black_box
        lock_design -level routing
        write_checkpoint -force [file join $out static_locked.dcp]
        set first 0
    }
    close_project
}
foreach name {oxide sha256 blake2s} {
    pr_verify -full_check -file [file join $out pr_verify_${name}.rpt] \
        [file join $out compact routed.dcp] [file join $out $name routed.dcp]
}
# Refuse inputs changed while implementation was running.
puts [exec sha256sum --check [file join $root build gem-direct system static_sources.sha256]]
foreach name {compact oxide sha256 blake2s} {
    set dir [file join $out $name]
    open_checkpoint [file join $dir routed.dcp]
    write_bitstream -force [file join $dir full.bit]
    close_project
    set partial [file join $dir full_pblock_hash_partial.bit]
    set f [open [file join $dir partial.bif] w]
    puts $f "all:\n\{\n  \"$partial\"\n\}"
    close $f
    puts [exec /opt/amd/xilinx/Vivado/2024.2/bin/bootgen -arch zynq \
        -image [file join $dir partial.bif] -process_bitstream bin -w on 2>@1]
}
set seal [file join $root build gem-direct ACCEPTED.sha256]
set f [open ${seal}.pending w]
set input [open [file join $root build gem-direct system static_sources.sha256] r]
puts $f [string trim [read $input]]
close $input
foreach path [concat [list $static [file join $out static_locked.dcp] \
    [file join $root build gem-direct system static_sources.sha256]] \
    [glob [file join $out * *.dcp] [file join $out * *.bit] [file join $out * *.bin] \
    [file join $out * *.rpt] [file join $out pr_verify_*.rpt]]] {
    puts $f [exec sha256sum $path]
}
close $f
file rename -force ${seal}.pending $seal
puts "NET_IMPLEMENTATION_PASS"
exit 0
