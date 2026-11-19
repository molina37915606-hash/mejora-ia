"""Configuración del disco de trabajo. Solo Zompix_Temporales se usa para archivos intermedios."""
import json
import os
import shutil
import tempfile
from pathlib import Path

APP_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "Zompix"
CONFIG_FILE = APP_DIR / "config.json"
SUBFOLDER = "Zompix_Temporales"


def configured_folder():
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        folder = data.get("work_folder", "")
        return str(folder) if isinstance(folder, str) else ""
    except (OSError, ValueError, TypeError):
        return ""


def checked_root(folder):
    """Exigir una carpeta real y escribible; nunca borrar datos ajenos."""
    parent = Path(folder).expanduser().resolve(strict=True)
    if not parent.is_dir():
        raise ValueError("Elegí una carpeta de tu disco externo.")
    root = parent / SUBFOLDER
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="prueba_", dir=root) as test:
        test.write(b"zompix")
        test.flush()
    if shutil.disk_usage(root).free < 256 * 1024 * 1024:
        raise ValueError("El disco elegido tiene menos de 256 MB libres.")
    return root


def create_session():
    """Si el disco configurado se desconectó, iniciar en local con aviso visible."""
    selected = configured_folder()
    if selected:
        try:
            root = checked_root(selected)
            return Path(tempfile.mkdtemp(prefix="zompix_", dir=root)), ""
        except (OSError, ValueError) as exc:
            warning = "No se pudo usar el disco elegido: " + str(exc) + ". Se está usando el disco local."
    else:
        warning = ""
    root = Path(tempfile.gettempdir()) / SUBFOLDER
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="zompix_", dir=root)), warning


def save_folder(folder):
    root = checked_root(folder)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"work_folder": str(Path(folder).resolve(strict=True))},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, CONFIG_FILE)
    return root


def status(work, warning=""):
    work = Path(work)
    try:
        free = round(shutil.disk_usage(work).free / 1e9, 1)
    except OSError:
        free = None
    return {"active": str(work.parent), "chosen": configured_folder(),
            "free_gb": free, "warning": warning}
