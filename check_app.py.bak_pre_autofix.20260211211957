# check_app.py
import traceback
import sys

try:
    # Import your app; this will run top-level code in app.py
    import app
    # Pull the Flask app object named `app`
    flask_app = getattr(app, 'app', None)
    if flask_app is None:
        print("Imported app.py but there is no `app` Flask object exported.")
        sys.exit(1)

    rules = sorted([f"{r.endpoint} -> {r.rule}" for r in flask_app.url_map.iter_rules()])
    print("OK: app imported successfully. Routes:")
    print("\n".join(rules))
except Exception:
    print("ERROR: Exception occurred while importing app.py — full traceback below:\n")
    traceback.print_exc()
    sys.exit(1)
