VENV := .venv
SYSTEM_PYTHON ?= python3
PYTHON := $(VENV)/bin/python
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest

.PHONY: bootstrap format format-check lint typecheck test dependency-check check run

bootstrap:
	$(SYSTEM_PYTHON) -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(PYTHON) -m pip install --requirement requirements-dev.lock
	$(PYTHON) -m pip install --no-deps --no-build-isolation --editable .

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

dependency-check:
	$(PYTHON) -m pip check

check: format-check lint typecheck test dependency-check

run:
	$(PYTHON) -m it_activity
