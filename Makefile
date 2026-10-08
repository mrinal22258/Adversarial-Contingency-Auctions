.PHONY: all reproduce sweep tables figures test clean

all: reproduce

reproduce:
	python experiments/run_extended_sweep.py
	python experiments/make_tables.py
	python experiments/make_figures.py

sweep:
	python experiments/run_extended_sweep.py

tables:
	python experiments/make_tables.py

figures:
	python experiments/make_figures.py

test:
	pytest

lint:
	python tools/lint_paper.py

clean:
	python -c "import shutil, glob, os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + ['.pytest_cache']]; [os.remove(f) for f in glob.glob('paper.*') if not f.endswith(('.tex', '.pdf', '.bbl'))]"

