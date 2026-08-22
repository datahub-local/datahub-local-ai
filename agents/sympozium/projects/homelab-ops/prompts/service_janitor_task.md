Run the weekly continuity sweep.

First, and most importantly: for each of Velero, CloudNativePG, Longhorn and
Kopia, find when a backup last succeeded and whether that is acceptable for a
daily schedule.

Then certificates and tokens expiring within 21 days. Then completed and failed
Jobs older than 7 days, Pods in Succeeded or Failed phase, and
PersistentVolumeClaims that no Pod mounts.

Then emit the Recoverable / Expiring / Accumulated / Suggested cleanup report.

Then deliver it as your Delivery section instructs.

