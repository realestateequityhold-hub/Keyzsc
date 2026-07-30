# Quickstart

1. Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the app locally:

```bash
export FLASK_ENV=development
export SECRET_KEY="a-very-secret-key"
python app.py
```

3. Run tests:

```bash
pytest -q
```
