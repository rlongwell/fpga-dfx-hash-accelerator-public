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
    if {[regexp {PW\s*:\s*([0-9]+)\s+Failing Endpoints} $report unused count] && $count != 0} {
        error "Pulse-width timing failed; see $report_path"
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
proc main {} {
    global argv
    if {[version -short] ne "2024.2"} { error "Vivado 2024.2 is required; found [version -short]" }
    if {[llength $argv] != 1} { error "Usage: dfx.tcl ROOT (optional DFX_RMS=sha3,sha256,blake2s)" }
    set root [file normalize [lindex $argv 0]]
    # Vivado prepends its own older Python to PATH; manifests require Python 3.11+.
    set python /usr/bin/python3
    if {[info exists ::env(DFX_PYTHON)]} { set python $::env(DFX_PYTHON) }
    set static [file join $root build vivado system static_synth.dcp]
    if {![file exists $static]} { error "Run scripts/build_system.sh synth first" }
    puts [exec $python -I [file join $root scripts vivado system_manifest.py] verify $root]
    source [file join $root scripts vivado dfx_sources.tcl]
    set out [file join $root build vivado dfx]
    set initial_name [lindex [dict keys $rm_sources] 0]
    set resume [expr {[info exists ::env(DFX_RESUME)] && $::env(DFX_RESUME) eq "1"}]
    set previous_hashes [dict create]
    if {$resume} {
        foreach path [list [file join $out static_locked.dcp] \
            [file join $out $initial_name routed.dcp] [file join $out sources.sha256]] {
            if {![file exists $path]} { error "Cannot resume without $path" }
        }
        set fh [open [file join $out sources.sha256] r]
        foreach line [split [read $fh] \n] {
            if {[regexp {^([0-9a-f]{64})  (.*)$} $line unused digest path]} {
                dict set previous_hashes $path $digest
            }
        }
        close $fh
        foreach path [concat [list $static [file join $root constraints dfx.xdc]] \
            [glob [file join $root rtl static *.sv]] [dict get $rm_sources $initial_name]] {
            set digest [lindex [exec sha256sum $path] 0]
            if {![dict exists $previous_hashes $path] || [dict get $previous_hashes $path] ne $digest} {
                error "Static/initial RM input changed; full DFX rebuild required: $path"
            }
        }
        foreach path [glob [file join $root rtl static *.sv]] {
            if {[file mtime $path] > [file mtime $static]} { error "Static RTL newer than checkpoint: $path; run synth first" }
        }
        foreach path [glob -nocomplain [file join $out * *.bit] [file join $out * *.bin] \
            [file join $out manifest.json] [file join $out build_info.txt]] { file delete -force $path }
    } else {
        # A failed new build must not leave an old image appearing current.
        file delete -force $out
    }
    foreach generated {dfx_manifest.json dfx_summary.json dfx_summary.md} {
        file delete -force [file join $root results $generated]
    }
    file mkdir $out
    set_param general.maxThreads 2
    set fh [open [file join $out rm_ooc.xdc] w]
    puts $fh {create_clock -name aclk -period 10.000 [get_ports aclk]}
    close $fh
    set fh [open [file join $out sources.sha256] w]
    foreach path [concat [list $static [file join $root constraints dfx.xdc]] \
        [glob [file join $root rtl static *.sv] [file join $root scripts vivado system*.tcl] [file join $root scripts vivado dfx*.tcl] \
            [file join $root scripts vivado system_manifest.py] [file join $root scripts vivado dfx_manifest.py]] \
        [lsort -unique [concat {*}[dict values $rm_sources]]]] {
        puts $fh [exec sha256sum $path]
    }
    close $fh
    # OOC synthesis preserves the exact top-level RM boundary for each algorithm.
    set reuse_routed [dict create]
    dict for {name sources} $rm_sources {
        file mkdir [file join $out $name]
        set unchanged [expr {$resume && [file exists [file join $out $name rm_synth.dcp]]}]
        foreach path $sources {
            if {![dict exists $previous_hashes $path] || [dict get $previous_hashes $path] ne [lindex [exec sha256sum $path] 0]} {
                set unchanged 0
            }
        }
        set checkpoint [file join $out $name routed.dcp]
        set reusable [expr {$unchanged && [file exists $checkpoint]}]
        if {$reusable && $name ne $initial_name} {
            # A synthesis from an interrupted newer run invalidates older routing.
            # Static compatibility is independently checked with pr_verify below.
            foreach prerequisite [list [file join $out $name rm_synth.dcp] [file join $out static_locked.dcp]] {
                if {[file mtime $checkpoint] < [file mtime $prerequisite]} { set reusable 0 }
            }
        }
        dict set reuse_routed $name $reusable
        if {$unchanged} { puts "DFX_REUSE_SYNTH $name"; continue }
        file delete -force [file join $out $name rm_synth.dcp]
        file delete -force $checkpoint
        create_project -in_memory -part xc7z020clg400-1
        read_verilog -sv $sources
        read_xdc [file join $out rm_ooc.xdc]
        set_property USED_IN {synthesis implementation out_of_context} [get_files [file join $out rm_ooc.xdc]]
        synth_design -top hash_rm -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy rebuilt
        write_checkpoint -force [file join $out $name rm_synth.dcp]
        report_utilization -hierarchical -file [file join $out $name synth_utilization.rpt]
        report_timing_summary -file [file join $out $name synth_timing.rpt]
        close_project
    }
    set first 1
    set routed [dict create]
    dict for {name sources} $rm_sources {
        set dir [file join $out $name]
        if {$resume && [dict get $reuse_routed $name]} {
            open_checkpoint [file join $dir routed.dcp]
            report_utilization -hierarchical -file [file join $dir routed_utilization.rpt]
            require_routing [file join $dir route_status.rpt]
            require_clean_drc [file join $dir routed_drc.rpt]
            require_timing [file join $dir routed_timing.rpt]
            dict set routed $name [file join $dir routed.dcp]
            set first 0
            close_project
            puts "DFX_REUSE_ROUTED $name"
            continue
        }
        if {$first} {
            open_checkpoint $static
            set_property HD.RECONFIGURABLE true [get_cells u_hash]
            read_xdc [file join $root constraints dfx.xdc]
        } else {
            open_checkpoint [file join $out static_locked.dcp]
        }
        read_checkpoint -strict -cell u_hash [file join $dir rm_synth.dcp]
        require_clean_drc [file join $dir floorplan_drc.rpt] [get_drc_checks HDPR*]
        opt_design
        place_design
        phys_opt_design
        route_design
        # Preserve the first routed result before any optional timing recovery.
        write_checkpoint -force [file join $dir routed.dcp]
        set worst_setup [get_property SLACK [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]]
        set worst_hold [get_property SLACK [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]]
        if {$worst_setup < 0.0 || $worst_hold < 0.0} {
            file copy -force [file join $dir routed.dcp] [file join $dir routed_before_phys_opt.dcp]
            report_timing_summary -delay_type min_max -file [file join $dir routed_before_phys_opt_timing.rpt]
            phys_opt_design -directive AggressiveExplore
            route_design
            write_checkpoint -force [file join $dir routed.dcp]
        }
        report_utilization -hierarchical -file [file join $dir routed_utilization.rpt]
        require_routing [file join $dir route_status.rpt]
        require_clean_drc [file join $dir routed_drc.rpt]
        require_timing [file join $dir routed_timing.rpt]
        dict set routed $name [file join $dir routed.dcp]
        if {$first} {
            update_design -cell u_hash -black_box
            lock_design -level routing
            write_checkpoint -force [file join $out static_locked.dcp]
            set first 0
        }
        close_project
    }
    set initial_name [lindex [dict keys $routed] 0]
    set initial [dict get $routed $initial_name]
    dict for {name checkpoint} $routed {
        if {$name eq $initial_name} { continue }
        pr_verify -full_check -file [file join $out pr_verify_${initial_name}_${name}.rpt] $initial $checkpoint
    }
    puts [exec sha256sum --check [file join $out sources.sha256]]
    puts [exec $python -I [file join $root scripts vivado system_manifest.py] verify $root]
    # Every configuration has passed routing, timing, DRC, and static compatibility.
    set bootgen [file join [file dirname [info nameofexecutable]] bootgen]
    if {![file executable $bootgen]} {
        set bootgen /opt/amd/xilinx/Vivado/2024.2/bin/bootgen
    }
    if {![file executable $bootgen]} { error "Bootgen 2024.2 is required for PCAP binaries" }
    dict for {name checkpoint} $routed {
        set dir [file join $out $name]
        open_checkpoint $checkpoint
        write_bitstream -force [file join $dir full.bit]
        close_project
        set partial [file join $dir full_pblock_hash_partial.bit]
        if {![file exists $partial]} { error "Vivado did not emit $partial" }
        set bif [file join $dir partial.bif]
        set fh [open $bif w]
        puts $fh "all:\n\{\n  \"$partial\"\n\}"
        close $fh
        set result [exec $bootgen -arch zynq -image $bif -process_bitstream bin -w on 2>@1]
        set fh [open [file join $dir bootgen.log] w]
        puts $fh $result
        close $fh
        set bin ${partial}.bin
        if {![file exists $bin] || [file size $bin] % 4 != 0} { error "Missing or unaligned PCAP binary: $bin" }
        set fh [open $bin rb]
        binary scan [read $fh 128] H* prefix
        close $fh
        if {[string first 665599aa $prefix] < 0} { error "PCAP binary has no correctly byte-swapped sync word: $bin" }
    }
    set fh [open [file join $out artifacts.sha256] w]
    foreach path [lsort [glob [file join $out * *.bit] [file join $out * *.bin]]] {
        puts $fh [exec sha256sum $path]
    }
    close $fh
    set fh [open [file join $out build_info.txt] w]
    puts $fh "Tool: [version -short]\nPart: xc7z020clg400-1\nClock target: 100 MHz\nRMs: [dict keys $rm_sources]\nInitial configuration: $initial_name\nCompleted UTC: [clock format [clock seconds] -gmt 1 -format {%Y-%m-%dT%H:%M:%SZ}]\nHardware tested: no"
    close $fh
    puts [exec $python -I [file join $root scripts vivado dfx_manifest.py] $root $out $initial_name]
    puts "DFX_BUILD_PASS [dict keys $rm_sources]"
}
if {[catch {main} reason options]} {
    puts stderr "DFX_BUILD_FAIL: $reason"
    puts stderr [dict get $options -errorinfo]
    exit 1
}
exit 0
