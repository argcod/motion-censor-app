"""Project-root path helpers — never depend on the process cwd."""
from __future__ import annotations

from pathlib import Path

# utils/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def project_path(*parts: str) -> Path:
    """Absolute path under the project root."""
    return PROJECT_ROOT.joinpath(*parts)


def asset_path(*parts: str) -> Path:
    """Absolute path under assets/."""
    return project_path("assets", *parts)


def snapshot_path(*parts: str) -> Path:
    """Absolute path under snapshots/."""
    return project_path("snapshots", *parts)


def log_path(*parts: str) -> Path:
    """Absolute path under logs/."""
    return project_path("logs", *parts)


def ensure_dir(path: Path) -> Path:
    # Make sure runtime folders exist before writing files into them
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_runtime_dirs() -> None:
    # Create the folders the app always needs on startup
    ensure_dir(project_path("snapshots"))
    ensure_dir(project_path("logs"))
    ensure_dir(project_path("assets"))


def path_str(path: Path | str) -> str:
    return str(path)


def resolve_asset_file(stored: str | None, fallback: str = "isometric_base.jpg") -> str:
    # Phase 6 — DB may store assets/… relative paths; always return a real file path
    fallback_path = asset_path(fallback)
    if not stored:
        return path_str(fallback_path)
    raw = Path(str(stored))
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend([project_path(str(stored)), PROJECT_ROOT / stored, asset_path(raw.name)])
    for candidate in candidates:
        try:
            if candidate.is_file():
                return path_str(candidate)
        except OSError:
            continue
    return path_str(fallback_path)


def resolve_snapshot_file(stored: str | None) -> Path | None:
    # DB stores project-relative paths; turn them into a real file if it still exists
    if not stored:
        return None
    raw = Path(str(stored))
    candidates = [raw] if raw.is_absolute() else [project_path(str(stored)), PROJECT_ROOT / stored]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None
