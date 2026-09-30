# Pickleball League API

FastAPI + SQLAlchemy service backing the web interface. See the
[root README](../README.md) for setup and [docs/api.md](../docs/api.md) for the
endpoint reference.

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # http://localhost:8000/docs
pytest
```

Docker: `docker build -t pickleball-api . && docker run -p 8000:8000 -v pickleball-data:/data pickleball-api`
