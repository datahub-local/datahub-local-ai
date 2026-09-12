Do an on-call sweep now.

Call facts_alerts_snapshot, then facts_volume_fill. Investigate anything the
class column marks as new or REAL-chronic, within your six-call budget. When an
alert identifies a pod, inspect its status before retrieving the affected
container's logs: identify `CrashLoopBackOff`, `OOMKilled`, or confirm it is
simply running from the returned data. When a workload is involved, check
argocd_get_application and, if it shows a recent sync or an out-of-sync resource,
argocd_get_application_events for what changed.

Then write the Status / New / Still firing / Resolved / Filling up report and
deliver it as your Delivery section instructs.
