"""Download and extract LibriSpeech dev-clean into DATA_DIR/librispeech.

Resume-safe: a partial download is kept as `<name>.part` and continued with an HTTP
Range request. The archive is verified against the OpenSLR md5 before extraction.
Re-running after success is a no-op.
"""

import hashlib
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

from common import librispeech_dir

SUBSET = "dev-clean"
ARCHIVE = f"{SUBSET}.tar.gz"
# From https://www.openslr.org/resources/12/md5sum.txt
MD5 = "42e2234ba48799c1f50f24a7926300a1"
MIRRORS = (
    "https://www.openslr.org/resources/12",
    "https://us.openslr.org/resources/12",
    "https://openslr.elda.org/resources/12",
)
CHUNK = 1 << 20

LICENCE_NOTE = """# LibriSpeech licence note

- Dataset: LibriSpeech ASR corpus (OpenSLR SLR12), subset `{subset}`
- Source: https://www.openslr.org/12
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0),
  https://creativecommons.org/licenses/by/4.0/
- Authors: Vassil Panayotov, Guoguo Chen, Daniel Povey, Sanjeev Khudanpur.
  "LibriSpeech: an ASR corpus based on public domain audio books", ICASSP 2015.
- Audio derives from LibriVox public-domain audiobook recordings.

Use in Sonari: evaluation only (gates G0/G1). Nothing from this directory is committed
to the repo. Any derived clip (for example `derived/g0/*.wav`) keeps this attribution.
"""


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, part: Path) -> None:
    """Download url into part, resuming from part's current size."""
    offset = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as err:
        if err.code == 416:  # Range not satisfiable: the file is already complete.
            return
        raise
    with response:
        if offset and response.status != 206:
            print("server ignored Range; restarting download", flush=True)
            offset = 0
        total = offset + int(response.headers.get("Content-Length", 0))
        mode = "ab" if offset else "wb"
        done = offset
        with part.open(mode) as f:
            while block := response.read(CHUNK):
                f.write(block)
                done += len(block)
                if done % (32 * CHUNK) < CHUNK:
                    print(f"  {done >> 20} / {total >> 20} MiB", flush=True)


def fetch_archive(target: Path) -> None:
    archive = target / ARCHIVE
    if archive.exists():
        return
    part = target / f"{ARCHIVE}.part"
    for mirror in MIRRORS:
        url = f"{mirror}/{ARCHIVE}"
        print(f"downloading {url}", flush=True)
        try:
            download(url, part)
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            print(f"  failed ({err}); partial file kept for resume", flush=True)
    else:
        sys.exit("all mirrors failed; re-run to resume")
    actual = md5sum(part)
    if actual != MD5:
        part.unlink()
        sys.exit(f"md5 mismatch: expected {MD5}, got {actual}; partial file removed")
    part.rename(archive)
    print(f"md5 ok ({MD5})")


def extract(target: Path) -> None:
    """Extract, stripping the archive's top-level `LibriSpeech/` directory."""
    if (target / SUBSET).is_dir() and (target / ".extracted").exists():
        return
    print(f"extracting {ARCHIVE}", flush=True)
    staging = target / ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    with tarfile.open(target / ARCHIVE) as tar:
        tar.extractall(staging, filter="data")
    for item in (staging / "LibriSpeech").iterdir():
        dest = target / item.name
        if dest.is_dir():
            shutil.rmtree(dest)
        elif dest.exists():
            dest.unlink()
        item.rename(dest)
    shutil.rmtree(staging)
    (target / ".extracted").touch()


def main() -> None:
    target = librispeech_dir()
    target.mkdir(parents=True, exist_ok=True)
    fetch_archive(target)
    extract(target)
    (target / "LICENCE-NOTE.md").write_text(LICENCE_NOTE.format(subset=SUBSET), encoding="utf-8")
    n_flac = sum(1 for _ in (target / SUBSET).rglob("*.flac"))
    print(f"LibriSpeech {SUBSET}: {n_flac} utterances in {target / SUBSET}")
    print("Licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).")
    print(f"Attribution note written to {target / 'LICENCE-NOTE.md'}")


if __name__ == "__main__":
    main()
