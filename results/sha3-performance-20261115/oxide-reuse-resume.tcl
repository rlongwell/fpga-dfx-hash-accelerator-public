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
# Elastic adapter with native-core placement retained from the accepted Oxide route.
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
set reference_route [file join $root build sha3-profile oxide-spread routed.dcp]
set recorded [concat $sources $vhdl [list [info script] $reference_route [file normalize rm_synth.dcp] [file normalize prior-synthesis.sources.sha256] \
    [file join $original static_locked.dcp] [file join $original sha3 routed.dcp] \
    [file join $original sha256 routed.dcp] [file join $original blake2s routed.dcp]]]
set fh [open sources.sha256 w]
foreach path $recorded { puts $fh [exec sha256sum $path] }
close $fh
set accepted_synth [file normalize rm_synth.dcp]
if {[lindex [exec sha256sum $accepted_synth] 0] ne "d9f0b2a9d1436a920cb209789f6e1f107b80f273e940ecbfe8745264e411691a"} { error "Changed synthesis checkpoint" }
# Keep the unchanged native core at its previously timing-closed locations.
# Only exact hierarchical-name and primitive-type matches receive constraints.
open_checkpoint $reference_route
set reference_placement [dict create]
foreach cell [get_cells -hier -filter {IS_PRIMITIVE == 1 && NAME =~ u_hash/core/*}] {
    set loc [get_property LOC $cell]
    set bel [get_property BEL $cell]
    if {$loc ne "" && $bel ne ""} {
        dict set reference_placement [get_property NAME $cell] [list [get_property REF_NAME $cell] $loc $bel]
    }
}
close_project
open_checkpoint [file join $original static_locked.dcp]
read_checkpoint -strict -cell u_hash rm_synth.dcp
require_clean_drc floorplan_drc.rpt [get_drc_checks HDPR*]
opt_design
set retained 0
foreach cell [get_cells -hier -filter {IS_PRIMITIVE == 1 && NAME =~ u_hash/core/*}] {
    set name [get_property NAME $cell]
    if {[dict exists $reference_placement $name]} {
        lassign [dict get $reference_placement $name] ref loc bel
        if {[get_property REF_NAME $cell] eq $ref} {
            set_property BEL $bel $cell
            set_property LOC $loc $cell
            incr retained
        }
    }
}
puts "RETAINED_OXIDE_CORE_PLACEMENT $retained"
if {$retained < 5000} { error "Too few unchanged native-core placement matches" }
place_design
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
