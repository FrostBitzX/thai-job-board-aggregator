import json
from datetime import datetime, timezone

from backend.models.job import ScoredJob


def export_json(jobs: list[ScoredJob], search_id: str) -> bytes:
    payload = {
        "search_id": search_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total": len(jobs),
        "jobs": [j.model_dump() for j in jobs],
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
