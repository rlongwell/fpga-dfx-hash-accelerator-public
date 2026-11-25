# Non-project DFX flow: build every RM, preserve one routed static image, verify
# compatibility, and only then produce full/partial programming images.
proc require_clean_drc {report_path {checks {}}} {
    if {[llength $checks]} {
        report_drc -checks $checks -file $report_path
    } else {
        report_drc -file $report_path
    }
    set bad [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]
    if {[llength $bad]} { error "DRC failed ($bad); see $report_path" }
}
proc require_timing {report_path} {
    report_timing_summary -delay_type min_max -report_unconstrained -file $report_path
    set fh [open $report_path r]
    set report [read $fh]
    close $fh
    foreach check {no_clock unconstrained_internal_endpoints} {
        set pattern [format {checking %s \(([0-9]+)\)} $check]
        if {![regexp $pattern $report unused count]} { error "Missing $check coverage in $report_path" }
        if {$count != 0} { error "$count $check timing violations; see $report_path" }
    }
    foreach type {max min} {
        set paths [get_timing_paths -quiet -delay_type $type -max_paths 1]
        if {![llength $paths]} { error "No $type timing paths were analyzed" }
        set slack [get_property SLACK [lindex $paths 0]]
        if {$slack < 0.0} { error "$type timing failed: slack $slack ns; see $report_path" }
        puts "DFX_TIMING_PASS $type slack=$slack"
    }
    # Setup/hold checks do not replace clock pulse-width checks.
    set pulse_checks [regexp -all -inline {PW\s*:\s*([0-9]+)\s+Failing Endpoints,\s+Worst Slack\s+([-0-9.]+)ns} $report]
    if {![llength $pulse_checks]} { error "Missing pulse-width timing checks; see $report_path" }
    foreach {match count slack} $pulse_checks {
        if {$count != 0 || $slack < 0.0} { error "Pulse-width timing failed; see $report_path" }
    }
}
proc require_routing {report_path} {
    report_route_status -file $report_path
    set fh [open $report_path r]
    set report [read $fh]
    close $fh
    foreach label {{nets with routing errors} {routable nets} {fully routed nets}} key {errors routable routed} {
        set pattern [format {# of %s[. ]*:\s*([0-9]+)} $label]
        if {![regexp $pattern $report unused count]} { error "Missing route status: $label in $report_path" }
        set $key $count
    }
    if {$errors != 0 || $routable != $routed} { error "Incomplete or invalid routing; see $report_path" }
}
# Bubble-free adapter for Oxide; unchanged pinned hash core, medium spreading placement after congestion in the high-spreading route.
# Build a SHA3 replacement against the existing locked static configuration.
# Never changes production artifacts. Every output must pass full pr_verify.
if {[llength $argv] != 2} { error "usage: sha3_variant.tcl ROOT fast|oxide" }
set root [file normalize [lindex $argv 0]]
set variant [lindex $argv 1]
if {$variant ni {fast oxide}} { error "Unsupported variant" }
if {[version -short] ne "2024.2"} { error "Vivado 2024.2 required" }
set_param general.maxThreads 2
set original [file join $root build vivado dfx]
set expected_static 0e14c2e8fc216b0b2c72d1788f902e61124da197dd17cb213c5c1ae4752ba7f9
if {[lindex [exec sha256sum [file join $original sha3 full.bit]] 0] ne $expected_static} {
    error "This variant build requires the accepted original static image"
}
set sources [list [file join $root rtl sha3 oxide_compare axis_bytes_elastic.sv] [file join $root rtl rm sha3_${variant}.sv]]
if {$variant eq "oxide"} {
    set ref [file join $root reference oxide hdl ip vhd]
    set vhdl [list [file join $ref axi_blocks axist_if_2k19_pkg.vhd] \
        [file join $ref common utils calc_pkg.vhd] [file join $ref sha3 keccak_pkg.vhd] \
        [file join $ref sha3 sha3_256.vhd] [file join $root rtl sha3 oxide_compare sha3_oxide_core.vhd]]
} else {
    lappend sources [file join $root rtl sha3 experiments hash_sha3_fast.sv]
    set vhdl {}
}
set recorded [concat $sources $vhdl [list [info script] \
    [file join $original static_locked.dcp] [file join $original sha3 routed.dcp] \
    [file join $original sha256 routed.dcp] [file join $original blake2s routed.dcp]]]
set fh [open sources.sha256 w]
foreach path $recorded { puts $fh [exec sha256sum $path] }
close $fh
create_project -in_memory -part xc7z020clg400-1
if {[llength $vhdl]} { read_vhdl -vhdl2019 $vhdl }
read_verilog -sv $sources
set fh [open rm_ooc.xdc w]
puts $fh {create_clock -name aclk -period 10.000 [get_ports aclk]}
close $fh
read_xdc rm_ooc.xdc
set_property USED_IN {synthesis implementation out_of_context} [get_files rm_ooc.xdc]
synth_design -top hash_rm -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt
write_checkpoint -force rm_synth.dcp
report_utilization -hierarchical -file synth_utilization.rpt
close_project
open_checkpoint [file join $original static_locked.dcp]
read_checkpoint -strict -cell u_hash rm_synth.dcp
require_clean_drc floorplan_drc.rpt [get_drc_checks HDPR*]
opt_design
place_design -directive AltSpreadLogic_medium
phys_opt_design
route_design
write_checkpoint -force routed.dcp
report_utilization -hierarchical -file routed_utilization.rpt
require_routing route_status.rpt
require_clean_drc routed_drc.rpt
require_timing routed_timing.rpt
close_project
foreach name {sha3 sha256 blake2s} {
    pr_verify -full_check -file pr_verify_${name}.rpt [file join $original $name routed.dcp] routed.dcp
}
puts [exec sha256sum --check sources.sha256]
open_checkpoint routed.dcp
write_bitstream -force full.bit
close_project
set partial [file normalize full_pblock_hash_partial.bit]
if {![file exists $partial]} { error "Missing partial bitstream" }
set fh [open partial.bif w]
puts $fh "all:\n\{\n  \"$partial\"\n\}"
close $fh
puts [exec /opt/amd/xilinx/Vivado/2024.2/bin/bootgen -arch zynq -image partial.bif -process_bitstream bin -w on 2>@1]
puts "SHA3_VARIANT_PASS $variant"
exit 0
