# All RMs use the same hash_rm boundary; never read two wrappers together.
set names {sha3 sha256 blake2s}
if {[info exists ::env(DFX_RMS)] && $::env(DFX_RMS) ne ""} {
    set names [split $::env(DFX_RMS) ,]
}
set rm_sources [dict create]
foreach name $names {
    if {$name ni {sha3 sha256 blake2s}} { error "Unknown RM: $name" }
    set sources [concat [lsort [glob -nocomplain [file join $root rtl common *.sv]]] \
        [lsort [glob -nocomplain [file join $root rtl $name *.sv]]] \
        [list [file join $root rtl rm ${name}.sv]]]
    if {[llength $sources] < 3} { error "Incomplete source set for $name" }
    foreach path $sources { if {![file exists $path]} { error "Missing RM source: $path" } }
    dict set rm_sources $name $sources
}
