import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The parsers and update_live import each other by bare module name.
for d in ("Scrapings", "Pipeline"):
    sys.path.insert(0, str(ROOT / d))
