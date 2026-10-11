import sys
import multiprocessing
import urllib.request
import shutil
import importlib.util
import json
import datetime

results = {}
results["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
results["python"] = sys.version
results["python_path"] = sys.executable
results["cpus"] = multiprocessing.cpu_count()

packages = [
    'pybullet', 'ortools', 'gradio', 'playwright', 
    'scipy', 'numpy', 'pandas', 'networkx', 'pytest', 
    'statsmodels', 'matplotlib', 'seaborn', 'yaml'
]
pkg_status = {}
for p in packages:
    spec = importlib.util.find_spec(p)
    if spec is not None:
        try:
            mod = __import__(p)
            pkg_status[p] = getattr(mod, '__version__', 'installed')
        except Exception as e:
            pkg_status[p] = f"error_importing: {e}"
    else:
        pkg_status[p] = "MISSING"
results["packages"] = pkg_status

latex_tools = ['pdflatex', 'latexmk', 'bibtex']
results["latex"] = {t: shutil.which(t) for t in latex_tools}

try:
    urllib.request.urlopen('http://www.google.com', timeout=3)
    results["network"] = "AVAILABLE"
except Exception as e:
    results["network"] = f"BLOCKED: {e}"

print(json.dumps(results, indent=2))
