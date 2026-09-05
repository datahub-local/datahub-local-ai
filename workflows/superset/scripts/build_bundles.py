#!/usr/bin/env python3
"""Build Superset export bundles from projects/*/dashboard_export.

Writes release/files/<project>.zip for every project that has a dashboard_export
directory. The release chart packages these zips as ConfigMaps consumed by the
Superset dashboard sidecar (datahub-local-core).

Zips are reproducible (fixed timestamps, sorted entries) so rebuilding without
changes leaves the working tree clean.

Also refuses to build a dataset that reads bronze. Trino grants `superset` full
access to every medallion catalog, so nothing else stops it, and bronze holds
unexpanded JSON - a chart on `raw_invoices` would count invoices where it meant
line items. See CLAUDE.md, "Bronze is not a consumer layer".
"""
import pathlib
import re
import sys
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
FIXED_DATE = (2020, 1, 1, 0, 0, 0)

# `bronze.` in a virtual dataset's SQL, or a `catalog: bronze` on a physical
# one. Matched on the raw YAML so it holds whatever shape the export takes.
BRONZE = re.compile(r"(?i)\bbronze\s*\.|^\s*catalog:\s*[\"']?bronze\b", re.MULTILINE)


def bronze_readers(export_dir):
    """Dataset files that reference the bronze catalog."""
    return [
        path
        for path in sorted(export_dir.rglob("*.yaml"))
        if "datasets" in path.parts and BRONZE.search(path.read_text())
    ]


def main():
    for project in sorted((BASE / "projects").iterdir()):
        export_dir = project / "dashboard_export"
        if not export_dir.is_dir():
            continue
        offenders = bronze_readers(export_dir)
        if offenders:
            print(
                f"{project.name}: dataset(s) read the bronze catalog, which is the landing "
                f"zone and not a consumer layer - add a silver model instead:",
                file=sys.stderr,
            )
            for path in offenders:
                print(f"  {path.relative_to(BASE)}", file=sys.stderr)
            return 1

        target = BASE / "release" / "files" / f"{project.name}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(export_dir.rglob("*.yaml")):
                info = zipfile.ZipInfo(str(path.relative_to(project)), date_time=FIXED_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(info, path.read_bytes())
                count += 1
        print(f"{target.relative_to(BASE)}: {count} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
