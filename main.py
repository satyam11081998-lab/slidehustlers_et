import sys
from pathlib import Path
import importlib.util

backend_dir = Path(__file__).resolve().parent / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Load backend/app/main.py directly
spec = importlib.util.spec_from_file_location("backend_app_main", backend_dir / "app" / "main.py")
module = importlib.util.module_from_spec(spec)
sys.modules["backend_app_main"] = module
spec.loader.exec_module(module)

app = module.app
