import ast
import os

ROUTES_DIR = "app/routes"

class RouteAuthTransformer(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        # check if it has a decorator
        has_route_decorator = any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("get", "post", "put", "delete")
            for d in node.decorator_list
        )
        if not has_route_decorator:
            return node
            
        # Add current_user: User = Depends(get_current_user)
        # to the arguments
        
        # Check if already present
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.arg == "current_user":
                return node
                
        # We need to construct the argument
        # current_user: User = Depends(get_current_user)
        arg = ast.arg(arg="current_user", annotation=ast.Name(id="User", ctx=ast.Load()))
        default = ast.Call(
            func=ast.Name(id="Depends", ctx=ast.Load()),
            args=[ast.Name(id="get_current_user", ctx=ast.Load())],
            keywords=[]
        )
        
        # Add it to kwonlyargs so we don't mess up positional argument ordering
        node.args.kwonlyargs.append(arg)
        node.args.kw_defaults.append(default)
        
        # Now inject the check:
        # if not current_user.is_superuser and current_user.company_id != company_id: raise HTTPException(403, "Not authorized")
        
        # Check if company_id is an argument
        has_company_id = any(a.arg == "company_id" for a in node.args.args + node.args.kwonlyargs)
        if has_company_id:
            check_code = "if not current_user.is_superuser and current_user.company_id != company_id: raise HTTPException(403, 'Not authorized to access this company\\'s data')"
            check_node = ast.parse(check_code).body[0]
            node.body.insert(0, check_node)
            
        return node

for filename in os.listdir(ROUTES_DIR):
    if not filename.endswith(".py") or filename in ("__init__.py", "auth.py", "health.py", "demo.py", "live.py"):
        continue

    filepath = os.path.join(ROUTES_DIR, filename)
    with open(filepath, "r") as f:
        source = f.read()
        
    tree = ast.parse(source)
    transformer = RouteAuthTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    
    # Check if we need to add imports
    has_import = "get_current_user" in source
    if not has_import:
        import_stmt = "from app.auth.deps import get_current_user\nfrom app.models.user import User\n"
        source = import_stmt + ast.unparse(new_tree)
    else:
        source = ast.unparse(new_tree)
        
    with open(filepath, "w") as f:
        f.write(source)
        
    print(f"Processed {filename}")
