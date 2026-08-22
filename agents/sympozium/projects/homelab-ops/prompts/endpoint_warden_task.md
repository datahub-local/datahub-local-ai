Run the daily fleet check.

For every node: pressure-stall rates, disk fill, SMART health, EDAC error
counts, temperature, IO saturation, uptime, kernel and OS version. Then check
the UPS. Then look for system pods in kube-system and monitoring that keep
restarting, grouped by node.

Compare everything against what you recorded last run, and report the trend
rather than the snapshot wherever you can.

Then emit the Fleet / Findings / Power report.

Then deliver it as your Delivery section instructs.

