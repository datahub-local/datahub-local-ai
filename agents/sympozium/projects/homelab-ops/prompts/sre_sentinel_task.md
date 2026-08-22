Do an on-call sweep now.

Query the firing alerts, diff them against what you saw last run, and root-cause
anything new or changed. Then check whether any PersistentVolumeClaim is filling
up, whether or not an alert has fired for it.

Then emit the Status / New / Still firing / Filling up report.

Then deliver it as your Delivery section instructs.

