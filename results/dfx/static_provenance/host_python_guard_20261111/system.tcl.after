proc main {} {
    global argv
    if {[version -short] ne "2024.2"} { error "Vivado 2024.2 is required; found [version -short]" }
    if {[llength $argv] != 2} { error "Usage: system.tcl ROOT bd|ip|synth" }
    lassign $argv root stage
    set root [file normalize $root]
    # Ignore Vivado's bundled Python/PYTHONHOME for host-side manifests.
    set python /usr/bin/python3
    if {[info exists ::env(SYSTEM_PYTHON)]} { set python $::env(SYSTEM_PYTHON) }
    set out [file join $root build vivado system]
    set project [file join $out project system.xpr]
    file mkdir $out
    set_param general.maxThreads 2
    if {$stage eq "bd" || ![file exists $project]} {
        if {[file exists [file dirname $project]]} { file delete -force [file dirname $project] }
        foreach old {static_synth.dcp system.xsa} {
            file delete -force [file join $out $old]
        }
        create_project -force system [file dirname $project] -part xc7z020clg400-1
        set_property target_language Verilog [current_project]
        source [file join $root scripts vivado system_bd.tcl]
        set bd [get_files */ps_dma.bd]
        generate_target all $bd
        set wrapper [make_wrapper -files $bd -top]
        add_files -norecurse $wrapper
        set_property top ps_dma_wrapper [current_fileset]
        create_ip_run $bd
        set fh [open [file join $out address_map.txt] w]
        foreach seg [get_bd_addr_segs -hierarchical] {
            puts $fh "$seg OFFSET=[get_property OFFSET $seg] RANGE=[get_property RANGE $seg]"
        }
        close $fh
        write_bd_tcl -force [file join $out ps_dma_export.tcl]
    } else {
        open_project $project
    }
    foreach run [get_runs -filter {IS_SYNTHESIS == 1}] {
        set_property STEPS.SYNTH_DESIGN.TCL.PRE [file join $root scripts vivado system_threads.tcl] $run
    }
    if {$stage eq "ip"} {
        set runs [get_runs -filter {IS_SYNTHESIS == 1 && NAME != synth_1}]
        set pending {}
        foreach run $runs {
            if {[get_property STATUS $run] ne "synth_design Complete!"} { lappend pending $run }
        }
        if {[llength $pending]} {
            launch_runs $pending -jobs 2
            foreach run $pending { wait_on_run $run }
        }
        foreach run $runs {
            if {[get_property STATUS $run] ne "synth_design Complete!"} {
                error "IP synthesis failed: $run: [get_property STATUS $run]"
            }
        }
    } elseif {$stage eq "synth"} {
        puts [exec $python -I [file join $root scripts vivado system_manifest.py] begin $root]
        foreach source {hash_shell.sv system_top.sv} {
            set path [file join $root rtl static $source]
            if {![file exists $path]} { error "Required RTL is missing: $path" }
            add_files -norecurse $path
        }
        # Never compile an algorithm into static synthesis. Preserve this boundary.
        set stub [file join $out hash_rm_stub.sv]
        set fh [open $stub w]
        puts $fh {(* black_box *) module hash_rm(
    input wire aclk, aresetn, start,
    input wire [63:0] message_length,
    input wire [63:0] s_axis_tdata,
    input wire [7:0] s_axis_tkeep,
    input wire s_axis_tvalid, s_axis_tlast,
    output wire s_axis_tready,
    output wire [255:0] digest,
    output wire digest_valid,
    input wire digest_ready,
    output wire busy,
    output wire [31:0] algorithm_id,
    output wire error
); endmodule}
        close $fh
        add_files -norecurse $stub
        set_property top system_top [current_fileset]
        set_property AUTO_INCREMENTAL_CHECKPOINT false [get_runs synth_1]
        set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY none [get_runs synth_1]
        update_compile_order -fileset sources_1
        reset_run synth_1
        launch_runs synth_1 -jobs 2
        wait_on_run synth_1
        if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} { error "Static synthesis failed" }
        open_run synth_1
        write_checkpoint -force [file join $out static_synth.dcp]
        report_utilization -hierarchical -file [file join $out static_utilization.rpt]
        report_timing_summary -file [file join $out static_synth_timing.rpt]
        write_hw_platform -fixed -force -file [file join $out system.xsa]
        puts [exec $python -I [file join $root scripts vivado system_manifest.py] finish $root]
    } elseif {$stage ne "bd"} {
        error "Unknown system stage: $stage"
    }
    close_project
    puts "SYSTEM_STAGE_PASS $stage"
}
if {[catch {main} reason options]} {
    puts stderr "SYSTEM_STAGE_FAIL: $reason"
    puts stderr [dict get $options -errorinfo]
    exit 1
}
exit 0
