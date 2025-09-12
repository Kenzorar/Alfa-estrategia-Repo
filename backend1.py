from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import shutil
import uuid

app = FastAPI(title="Plan Estrategico API (minimal)")

UPLOAD_DIR = Path("e:/vsc/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Schemas
class ObjetiveCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_year: int
    end_year: int

class Objetive(ObjetiveCreate):
    id: int

class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    year: int

class Goal(GoalCreate):
    id: int
    objetive_id: int

class IndicatorCreate(BaseModel):
    title: str
    target: Optional[str] = None
    unit: Optional[str] = None

class Indicator(IndicatorCreate):
    id: int
    goal_id: int

class EvidenceCreate(BaseModel):
    description: Optional[str] = ""
    filename: str
    original_filename: Optional[str] = None

class Evidence(EvidenceCreate):
    id: int
    indicator_id: int
    uploaded_at: Optional[str] = None


# In-memory store (minimal, no DB)
class InMemoryStore:
    def __init__(self):
        self._objectives: dict[int, Objetive] = {}
        self._goals: dict[int, List[Goal]] = {}      # objetive_id -> goals
        self._inds: dict[int, List[Indicator]] = {}  # goal_id -> indicators
        self._evid: dict[int, Evidence] = {}
        self._c = {"obj": 0, "goal": 0, "ind": 0, "evi": 0}

    # Objetives
    def create_objetive(self, payload: ObjetiveCreate) -> Objetive:
        self._c["obj"] += 1
        oid = self._c["obj"]
        obj = Objetive(id=oid, **payload.dict())
        self._objectives[oid] = obj
        return obj

    def list_objetives(self) -> List[Objetive]:
        return list(self._objectives.values())

    def get_objetive(self, oid: int) -> Optional[Objetive]:
        return self._objectives.get(oid)

    # Goals
    def create_goal(self, objetive_id: int, payload: GoalCreate) -> Optional[Goal]:
        if objetive_id not in self._objectives:
            return None
        self._c["goal"] += 1
        gid = self._c["goal"]
        goal = Goal(id=gid, objetive_id=objetive_id, **payload.dict())
        self._goals.setdefault(objetive_id, []).append(goal)
        # initialize indicators list for this goal id
        self._inds.setdefault(gid, [])
        return goal

    def list_goals(self, objetive_id: int) -> List[Goal]:
        return self._goals.get(objetive_id, [])

    def get_goal(self, goal_id: int) -> Optional[Goal]:
        for goals in self._goals.values():
            for g in goals:
                if g.id == goal_id:
                    return g
        return None

    # Indicators
    def create_indicator(self, goal_id: int, payload: IndicatorCreate) -> Optional[Indicator]:
        if self.get_goal(goal_id) is None:
            return None
        self._c["ind"] += 1
        iid = self._c["ind"]
        ind = Indicator(id=iid, goal_id=goal_id, **payload.dict())
        self._inds.setdefault(goal_id, []).append(ind)
        return ind

    def list_indicators(self, goal_id: int) -> List[Indicator]:
        return self._inds.get(goal_id, [])

    def get_indicator(self, indicator_id: int) -> Optional[Indicator]:
        for inds in self._inds.values():
            for ind in inds:
                if ind.id == indicator_id:
                    return ind
        return None

    # Evidence
    def create_evidence(self, indicator_id: int, payload: EvidenceCreate) -> Optional[Evidence]:
        if self.get_indicator(indicator_id) is None:
            return None
        self._c["evi"] += 1
        eid = self._c["evi"]
        uploaded_at = datetime.utcnow().isoformat()
        ev = Evidence(id=eid, indicator_id=indicator_id, uploaded_at=uploaded_at, **payload.dict())
        self._evid[eid] = ev
        return ev

    def get_evidence(self, evidence_id: int) -> Optional[Evidence]:
        return self._evid.get(evidence_id)


store = InMemoryStore()

# Routes
@app.post("/objetives", response_model=Objetive)
def create_objetive(payload: ObjetiveCreate):
    return store.create_objetive(payload)

@app.get("/objetives", response_model=List[Objetive])
def list_objetives():
    return store.list_objetives()

@app.get("/objetives/{objetive_id}", response_model=Objetive)
def get_objetive(objetive_id: int):
    obj = store.get_objetive(objetive_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objetive not found")
    return obj

@app.post("/objetives/{objetive_id}/goals", response_model=Goal)
def create_goal(objetive_id: int, payload: GoalCreate):
    goal = store.create_goal(objetive_id, payload)
    if not goal:
        raise HTTPException(status_code=404, detail="Objetive not found")
    return goal

@app.get("/objetives/{objetive_id}/goals", response_model=List[Goal])
def list_goals(objetive_id: int):
    return store.list_goals(objetive_id)

@app.post("/goals/{goal_id}/indicators", response_model=Indicator)
def create_indicator(goal_id: int, payload: IndicatorCreate):
    ind = store.create_indicator(goal_id, payload)
    if not ind:
        raise HTTPException(status_code=404, detail="Goal not found")
    return ind

@app.get("/goals/{goal_id}/indicators", response_model=list[Indicator])
def list_indicators(goal_id: int):
    return store.list_indicators(goal_id)

@app.post("/indicators/{indicator_id}/evidences", response_model=Evidence)
def upload_evidence(indicator_id: int, file: UploadFile = File(...), description: str = ""):
    ind = store.get_indicator(indicator_id)
    if not ind:
        raise HTTPException(status_code=404, detail="Indicator not found")

    ext = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOAD_DIR / filename
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ev = store.create_evidence(
        indicator_id,
        EvidenceCreate(description=description, filename=filename, original_filename=file.filename),
    )
    if not ev:
        raise HTTPException(status_code=400, detail="Could not create evidence")
    return ev

@app.get("/evidences/{evidence_id}", response_model=Evidence)
def get_evidence(evidence_id: int):
    ev = store.get_evidence(evidence_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return ev

@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})

