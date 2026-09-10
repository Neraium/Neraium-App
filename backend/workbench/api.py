"""Single-operator Historical Evaluation workbench API."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import threading
import uuid
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from . import authority, intake, report, store

app = FastAPI(title="Neraium Internal Historical Evaluation Workbench", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3006", "http://127.0.0.1:3006"],
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
execution_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return uuid.uuid4().hex


def digest(value):
    return hashlib.sha256(store.encode(value).encode()).hexdigest()


router = APIRouter(prefix="/api")

@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc), **({"timestamp_review": exc.choices}
                        if isinstance(exc, intake.TimestampReview) else {})}, status_code=422)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse({"detail": "Record not found"}, status_code=404)


@app.exception_handler(authority.AuthorityError)
async def unavailable(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=503)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evaluation(Model):
    mode: Literal["single", "paired"] = "single"
    label: str = Field(default="", max_length=200)
    customer: str = Field(default="", max_length=200)
    facility: str = Field(default="", max_length=200)
    system: str = Field(default="", max_length=200)
    scope: str = Field(default="", max_length=2000)


class Validation(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    timestamp_column: str = ""
    timestamp_mode: str = ""


class Signal(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    column: str = Field(max_length=160)
    include: bool
    meaning: str = Field(default="", max_length=160)
    unit: str = Field(default="", max_length=40)
    reason: str = Field(default="", max_length=500)


class Mapping(Model):
    pair_confirmed: bool = False
    context: str = Field(default="", max_length=2000)
    signals: list[Signal] = Field(min_length=1, max_length=63)
    start: str = ""
    end: str = ""


class Approval(Model):
    preview_id: str
    confirmed: bool


class Review(Model):
    reviewer: str = Field(min_length=1, max_length=160)
    evidence_reviewed: bool


@router.get("/authority")
def authority_status():
    try:
        return {"available": True, "identity": authority.identity()}
    except authority.AuthorityError as exc:
        return {"available": False, "reason": str(exc)}


@router.get("/evaluations")
def evaluations():
    with closing(store.connect()) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT document FROM evaluations ORDER BY rowid DESC")]


@router.post("/evaluations", status_code=201)
def create_evaluation(body: Evaluation):
    value = {**body.model_dump(), "id": identifier(), "created_at": now(), "stage": "DATA RECEIVED", "revision": 0}
    with closing(store.connect()) as db, db:
        db.execute("INSERT INTO evaluations VALUES (?,?)", (value["id"], store.encode(value)))
    return value


@router.get("/evaluations/{evaluation_id}")
def evaluation(evaluation_id: str):
    with closing(store.connect()) as db:
        value = store.get(db, "evaluations", evaluation_id)
        if value.get("reference_source_id"):
            source = store.get(db, "sources", value["reference_source_id"])
            value["reference_source"] = {k: v for k, v in source.items() if k != "table"}
            value["reference_source"]["columns"] = source["table"]["columns"]
        if value.get("source_id"):
            source = store.get(db, "sources", value["source_id"])
            value["source"] = {k: v for k, v in source.items() if k != "table"}
            value["source"]["columns"] = source["table"]["columns"]
            value["source"]["preview"] = source["table"]["rows"][:8]
        runs = [json.loads(row[0]) for row in db.execute("SELECT document FROM runs WHERE evaluation_id=? ORDER BY rowid DESC", (evaluation_id,))]
        value["runs"] = [{k: r.get(k) for k in ("id", "status", "created_at", "error", "source_id")} for r in runs]
        return value


@router.post("/evaluations/{evaluation_id}/source", status_code=201)
async def upload(evaluation_id: str, request: Request, filename: str, role: Literal["reference", "comparison"] = "comparison"):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > intake.MAX_BYTES:
            raise HTTPException(413, "Maximum upload size is 10 MiB.")
    table = intake.parse(bytes(raw), filename)
    source = {"id": identifier(), "filename": filename.replace("\\", "/").split("/")[-1][:200],
              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "received_at": now(), "table": table}
    with closing(store.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        value = store.get(db, "evaluations", evaluation_id)
        if role == "reference" and value.get("mode") != "paired":
            raise ValueError("Reference upload requires a paired evaluation.")
        db.execute("INSERT INTO sources VALUES (?,?,?,?)", (source["id"], evaluation_id, bytes(raw), store.encode(source)))
        for key in ("reference_validation" if role == "reference" else "validation", "mapping", "preview", "approved_mapping", "latest_run_id"):
            value.pop(key, None)
        value["reference_source_id" if role == "reference" else "source_id"] = source["id"]
        value.update(stage="VALIDATION", revision=value["revision"] + 1)
        store.save_evaluation(db, value)
    return {"source_id": source["id"], "sha256": source["sha256"]}


@router.get("/sources/{source_id}/original")
def original(source_id: str):
    with closing(store.connect()) as db:
        row = db.execute("SELECT raw FROM sources WHERE id=?", (source_id,)).fetchone()
        if row is None:
            raise KeyError(source_id)
        return Response(row[0], media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="source-{source_id}.bin"'})


@router.post("/evaluations/{evaluation_id}/validate")
def validate(evaluation_id: str, body: Validation, role: Literal["reference", "comparison"] = "comparison"):
    with closing(store.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        value = store.get(db, "evaluations", evaluation_id)
        source = store.get(db, "sources", value["reference_source_id" if role == "reference" else "source_id"])
        validation = (intake.validate(source["table"], body.timestamp_column, body.timestamp_mode,
                                      allow_source_clock=value.get("mode") == "paired")
                      if body.timestamp_column else intake.auto_validate(source["table"], allow_source_clock=value.get("mode") == "paired"))
        for key in ("mapping", "preview", "approved_mapping", "latest_run_id"):
            value.pop(key, None)
        value["reference_validation" if role == "reference" else "validation"] = validation
        eligible = validation["eligible_timestamps"] and (value.get("mode") != "paired" or
                    all(value.get(k, {}).get("eligible_timestamps") for k in ("validation", "reference_validation")))
        value.update(stage="SIGNAL/SYSTEM MAPPING" if eligible else "VALIDATION", revision=value["revision"] + 1)
        store.save_evaluation(db, value)
    return validation


def build_input(value, source, mapping):
    if value.get("mode") != "paired":
        return intake.analysis_input(source["table"], value["validation"], mapping)
    if not value.get("reference_source_id") or not value.get("reference_validation") or not value.get("validation"):
        raise ValueError("Upload and validate both reference and comparison before mapping.")
    with closing(store.connect()) as db:
        reference = store.get(db, "sources", value["reference_source_id"])
    return intake.paired_input(reference["table"], source["table"], value["reference_validation"], value["validation"], mapping)


@router.post("/evaluations/{evaluation_id}/mapping-preview")
def preview_mapping(evaluation_id: str, body: Mapping):
    with closing(store.connect()) as db:
        value = store.get(db, "evaluations", evaluation_id)
        if not value.get("source_id"):
            raise ValueError("Upload and validate the comparison dataset before mapping.")
        source = store.get(db, "sources", value["source_id"])
    mapping = body.model_dump()
    payload = build_input(value, source, mapping)
    response = authority.call(payload, "preview")
    preview = {"id": identifier(), "catalog": response["catalog"], "identity": response["identity"],
               "input_sha256": digest(payload), "created_at": now()}
    with closing(store.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = store.get(db, "evaluations", evaluation_id)
        if current["revision"] != value["revision"]:
            raise HTTPException(409, "Evaluation changed during preview; reload and try again.")
        current.pop("approved_mapping", None)
        current.pop("latest_run_id", None)
        current.update(mapping=mapping, preview=preview, stage="SIGNAL/SYSTEM MAPPING", revision=current["revision"] + 1)
        store.save_evaluation(db, current)
    return preview


@router.post("/evaluations/{evaluation_id}/approve-mapping")
def approve_mapping(evaluation_id: str, body: Approval):
    with closing(store.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        value = store.get(db, "evaluations", evaluation_id)
        if not body.confirmed or body.preview_id != value.get("preview", {}).get("id"):
            raise HTTPException(409, "Confirm the current authority classification preview first.")
        value.update(approved_mapping={"preview_id": body.preview_id, "approved_at": now()}, stage="ANALYSIS", revision=value["revision"] + 1)
        store.save_evaluation(db, value)
    return {"approved": True}


@router.post("/evaluations/{evaluation_id}/runs", status_code=201)
def analyze(evaluation_id: str):
    if not execution_lock.acquire(blocking=False):
        raise HTTPException(409, "Another analysis is running; wait for it to finish.")
    try:
        with closing(store.connect()) as db, db:
            value = store.get(db, "evaluations", evaluation_id)
            if not value.get("approved_mapping"):
                raise HTTPException(409, "Approve signal mapping before analysis.")
            source = store.get(db, "sources", value["source_id"])
            payload = build_input(value, source, value["mapping"])
            if digest(payload) != value["preview"]["input_sha256"] or authority.identity() != value["preview"]["identity"]:
                raise HTTPException(409, "Inputs or authority changed; create and approve a new preview.")
            run = {"id": identifier(), "evaluation_id": evaluation_id, "source_id": source["id"],
                   "created_at": now(), "status": "running", "evaluation": value,
                   "source": {k: v for k, v in source.items() if k != "table"},
                   "validation": value["validation"], "mapping": value["mapping"], "input": payload,
                   "input_sha256": digest(payload)}
            if value.get("mode") == "paired":
                reference = store.get(db, "sources", value["reference_source_id"])
                run["reference_source"] = {k: v for k, v in reference.items() if k != "table"}
                run["reference_validation"] = value["reference_validation"]
            run["request_sha256"] = digest({**payload, "run_id": run["id"]})
            db.execute("INSERT INTO runs VALUES (?,?,?)", (run["id"], evaluation_id, store.encode(run)))
        try:
            response = authority.call({**payload, "run_id": run["id"]})
            if response["catalog"] != value["preview"]["catalog"]:
                raise authority.AuthorityError("Authority classification changed since approval; result rejected.")
            run.update(status=response["result"]["status"], response=response,
                       result_sha256=digest(response["result"]))
        except authority.AuthorityError as exc:
            run.update(status="failed", error=str(exc))
        run["finished_at"] = now()
        with closing(store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE runs SET document=? WHERE id=?", (store.encode(run), run["id"]))
            current = store.get(db, "evaluations", evaluation_id)
            if current["revision"] == value["revision"]:
                current.update(stage="RESULTS", latest_run_id=run["id"])
                store.save_evaluation(db, current)
        return {"id": run["id"], "status": run["status"], "error": run.get("error")}
    finally:
        execution_lock.release()


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    with closing(store.connect()) as db:
        run = store.get(db, "runs", run_id)
        run["reviews"] = [{k: v for k, v in json.loads(row[0]).items() if k != "html"} for row in db.execute("SELECT document FROM reviews WHERE run_id=? ORDER BY rowid DESC", (run_id,))]
    run["evidence_sections"] = report.evidence_sections(run.get("response", {}).get("result", {}))
    return run


@router.get("/runs/{run_id}/evidence")
def evidence(run_id: str):
    with closing(store.connect()) as db:
        run = store.get(db, "runs", run_id)
    return Response(store.encode(run), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="neraium-evidence-{run_id}.json"'})


@router.post("/runs/{run_id}/reviews", status_code=201)
def review(run_id: str, body: Review):
    with closing(store.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        run = store.get(db, "runs", run_id)
        if run["status"] not in {"complete", "limited"} or not body.evidence_reviewed:
            raise HTTPException(409, "Review a complete or limited authoritative result before producing a report.")
        value = {"id": identifier(), "run_id": run_id, "created_at": now(), **body.model_dump()}
        value["html"] = report.render(run, value)
        value["report_sha256"] = hashlib.sha256(value["html"].encode()).hexdigest()
        db.execute("INSERT INTO reviews VALUES (?,?,?)", (value["id"], run_id, store.encode(value)))
        evaluation = store.get(db, "evaluations", run["evaluation_id"])
        if evaluation.get("latest_run_id") == run_id:
            evaluation["stage"] = "CUSTOMER REPORT"
            store.save_evaluation(db, evaluation)
    return {k: v for k, v in value.items() if k != "html"}


@router.get("/reviews/{review_id}/report")
def customer_report(review_id: str):
    with closing(store.connect()) as db:
        review = store.get(db, "reviews", review_id)
    return HTMLResponse(review["html"], headers={"Content-Disposition": f'attachment; filename="neraium-report-{review_id}.html"'})


app.include_router(router)
