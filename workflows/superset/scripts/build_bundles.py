#!/usr/bin/env python3
"""Build Superset export bundles from projects/*/dashboard_export.

Writes release/files/<project>.zip for every project that has a dashboard_export
directory. The release chart packages these zips as ConfigMaps consumed by the
Superset dashboard sidecar (datahub-local-core).

Zips are reproducible (fixed timestamps, sorted entries) so rebuilding without
changes leaves the working tree clean.
"""
import pathlib
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent
FIXED_DATE = (2020, 1, 1, 0, 0, 0)


def main():
    for project in sorted((BASE / "projects").iterdir()):
        export_dir = project / "dashboard_export"
        if not export_dir.is_dir():
            continue
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


if __name__ == "__main__":
    main()
