---
name: orchestrator-architecture
description: Expert in the orchestrator's layered architecture and integration patterns
expert_type: architecture
triggers:
  keywords:
    - module
    - feature
    - implement
    - integrate
    - crud
    - api
    - endpoint
    - repository
    - service
    - routes
  topics:
    - new feature
    - add module
    - create endpoint
---

# Orchestrator Architecture Expert

You guide the planner to create complete integration plans for new features in this layered architecture.

## Focus Areas
- Layered architecture: Repository -> Service -> Routes -> Templates
- Route registration chain (routes/__init__.py -> app.py)
- Dependency injection pattern (dependencies.py)
- Page routes vs API routes distinction

## Critical Integration Chain

When adding a new feature module (e.g., "questions"), you MUST create ALL of these layers:

### 1. Repository Layer (Database Access)
```
db/repositories/{module}.py           - CRUD operations class
db/repositories/interfaces.py         - Add I{Module}Repository interface
db/repositories/__init__.py           - Export {Module}Repository
db/__init__.py                        - Export {Module}Repository
```

Example from Knowledge module:
```python
# db/repositories/knowledge.py
class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> list[Knowledge]:
        ...
```

### 2. Service Layer (Business Logic)
```
portal/services/{module}_service.py   - Business logic wrapping repository
```

Example:
```python
# portal/services/knowledge_service.py
class KnowledgeService:
    def __init__(self, repo: KnowledgeRepository):
        self._repo = repo

    async def get_knowledge_for_template(self):
        ...
```

### 3. Dependency Injection
```
portal/dependencies.py                - Add get_{module}_repo() function
```

Example:
```python
# portal/dependencies.py
async def get_knowledge_repo():
    async with get_session() as session:
        yield KnowledgeRepository(session)
```

### 4. API Routes (REST Endpoints)
```
portal/routes/{module}.py             - APIRouter with CRUD endpoints
portal/routes/__init__.py             - Import and export {module}_router
portal/app.py                         - app.include_router({module}_router)
```

Example:
```python
# portal/routes/knowledge.py
from db import KnowledgeRepository
from portal.dependencies import get_knowledge_repo

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

def _get_service(repo: KnowledgeRepository = Depends(get_knowledge_repo)):
    return KnowledgeService(repo)

@router.get("")
async def get_all(service: KnowledgeService = Depends(_get_service)):
    ...
```

### 5. Page Routes (HTML Pages)
```
portal/routes/pages.py                - Add /{module} page route
                                      - Update dashboard() if widget needed
```

Example:
```python
# portal/routes/pages.py
@router.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(
    request: Request,
    service: KnowledgeService = Depends(_get_knowledge_service),
):
    data = await service.get_knowledge_for_template()
    return templates.TemplateResponse(request, "knowledge.html", {"knowledge": data})
```

### 6. Schema Layer (Request/Response Models)
```
portal/schemas/requests.py            - Pydantic models for API contracts
```

### 7. Template Layer (UI)
```
portal/templates/{module}.html        - Main page template
portal/templates/dashboard.html       - Widget (if applicable)
```

## Planning Checklist

For any new feature that touches the database, your plan MUST include steps for:

- [ ] Database migration (if new tables)
- [ ] Repository class in `db/repositories/`
- [ ] Repository interface in `db/repositories/interfaces.py`
- [ ] Repository exports in `__init__.py` files
- [ ] Service class in `portal/services/`
- [ ] Dependency getter in `portal/dependencies.py`
- [ ] API routes in `portal/routes/{module}.py`
- [ ] Route imports in `portal/routes/__init__.py`
- [ ] Route registration in `portal/app.py`
- [ ] Page route in `portal/routes/pages.py`
- [ ] Pydantic schemas in `portal/schemas/`
- [ ] Template in `portal/templates/`

## Reference: Complete Feature Trace

To understand the full integration, trace the Knowledge module:

```
Database: db/migrations/versions/001_initial.sql (knowledge table)
    |
    v
Repository: db/repositories/knowledge.py (KnowledgeRepository)
    |
    v
Export: db/repositories/__init__.py -> db/__init__.py
    |
    v
Service: portal/services/knowledge_service.py (KnowledgeService)
    |
    v
Dependency: portal/dependencies.py (get_knowledge_repo)
    |
    v
API Routes: portal/routes/knowledge.py (router)
    |
    v
Registration: portal/routes/__init__.py -> portal/app.py
    |
    v
Page Route: portal/routes/pages.py (/knowledge)
    |
    v
Template: portal/templates/knowledge.html
```

## Common Mistakes to Avoid

1. **Creating templates without routes** - UI won't be accessible
2. **Creating routes without registration** - FastAPI won't mount them
3. **Creating repositories without exports** - Imports will fail
4. **Missing dependency injection** - Routes can't get repository instances
5. **Forgetting page routes** - Only API exists, no HTML pages
6. **Dashboard widget without data** - Widget renders but shows nothing

## Review Checklist

- [ ] All 7 layers addressed for new features
- [ ] Route registered in app.py with include_router()
- [ ] Repository exported through __init__.py chain
- [ ] Dependency getter created for repository
- [ ] Page route passes required data to template
- [ ] Dashboard updated if feature has a widget
