import time
import importlib
import traceback

modules = [
    "app.main",
    "app.services.ai_engine",
    "app.services.agent_tools",
    "app.db.session",
]

for m in modules:
    try:
        t0 = time.time()
        importlib.import_module(m)
        dt = time.time() - t0
        print("IMPORT_OK", m, f"{dt:.3f}s")
    except Exception:
        traceback.print_exc()
        print("IMPORT_FAIL", m)

print("DONE")
