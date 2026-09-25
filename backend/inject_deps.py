import os
import re

ROUTES_DIR = "app/routes"

for filename in os.listdir(ROUTES_DIR):
    if not filename.endswith(".py") or filename in ("__init__.py", "auth.py", "health.py", "demo.py", "live.py"):
        continue

    filepath = os.path.join(ROUTES_DIR, filename)
    with open(filepath, "r") as f:
        content = f.read()

    # Step 1: Add import
    if "verify_company_access" not in content:
        import_stmt = "from app.auth.deps import verify_company_access, get_current_user\nfrom app.models.user import User\n"
        if "from app.auth.deps" not in content:
            content = import_stmt + content
        
    # Step 2: Add to signature
    content, count = re.subn(
        r"(def\s+[a-zA-Z0-9_]+\s*\([^)]*company_id\s*:\s*int[^)]*)(?=\))",
        r"\1, current_user: User = Depends(verify_company_access)",
        content,
        flags=re.MULTILINE
    )
    
    with open(filepath, "w") as f:
        f.write(content)

    print(f"Updated {filename}: {count} replacements")
