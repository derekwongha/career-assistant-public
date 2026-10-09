import json
import sys
import urllib.request

def check_lm_studio():
    url = "http://127.0.0.1:1234/v1/models"
    try:
        req = urllib.request.urlopen(url, timeout=5)
        if req.status != 200:
            sys.exit(1)
            
        data = json.loads(req.read().decode("utf-8"))
        models = [m.get("id", "") for m in data.get("data", [])]
        has_target = any("gpt-oss-20b" in m.lower() for m in models)
        
        if has_target:
            print("[OK] LM Studio API active. Model 'openai/gpt-oss-20b' is loaded.")
            print(f"     Loaded models: {models}")
            sys.exit(0)
        else:
            print("[WARNING] LM Studio API is active, but target model 'openai/gpt-oss-20b' is not loaded.")
            print(f"          Currently loaded models: {models}")
            sys.exit(1)
    except Exception as exc:
        print(f"[WARNING] Could not reach LM Studio API at {url}: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    check_lm_studio()
