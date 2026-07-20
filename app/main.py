import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Remove the root 'app' from sys.modules so it resolves to 'backend/app'
for key in list(sys.modules.keys()):
    if key == "app" or key.startswith("app."):
        del sys.modules[key]

# Now import the actual backend app
import app.main as backend_main
app = backend_main.app
