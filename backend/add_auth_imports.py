import os
import re

ROUTES_DIR = "app/routes"
DEPS_IMPORT = "\nfrom app.auth.deps import verify_company_access, get_current_user\nfrom app.models.user import User\n"

for filename in os.listdir(ROUTES_DIR):
    if not filename.endswith(".py") or filename in ("__init__.py", "auth.py", "health.py", "demo.py"):
        continue
    
    filepath = os.path.join(ROUTES_DIR, filename)
    with open(filepath, "r") as f:
        content = f.read()

    # Add the imports if not present
    if "verify_company_access" not in content:
        # Find the first 'import' or 'from'
        match = re.search(r"^(import |from )", content, re.MULTILINE)
        if match:
            idx = match.start()
            content = content[:idx] + DEPS_IMPORT + content[idx:]
        else:
            content = DEPS_IMPORT + content
            
        with open(filepath, "w") as f:
            f.write(content)
