# Thai Job Board Aggregator

ระบบค้นหาและรวบรวมประกาศงานจาก JobsDB Thailand พร้อม scoring engine และ export ผลลัพธ์เป็น JSON หรือ Excel

**Stack**: FastAPI · Vue 3 (Vite) · Redis · Python 3.11+

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+ with pnpm
- Redis (optional — falls back to in-memory cache if unavailable)

### Backend

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright Chromium (required for fallback scraping)
playwright install chromium --with-deps

# 4. Copy env config
cp .env.example .env

# 5. Start the backend
uvicorn backend.main:app --reload
```

Backend runs at http://localhost:8000

### Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

Frontend runs at http://localhost:5173

---

## Docker Quick Start

```bash
# Copy env config first
cp .env.example .env

# Build and start all services (backend + redis + frontend)
docker compose up --build
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Redis: localhost:6379

> **Note:** Playwright requires `playwright install chromium --with-deps` after pip install. This is handled automatically in the Docker image by `Dockerfile.backend`.

---

## Environment Variables

See `.env.example` for all configurable settings. Key variables:

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `CACHE_TTL_SECONDS` | `7200` | Cache TTL in seconds (2 hours) |
| `DEFAULT_PAGE_SIZE` | `100` | Default number of jobs returned |
| `MAX_PAGE_SIZE` | `500` | Maximum allowed page size |
| `MAX_RETRIES` | `3` | Scraper retry attempts |
| `RETRY_BASE_DELAY` | `1.0` | Base delay for exponential backoff (seconds) |
| `DETAIL_BATCH_SIZE` | `10` | Concurrent job detail fetch batch size |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

---

## Architecture Overview

```
SearchForm → POST /search → Cache check
                                 ↓ miss
                          JobsDB GraphQL API
                                 ↓ 401/403 or exhausted
                          Playwright Fallback (JSON-LD)
                                 ↓
                          get_detail() × N  (batch 10)
                                 ↓
                          Skills Extraction (vocab match)
                                 ↓
                          Scoring Engine (weighted, 5 criteria)
                                 ↓
                          Store in Cache → SearchResponse
                                 ↓
                          ResultsTable → Export (JSON/Excel)
```

### Scoring Weights (defaults)

| Criterion | Default Weight |
|---|---|
| Keywords | 30% |
| Skills | 25% |
| Salary | 20% |
| Location | 15% |
| Experience | 10% |

Weights are renormalised at runtime — they always sum to 1.0 regardless of raw input values.

---

## Running Tests

```bash
# All backend tests
pytest backend/tests/

# All frontend tests
cd frontend && pnpm run test -- --run
```

Or with the Makefile:

```bash
make test-backend
make test-frontend
```

---

## Skills Vocabulary

ระบบดึงทักษะจาก job description โดยจับคู่กับ vocabulary list ที่กำหนดไว้ใน `backend/scrapers/jobsdb.py`

### กลไกการทำงาน

1. ลอก HTML ออกด้วย BeautifulSoup
2. แปลงข้อความเป็นตัวพิมพ์เล็ก
3. จับคู่แต่ละคำใน vocab ด้วย whole-word boundary matching
4. คืนผลเป็น sorted, deduplicated `list[str]`

### การเพิ่ม / แก้ไข Vocabulary

เปิดไฟล์ `backend/scrapers/jobsdb.py` หา `SKILLS_VOCAB` แล้วแก้ไขได้เลย:

```python
SKILLS_VOCAB: list[str] = [
    # Languages
    "python", "javascript", "typescript", "java", "go", "rust",
    "c++", "c#",

    # Frontend
    "react", "vue", "angular",
    # ...
]
```

**กฎ 4 ข้อ:**

**1. ใช้ตัวพิมพ์เล็กเสมอ** — ระบบ lowercase ข้อความก่อน match

```python
"svelte"   # ถูก
"Svelte"   # ผิด
```

**2. คำที่มีสัญลักษณ์ — เพิ่มได้ทันที ไม่ต้องแก้ regex**

regex ที่ใช้อยู่รองรับ `c++`, `c#`, `node.js`, `ci/cd` อยู่แล้ว

**3. คำหลายคำ (multi-word) — เพิ่มได้ทันที**

```python
"data analysis", "prompt engineering", "large language model"
```

**4. ระวังคำสั้นมากๆ** — ควรทดสอบก่อนเพิ่มคำที่สั้นกว่า 2 ตัวอักษร

### ทดสอบคำใหม่ก่อนเพิ่มจริง

```python
from backend.scrapers.jobsdb import extract_skills

new_vocab = ["svelte", "bun"]

assert "svelte" in extract_skills("<p>We use Svelte and TypeScript</p>", new_vocab)
assert "bun" not in extract_skills("<p>bundle webpack abundance</p>", new_vocab)

print("OK")
```

### จัด group เมื่อ vocab ใหญ่ขึ้น

vocab 39 คำปัจจุบันยังจัดการได้ง่าย แต่เมื่อเกิน ~80 คำแนะนำแยก comment group:

```python
SKILLS_VOCAB: list[str] = [
    # Languages
    "python", "javascript", ...
    # Frontend Frameworks
    "react", "vue", ...
    # Backend Frameworks
    "fastapi", "django", ...
    # Cloud & DevOps
    "docker", "kubernetes", "aws", ...
    # Data & AI
    "sql", "machine learning", ...
    # Soft Skills
    "communication", "leadership", ...
]
```

### แนวทางปรับปรุงในอนาคต

| แนวทาง | เหมาะเมื่อ |
|---|---|
| Data-driven mining (นับคำจาก job data จริง) | มีข้อมูลสะสมแล้ว อยากให้ vocab อัปเดตตามตลาด |
| ESCO Skills Ontology (~13,000 ทักษะ, open dataset) | ต้องการมาตรฐาน มี synonym ครบ |
| LLM extraction | vocab ไม่เพียงพอ ยอมรับ latency และ cost เพิ่ม |
