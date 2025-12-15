# wsgi.py
# Resilient WSGI entrypoint for Gunicorn / Render.
#
# Tries several common module/attribute combinations and:
# - If an attribute 'app' is found, uses it.
# - If a 'create_app' factory is found, calls it (no args).
# If nothing is found it raises a clear RuntimeError so logs show what to fix.

import importlib
import traceback

candidates = [
    ("app", "app"),
    ("app", "create_app"),
    ("application", "app"),
    ("application", "create_app"),
    ("run", "app"),
    ("run", "create_app"),
    ("wsgi", "app"),
    ("main", "app"),
    ("src.app", "app"),
    ("src.app", "create_app"),
]

app = None
errors = []

for module_name, attr in candidates:
    try:
        mod = importlib.import_module(module_name)
        if hasattr(mod, attr):
            obj = getattr(mod, attr)
            # If it's a factory named create_app, call it (no args)
            if attr == "create_app" and callable(obj):
                try:
                    app = obj()
                    break
                except Exception as e:
                    errors.append(f"create_app() in {module_name} raised: {e}\n{traceback.format_exc()}")
                    continue
            else:
                app = obj
                break
    except Exception as e:
        # Save import errors for debugging later
        errors.append(f"import {module_name} failed: {e}\n{traceback.format_exc()}")

if app is None:
    msg = [
        "Could not locate a Flask WSGI 'app' instance or a 'create_app' factory in any of the checked modules.",
        "Checked candidates (module, attribute):",
        *[f"  - {m}.{a}" for m, a in candidates],
        "",
        "Import errors and tracebacks (if any):",
        *errors,
        "",
        "Please ensure your Flask app exposes one of the following examples:",
        "  - app.py: app = Flask(__name__)",
        "  - app.py: def create_app(): return Flask(...) and you have a wsgi.py that calls create_app()",
    ]
    raise RuntimeError("\n".join(msg))