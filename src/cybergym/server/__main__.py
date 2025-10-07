import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Security, UploadFile, status
from fastapi.security import APIKeyHeader
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from cybergym.server.config import settings
from cybergym.server.logging import ArtifactLogger
from cybergym.server.pocdb import get_poc_by_hash, init_engine
from cybergym.server.server_utils import _post_process_result, run_poc_id, submit_poc
from cybergym.server.types import Payload, PocQuery, VerifyPocs
from cybergym.task.types import DEFAULT_SALT

SALT = DEFAULT_SALT
API_KEY_NAME = "X-API-Key"
engine: Engine = None


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = init_engine(settings.db_path)

    import cybergym.server.events

    yield

    if engine:
        engine.dispose()


app = FastAPI(lifespan=lifespan)

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == settings.cybergym_api_key:
        return api_key
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


public_router = APIRouter()
private_router = APIRouter(dependencies=[Depends(get_api_key)])


@public_router.post("/submit-vul")
def submit_vul(db: SessionDep, metadata: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
    try:
        payload = Payload.model_validate_json(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid metadata format") from None
    payload.data = file.file.read()
    res = submit_poc(db, payload, mode="vul", log_dir=settings.log_dir, salt=SALT, oss_fuzz_path=settings.oss_fuzz_path)
    res = _post_process_result(res, payload.require_flag)
    return res


@private_router.post("/submit-fix")
def submit_fix(db: SessionDep, metadata: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
    try:
        payload = Payload.model_validate_json(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid metadata format") from None
    payload.data = file.file.read()
    res = submit_poc(db, payload, mode="fix", log_dir=settings.log_dir, salt=SALT, oss_fuzz_path=settings.oss_fuzz_path)
    res = _post_process_result(res, payload.require_flag)
    return res


@private_router.post("/query-poc")
def query_db(db: SessionDep, query: PocQuery):
    records = get_poc_by_hash(db, query.agent_id, query.task_id)
    if not records:
        raise HTTPException(status_code=404, detail="Record not found")
    return [record.to_dict() for record in records]


@private_router.post("/verify-agent-pocs")
def verify_all_pocs_for_agent_id(db: SessionDep, query: VerifyPocs):
    records = get_poc_by_hash(db, query.agent_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records found for this agent_id")

    for record in records:
        run_poc_id(db, settings.log_dir, record.poc_id, oss_fuzz_path=settings.oss_fuzz_path)

    return {
        "message": f"All {len(records)} PoCs for this agent_id have been verified",
        "poc_ids": [record.poc_id for record in records],
    }


app.include_router(public_router)
app.include_router(private_router)

if __name__ == "__main__":
    print("[INFO] Starting CyberGym Server initialization...")

    parser = argparse.ArgumentParser(description="CyberGym Server")
    parser.add_argument("--host", type=str, help="Host to run the server on")
    parser.add_argument("--port", type=int, help="Port to run the server on")
    parser.add_argument("--salt", type=str, help="Salt for checksum")
    parser.add_argument("--log_dir", type=Path, help="Directory to store logs")
    parser.add_argument("--db_path", type=Path, help="Path to SQLite DB")
    parser.add_argument("--cybergym_oss_fuzz_path", type=Path, help="Path to OSS-Fuzz")

    args = parser.parse_args()

    print(f"[INFO] Loading configuration from .env file...")
    print(
        f"[INFO] Server: {settings.server_ip}:{settings.server_port}, DB: {settings.db_path}, Logs: {settings.log_dir}")

    settings.update_from_args(args)

    if args.salt:
        SALT = args.salt
        print(f"[INFO] Using custom salt for checksum")

    if any([args.host, args.port, args.log_dir, args.db_path, args.cybergym_oss_fuzz_path]):
        print(f"[INFO] Configuration updated with CLI arguments")

    settings.ensure_directories()
    print(f"[INFO] Directories created at {settings.log_dir}")

    ArtifactLogger.setup_logger(settings.get_artifact_dir())
    print(f"[INFO] Artifact logger initialized at {settings.get_artifact_dir()}")

    print(f"[INFO] Starting server on {settings.server_ip}:{settings.server_port}")
    uvicorn.run(app, host=settings.server_ip, port=settings.server_port)
