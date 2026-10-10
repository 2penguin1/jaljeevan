"""Write backend/openapi.json so the frontend can generate TypeScript types without a running server.

Run: cd backend && uv run python -m scripts.export_openapi
"""
import json
from pathlib import Path

from app.main import app

out = Path(__file__).resolve().parents[1] / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
