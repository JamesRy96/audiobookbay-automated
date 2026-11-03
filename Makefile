# File: Makefile
.PHONY: run install test e2e check

run:
	uv run --env-file .env python -m audiobook_automated.app

install:
	uv sync --frozen --all-extras
	npm ci

test:
	uv run --frozen --all-extras pytest
	npm run test:js -- --runInBand

e2e:
	npm run test:e2e

check:
	uv run --frozen --all-extras pre-commit run --all-files
