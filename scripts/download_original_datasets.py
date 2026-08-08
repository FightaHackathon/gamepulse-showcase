from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


DATASETS = (
    {
        "slug": "fronkongames/steam-games-dataset",
        "folder": "steam-games-dataset",
        "source_url": "https://www.kaggle.com/datasets/fronkongames/steam-games-dataset",
    },
    {
        "slug": "akashunikaggle/steam-game-reviews-of-743-games",
        "folder": "steam-game-reviews-of-743-games",
        "source_url": "https://www.kaggle.com/datasets/akashunikaggle/steam-game-reviews-of-743-games",
    },
    {
        "slug": "muhammadaqeelkabir/steam-games-dataset-steamspy-api",
        "folder": "steam-games-dataset-steamspy-api",
        "source_url": "https://www.kaggle.com/datasets/muhammadaqeelkabir/steam-games-dataset-steamspy-api",
    },
)

CHUNK_SIZE = 8 * 1024 * 1024
REPORT_INTERVAL_SECONDS = 10
MAX_DOWNLOAD_ATTEMPTS = 10


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP validation failed at {bad_member}")


def download_once(slug: str, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    downloaded = partial.stat().st_size if partial.exists() else 0
    url = f"https://www.kaggle.com/api/v1/datasets/download/{slug}"
    headers = {"User-Agent": "GamePulse-prototype-dataset-downloader/1.0"}
    if downloaded:
        headers["Range"] = f"bytes={downloaded}-"

    request = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(request, timeout=120)
    status = getattr(response, "status", response.getcode())
    append = downloaded > 0 and status == 206
    if downloaded and not append:
        downloaded = 0

    content_length = response.headers.get("Content-Length")
    expected = downloaded + int(content_length) if content_length else None
    mode = "ab" if append else "wb"
    last_report = time.monotonic()

    print(
        f"[{utc_now()}] Downloading {slug} "
        f"from byte {downloaded:,}"
        + (f" of {expected:,}" if expected else ""),
        flush=True,
    )

    with partial.open(mode) as file:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            file.write(chunk)
            file.flush()
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_report >= REPORT_INTERVAL_SECONDS:
                percent = (
                    f" ({downloaded / expected:.1%})" if expected else ""
                )
                print(
                    f"[{utc_now()}] {slug}: {downloaded:,} bytes{percent}",
                    flush=True,
                )
                last_report = now
        os.fsync(file.fileno())

    if expected is not None and downloaded != expected:
        raise RuntimeError(
            f"Incomplete download for {slug}: got {downloaded}, expected {expected}"
        )

    partial.replace(destination)
    print(f"[{utc_now()}] Validating {destination}", flush=True)
    validate_zip(destination)


def download(slug: str, destination: Path) -> None:
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            download_once(slug, destination)
            return
        except Exception as error:
            if attempt == MAX_DOWNLOAD_ATTEMPTS:
                raise
            print(
                f"[{utc_now()}] Download attempt {attempt} failed for {slug}: "
                f"{error}. Retrying with saved partial data.",
                flush=True,
            )
            time.sleep(min(attempt * 3, 30))


def main() -> int:
    workspace = Path(__file__).resolve().parents[1]
    log_path_value = os.environ.get(
        "GAMEPULSE_DOWNLOAD_LOG",
        str(workspace / ".tmp" / "dataset-download" / "download.log"),
    )
    if log_path_value:
        log_path = Path(log_path_value)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file

    snapshot_date = os.environ.get("GAMEPULSE_DATASET_DATE", "2026-07-30")
    raw_root = workspace / "data" / "raw" / snapshot_date
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    for dataset in DATASETS:
        folder = raw_root / str(dataset["folder"])
        folder.mkdir(parents=True, exist_ok=True)
        archive_path = folder / "dataset.zip"

        try:
            if archive_path.exists():
                try:
                    validate_zip(archive_path)
                    print(
                        f"[{utc_now()}] Reusing valid archive {archive_path}",
                        flush=True,
                    )
                except (OSError, zipfile.BadZipFile, RuntimeError):
                    partial_path = archive_path.with_suffix(
                        archive_path.suffix + ".part"
                    )
                    if not partial_path.exists():
                        archive_path.replace(partial_path)
                    download(str(dataset["slug"]), archive_path)
            else:
                download(str(dataset["slug"]), archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                members = [
                    {"name": info.filename, "uncompressed_bytes": info.file_size}
                    for info in archive.infolist()
                    if not info.is_dir()
                ]

            manifest.append(
                {
                    **dataset,
                    "downloaded_at": utc_now(),
                    "archive": str(archive_path.relative_to(workspace)),
                    "archive_bytes": archive_path.stat().st_size,
                    "sha256": sha256(archive_path),
                    "files": members,
                    "status": "complete",
                }
            )
            print(f"[{utc_now()}] Completed {dataset['slug']}", flush=True)
        except Exception as error:
            manifest.append(
                {
                    **dataset,
                    "downloaded_at": utc_now(),
                    "status": "failed",
                    "error": str(error),
                }
            )
            print(
                f"[{utc_now()}] FAILED {dataset['slug']}: {error}",
                file=sys.stderr,
                flush=True,
            )

    manifest_path = raw_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    failures = [item for item in manifest if item["status"] != "complete"]
    print(f"[{utc_now()}] Wrote {manifest_path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
