# Interrupted first route

The first implementation process ended with SIGTERM while routing, before it produced a routed checkpoint or final timing report. No Vivado design error was reported. `interrupted_route.log` preserves that incomplete attempt; it is not evidence of a timing failure.

Implementation was restarted from the completed synthesis checkpoint after checking every recorded source SHA-256. `scripts/vivado/engine_resume.tcl` uses the same opt/place/phys_opt/route/report sequence as the original measurement flow. The final reports in this directory, when present, are from that resumed run.
