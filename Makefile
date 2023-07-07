PYTHON=python3

install_poetry:
        python3 -m pip install poetry
        python3 -m poetry install


run: install_poetry
        poetry run $(PYTHON) -m app
