.PHONY: all results reproduce sweep tables figures test lint clean paper release release-check

all: results

results:
	python tools/build_all_results.py

reproduce: results

sweep:
	python experiments/run_extended_sweep.py

tables:
	python experiments/make_tables.py

figures:
	python experiments/make_figures.py

test:
	pytest

paper:
	python tools/build_paper.py

lint:
	python tools/lint_paper.py

clean:
	python -c "import shutil, glob, os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + ['.pytest_cache']]; [os.remove(f) for f in glob.glob('paper.*') if not f.endswith(('.tex', '.pdf', '.bbl'))]"

release:
	python tools/make_release.py

release-check:
	python tools/check_anonymity.py

