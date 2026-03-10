"""
Shared in-memory state for Computer Use tasks.

Imported by BOTH main.py (FastAPI endpoints) and app.py (Chainlit agent).
This avoids the circular import deadlock:
  main.py → chainlit → app.py → import main → deadlock

Both files do: from cu_state import _cu_tasks, _cu_results, _cu_agents, _cu_pending

Because Python module imports are cached (sys.modules), both files get
the SAME dict objects — mutations in main.py are visible in app.py and vice versa.
"""
from collections import defaultdict

_cu_tasks: dict = {}
_cu_results: dict = {}
_cu_agents: dict = {}
_cu_pending: defaultdict = defaultdict(list)
