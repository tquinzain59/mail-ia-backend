VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: setup run test lint format precommit

setup:
	@test -d $(VENV) || python -m venv $(VENV)
	$(PIP) install -r requirements.txt
	$(VENV)/bin/pre-commit install

run:
	$(PY) -m uvicorn src.main:app --reload

test:
	$(PY) -m pytest -q

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy src

format:
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check . --fix

precommit:
	$(VENV)/bin/pre-commit run --all-files