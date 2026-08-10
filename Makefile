VENV := .venv
PYTHON := $(VENV)/bin/python
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest

.PHONY: bootstrap format format-check lint typecheck test check run

bootstrap:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --requirement requirements-dev.lock
	$(PYTHON) -m pip install --no-deps --editable .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

format-check:
	$(RUFF) format --check .

lint:
	$(RUFF) check .

typecheck:
	$(MYPY) src tests

test:
	$(PYTEST)

check: format-check lint typecheck test

run:
	$(PYTHON) -m it_activity
