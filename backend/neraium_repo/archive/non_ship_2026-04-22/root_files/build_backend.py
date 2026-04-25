from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import tarfile
import zipfile

NAME = "neraium_core"
DIST_NAME = "neraium_core"
VERSION = "0.1.0"
WHEEL_TAG = "py3-none-any"


def _dist_info_dir() -> str:
    return f"{DIST_NAME}-{VERSION}.dist-info"


def _wheel_name() -> str:
    return f"{DIST_NAME}-{VERSION}-{WHEEL_TAG}.whl"


def _iter_files(root: Path):
    include_dirs = [root / "neraium_core", root / "httpx"]
    include_files = [root / "run_live_stock_market.py"]
    for d in include_dirs:
        if d.exists():
            for path in d.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    yield path, path.relative_to(root).as_posix()
    for f in include_files:
        if f.exists():
            yield f, f.name


def _metadata() -> str:
    requires_dist = [
        "fastapi>=0.110",
        "numpy>=1.24",
        "pandas>=2.0",
        "pydantic>=2",
        "python-multipart>=0.0.9",
        "starlette>=0.36",
        "uvicorn>=0.29",
    ]
    requires_dist_lines = [f"Requires-Dist: {dep}" for dep in requires_dist]
    return "\n".join(
        [
            "Metadata-Version: 2.1",
            f"Name: {NAME}",
            f"Version: {VERSION}",
            "Summary: Read-only structural instability instrumentation engine and API",
            "Requires-Python: >=3.10",
            *requires_dist_lines,
            "",
        ]
    )


def _wheel_file() -> str:
    return "\n".join([
        "Wheel-Version: 1.0",
        "Generator: custom-backend",
        "Root-Is-Purelib: true",
        f"Tag: {WHEEL_TAG}",
        "",
    ])


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    root = Path(__file__).resolve().parent
    wheel_directory = Path(wheel_directory)
    wheel_directory.mkdir(parents=True, exist_ok=True)
    wheel_path = wheel_directory / _wheel_name()
    dist_info = _dist_info_dir()

    records: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in _iter_files(root):
            data = src.read_bytes()
            zf.writestr(arc, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
            records.append((arc, f"sha256={digest}", str(len(data))))

        metadata_path = f"{dist_info}/METADATA"
        wheel_path_in_zip = f"{dist_info}/WHEEL"
        metadata_data = _metadata().encode()
        wheel_data = _wheel_file().encode()
        zf.writestr(metadata_path, metadata_data)
        zf.writestr(wheel_path_in_zip, wheel_data)
        for arc, data in ((metadata_path, metadata_data), (wheel_path_in_zip, wheel_data)):
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
            records.append((arc, f"sha256={digest}", str(len(data))))

        record_path = f"{dist_info}/RECORD"
        output = []
        for row in records:
            output.append(row)
        output.append((record_path, "", ""))
        record_data = "\n".join(",".join(r) for r in output).encode()
        zf.writestr(record_path, record_data)

    return wheel_path.name


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    metadata_directory = Path(metadata_directory)
    dist_info = metadata_directory / _dist_info_dir()
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_file(), encoding="utf-8")
    (dist_info / "RECORD").write_text("", encoding="utf-8")
    return dist_info.name


def build_sdist(sdist_directory, config_settings=None):
    root = Path(__file__).resolve().parent
    sdist_directory = Path(sdist_directory)
    sdist_directory.mkdir(parents=True, exist_ok=True)
    name = f"{DIST_NAME}-{VERSION}.tar.gz"
    out = sdist_directory / name
    with tarfile.open(out, "w:gz") as tar:
        for path in ["pyproject.toml", "build_backend.py", "setup.py", "README.md", "pytest.ini"]:
            p = root / path
            if p.exists():
                tar.add(p, arcname=f"{DIST_NAME}-{VERSION}/{path}")
        for src, arc in _iter_files(root):
            tar.add(src, arcname=f"{DIST_NAME}-{VERSION}/{arc}")
    return name


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []
