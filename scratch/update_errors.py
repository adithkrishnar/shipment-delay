import os
import re

frontend_dir = r"c:\Users\adith\Downloads\Telegram Desktop\supply-chain-intelligence\supply-chain-intelligence\frontend\src\pages"

files_to_update = [
    "Suppliers.jsx",
    "Anomalies.jsx",
    "Simulator.jsx",
    "Recommendations.jsx",
    "Models.jsx"
]

def update_error_state():
    for filename in files_to_update:
        filepath = os.path.join(frontend_dir, filename)
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex to find: if (error) return <div className="page"><p...>{error}</p></div>;
        # or similar.
        pattern = r"if\s*\(\s*error\s*\)\s*return\s*<div[^>]*>.*?{error}.*?</div>;"
        
        # We need to know what api function is called to generate the retry string.
        # Let's extract the api call name from the file
        # e.g., getSuppliers(company.id).then(setData)
        api_func_match = re.search(r"(\w+)\(\s*company\.id\s*\)\.then\(", content)
        if api_func_match:
            api_func = api_func_match.group(1)
            retry_code = f"setError(null); {api_func}(company.id).then(setData).catch(e => setError(e.message));"
        else:
            # Fallback if we can't find it easily
            retry_code = "window.location.reload();"
            if "simulate(" in content:
               retry_code = "setError(null);"
               
        new_error_state = f"""if (error) return (
    <div className="page animate-fade" style={{{{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}}}>
      <p style={{{{ color: 'var(--text-secondary)', marginBottom: '16px' }}}}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={{() => {{ {retry_code} }}}}>Retry</button>
    </div>
  );"""
        
        if re.search(pattern, content):
            content = re.sub(pattern, new_error_state, content)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filename}")
        else:
            print(f"Could not match error pattern in {filename}")

if __name__ == "__main__":
    update_error_state()
