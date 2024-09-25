OS := $(shell uname -s)


.PHONY:	install
install:
	ln -sf poetry.$(OS).lock poetry.lock
	poetry install --no-root


.PHONY:	fmt
fmt:
	poetry run black .
	poetry run isort .


.PHONY:	lint
lint:
	poetry run ruff check .


.PHONY: typecheck
typecheck:
	poetry run pyright .
