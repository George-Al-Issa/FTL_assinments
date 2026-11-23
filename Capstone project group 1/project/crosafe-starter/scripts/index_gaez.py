"""Stream the official GAEZ catalog into a newline-delimited JSON inventory."""
import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from crosafe.cloud_catalog import ROOT, list_objects


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--prefix", default=ROOT, help="Inventory the entire namespace or a single collection")
    options = parser.parse_args()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    token, count = "", 0
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=options.output.parent, delete=False,
        ) as output:
            temporary = Path(output.name)
            while True:
                page = list_objects(options.prefix, token, recursive=True)
                for item in page["objects"]:
                    output.write(json.dumps(item) + "\n")
                    count += 1
                token = page["next"]
                if not token:
                    break
        temporary.replace(options.output)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    print(f"Indexed {count:,} official objects in {options.output}")


if __name__ == "__main__":
    main()
