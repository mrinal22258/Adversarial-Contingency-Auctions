PYTHON ?= python

.PHONY: all results reproduce sweep tables figures test lint clean paper release release-check audit

all: results

results:
	$(PYTHON) tools/build_all_results.py

reproduce: results

sweep:
	$(PYTHON) experiments/run_extended_sweep.py

tables:
	$(PYTHON) experiments/make_tables.py

figures:
	$(PYTHON) experiments/make_figures.py

test:
	pytest

audit: release-check
	$(PYTHON) tools/verify_protocol.py

paper:
	$(PYTHON) tools/build_paper.py

lint:
	$(PYTHON) tools/lint_paper.py

clean:
	$(PYTHON) -c "import shutil, glob, os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + ['.pytest_cache']]; [os.remove(f) for f in glob.glob('paper.*') if not f.endswith(('.tex', '.pdf', '.bbl'))]"

release:
	$(PYTHON) tools/make_release.py

release-check:
	$(PYTHON) tools/check_anonymity.py

