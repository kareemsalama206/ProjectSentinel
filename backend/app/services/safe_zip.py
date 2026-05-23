from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import Path

from app.core.config import get_settings


class ArchiveValidationError(ValueError):
    pass


def validate_upload_name(file_name: str) -> None:
    if not file_name.lower().endswith(".zip"):
        raise ArchiveValidationError("Unsupported archive type.")


def safe_extract_zip(content: bytes, destination: Path) -> None:
    settings = get_settings()
    if len(content) > settings.max_upload_size_bytes:
        raise ArchiveValidationError("Project archive is too large.")
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ArchiveValidationError("Unsupported archive type.")

    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    total_size = 0
    file_count = 0

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for member in archive.infolist():
                normalized = normalize_zip_path(member.filename)
                if not normalized:
                    continue
                if member.flag_bits & 0x1:
                    raise ArchiveValidationError("Encrypted ZIP archives are not supported.")
                if member.is_dir():
                    continue
                file_count += 1
                total_size += member.file_size
                if file_count > settings.max_extracted_files or total_size > settings.max_extracted_size_bytes:
                    raise ArchiveValidationError("Project archive is too large.")

                target = (destination / normalized).resolve()
                if not is_relative_to(target, destination_root):
                    raise ArchiveValidationError("ZIP archive contains unsafe paths.")

                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except zipfile.BadZipFile as exc:
        raise ArchiveValidationError("Unsupported archive type.") from exc


def normalize_zip_path(raw_name: str) -> str | None:
    name = raw_name.replace("\\", "/")
    if not name or name.endswith("/"):
        return None
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ArchiveValidationError("ZIP archive contains unsafe paths.")
    parts = [part for part in name.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ArchiveValidationError("ZIP archive contains unsafe paths.")
    return "/".join(parts)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
