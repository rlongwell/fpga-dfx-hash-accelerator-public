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
