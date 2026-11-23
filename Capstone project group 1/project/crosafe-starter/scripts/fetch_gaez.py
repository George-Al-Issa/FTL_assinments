"""Download CroSafe's selected FAO GAEZ v5 pilot assets from Google Cloud."""
import argparse
from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

ROOT = ("https://storage.googleapis.com/fao-gismgr-gaez-v5-data/"
        "DATA/GAEZ-V5/MAPSET/RES05-SIX/")
STEM = "GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.WHE"


def download(url: str, destination: Path) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            with urlopen(url, timeout=30) as response:
                copyfileobj(response, output)
        temporary.chmod(0o644)
        temporary.replace(destination)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/gaez"))
    directory = parser.parse_args().directory
    directory.mkdir(parents=True, exist_ok=True)
    for regime in ("LRLM", "LILM"):
        for suffix in ("tif", "json"):
            name = f"{STEM}.{regime}.{suffix}"
            download(ROOT + name, directory / name)
            print(f"Downloaded {name}")


if __name__ == "__main__":
    main()
