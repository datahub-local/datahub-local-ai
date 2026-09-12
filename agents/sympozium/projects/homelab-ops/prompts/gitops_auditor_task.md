Check drift now.

Call facts_argocd_drift. For anything not Synced and Healthy, use
argocd_get_application and argocd_get_application_events, then the GitHub read
tools to find the source commit that names the drifted resource, within your
six-call budget. Never ask for a resource tree.

Then write the Status / Drift / Escalating report and deliver it as your Delivery
section instructs.
