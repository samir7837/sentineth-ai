import re
from pathlib import Path, PurePosixPath

from app.providers.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[3] / "storage" / "documents"
        self.base_dir = Path(base_dir).resolve()

    def _sanitize_filename(self, filename: str) -> str:
        if not filename or not filename.strip():
            return "uploaded_file.bin"

        cleaned = filename.replace("\\", "/")
        safe_name = PurePosixPath(cleaned).name
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", safe_name)
        safe_name = safe_name.strip().strip(".")

        if not safe_name or safe_name in {".", ".."}:
            return "uploaded_file.bin"

        return safe_name

    async def save(
        self,
        organization_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        org_dir = self.base_dir / str(organization_id)
        org_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = self._sanitize_filename(filename)
        target_path = (org_dir / safe_filename).resolve(strict=False)
        org_root = org_dir.resolve(strict=False)

        if target_path != org_root and org_root not in target_path.parents:
            raise ValueError("Filename resolves outside the organization storage directory.")

        with open(target_path, "wb") as handle:
            handle.write(content)

        return str(target_path)

    async def delete(
        self,
        path: str,
    ) -> None:
        if not path:
            return

        file_path = Path(path)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()

    async def exists(
        self,
        path: str,
    ) -> bool:
        if not path:
            return False

        return Path(path).exists()
