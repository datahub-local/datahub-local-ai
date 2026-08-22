Run the daily database check.

Start with Postgres health and WAL archiving, then the top queries, then Valkey
memory pressure, then the free space and growth rate on every database volume.

Compare sizes and query findings against what you recorded last run.

Then emit the Status / Postgres / Valkey / Capacity report.

Then deliver it as your Delivery section instructs.

