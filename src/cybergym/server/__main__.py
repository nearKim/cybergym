import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Security, UploadFile, status
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from cybergym.server.config import settings
from cybergym.server.exceptions import (
    CyberGymException,
    AuthenticationException,
    RecordNotFoundException,
    ValidationException,
    DatabaseException
)
from cybergym.server.logging import ArtifactLogger, get_logger
from cybergym.server.pocdb import get_poc_by_hash, init_engine
from cybergym.server.server_utils import _post_process_result, run_poc_id, submit_poc
from cybergym.server.types import Payload, PocQuery, VerifyPocs
from cybergym.task.types import DEFAULT_SALT


SALT = DEFAULT_SALT
API_KEY_NAME = "X-API-Key"
engine: Engine = None
logger = get_logger()

def get_session():
    try:
        with Session(engine) as session:
            yield session
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        raise DatabaseException(f"Failed to create database session: {str(e)}")


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    try:
        logger.info("Starting CyberGym server lifespan")
        engine = init_engine(settings.db_path)
        logger.info(f"Database engine initialized at {settings.db_path}")
        
        import cybergym.server.events
        logger.info("Server events module loaded")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise
    finally:
        if engine:
            try:
                engine.dispose()
                logger.info("Database engine disposed")
            except Exception as e:
                logger.error(f"Error disposing database engine: {e}")


app = FastAPI(lifespan=lifespan)

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key: Optional[str] = Security(api_key_header)):
    if not api_key:
        logger.warning("API key missing in request")
        raise AuthenticationException("API key required")
    
    if api_key != settings.cybergym_api_key:
        logger.warning(f"Invalid API key attempted")
        raise AuthenticationException("Invalid API key")
    
    return api_key


public_router = APIRouter()
private_router = APIRouter(dependencies=[Depends(get_api_key)])


@public_router.post("/submit-vul")
def submit_vul(db: SessionDep, metadata: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
    logger.info(f"Received vulnerability submission request")
    
    try:
        payload = Payload.model_validate_json(metadata)
        logger.debug(f"Validated payload for agent_id={payload.agent_id}, task_id={payload.task_id}")
    except ValidationError as e:
        logger.error(f"Invalid metadata format: {e}")
        raise ValidationException("metadata", metadata, "Invalid JSON format")
    except Exception as e:
        logger.error(f"Unexpected error parsing metadata: {e}")
        raise ValidationException("metadata", metadata, str(e))
    
    try:
        payload.data = file.file.read()
        logger.debug(f"Read {len(payload.data)} bytes from uploaded file")
        
        res = submit_poc(
            db, payload, mode="vul", 
            log_dir=settings.log_dir, 
            salt=SALT, 
            oss_fuzz_path=settings.oss_fuzz_path
        )
        res = _post_process_result(res, payload.require_flag)
        
        logger.info(f"Successfully processed vulnerability submission: poc_id={res.get('poc_id')}")
        return res
        
    except CyberGymException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in submit_vul: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@private_router.post("/submit-fix")
def submit_fix(db: SessionDep, metadata: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
    logger.info(f"Received fix submission request")
    
    try:
        payload = Payload.model_validate_json(metadata)
        logger.debug(f"Validated payload for agent_id={payload.agent_id}, task_id={payload.task_id}")
    except ValidationError as e:
        logger.error(f"Invalid metadata format: {e}")
        raise ValidationException("metadata", metadata, "Invalid JSON format")
    except Exception as e:
        logger.error(f"Unexpected error parsing metadata: {e}")
        raise ValidationException("metadata", metadata, str(e))
    
    try:
        payload.data = file.file.read()
        logger.debug(f"Read {len(payload.data)} bytes from uploaded file")
        
        res = submit_poc(
            db, payload, mode="fix", 
            log_dir=settings.log_dir, 
            salt=SALT, 
            oss_fuzz_path=settings.oss_fuzz_path
        )
        res = _post_process_result(res, payload.require_flag)
        
        logger.info(f"Successfully processed fix submission: poc_id={res.get('poc_id')}")
        return res
        
    except CyberGymException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in submit_fix: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@private_router.post("/query-poc")
def query_db(db: SessionDep, query: PocQuery):
    logger.info(f"Querying PoC records: agent_id={query.agent_id}, task_id={query.task_id}")
    
    try:
        records = get_poc_by_hash(db, query.agent_id, query.task_id)
        
        if not records:
            logger.warning(f"No records found for agent_id={query.agent_id}, task_id={query.task_id}")
            raise RecordNotFoundException("PoCRecord", {"agent_id": query.agent_id, "task_id": query.task_id})
        
        logger.info(f"Found {len(records)} records for query")
        return [record.to_dict() for record in records]
        
    except RecordNotFoundException:
        raise
    except CyberGymException as e:
        logger.error(f"Database error in query_db: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query_db: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@private_router.post("/verify-agent-pocs")
def verify_all_pocs_for_agent_id(db: SessionDep, query: VerifyPocs):
    logger.info(f"Verifying all PoCs for agent_id={query.agent_id}")
    
    try:
        records = get_poc_by_hash(db, query.agent_id)
        
        if not records:
            logger.warning(f"No records found for agent_id={query.agent_id}")
            raise RecordNotFoundException("PoCRecord", {"agent_id": query.agent_id})
        
        logger.info(f"Found {len(records)} PoCs to verify for agent_id={query.agent_id}")
        
        verified_count = 0
        failed_pocs = []
        
        for record in records:
            try:
                logger.debug(f"Verifying poc_id={record.poc_id}")
                run_poc_id(db, settings.log_dir, record.poc_id, oss_fuzz_path=settings.oss_fuzz_path)
                verified_count += 1
            except Exception as e:
                logger.error(f"Failed to verify poc_id={record.poc_id}: {e}")
                failed_pocs.append({"poc_id": record.poc_id, "error": str(e)})
        
        result = {
            "message": f"Verified {verified_count}/{len(records)} PoCs for agent_id={query.agent_id}",
            "poc_ids": [record.poc_id for record in records],
            "verified_count": verified_count,
            "total_count": len(records)
        }
        
        if failed_pocs:
            result["failed_pocs"] = failed_pocs
            logger.warning(f"Some PoCs failed verification: {failed_pocs}")
        
        logger.info(f"Verification completed for agent_id={query.agent_id}")
        return result
        
    except RecordNotFoundException:
        raise
    except CyberGymException as e:
        logger.error(f"Database error in verify_all_pocs: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_all_pocs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.exception_handler(CyberGymException)
async def cybergym_exception_handler(request, exc: CyberGymException):
    logger.error(f"CyberGym exception: {exc.message}, details: {exc.details}")
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, AuthenticationException):
        status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, RecordNotFoundException):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ValidationException):
        status_code = status.HTTP_400_BAD_REQUEST
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message, "type": exc.__class__.__name__}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

app.include_router(public_router)
app.include_router(private_router)

if __name__ == "__main__":
    try:
        logger.info("Starting CyberGym Server initialization...")

        parser = argparse.ArgumentParser(description="CyberGym Server")
        parser.add_argument("--host", type=str, help="Host to run the server on")
        parser.add_argument("--port", type=int, help="Port to run the server on")
        parser.add_argument("--salt", type=str, help="Salt for checksum")
        parser.add_argument("--log_dir", type=Path, help="Directory to store logs")
        parser.add_argument("--db_path", type=Path, help="Path to SQLite DB")
        parser.add_argument("--cybergym_oss_fuzz_path", type=Path, help="Path to OSS-Fuzz")

        args = parser.parse_args()

        logger.info("Loading configuration from .env file...")
        logger.info(
            f"Server: {settings.server_ip}:{settings.server_port}, DB: {settings.db_path}, Logs: {settings.log_dir}"
        )

        settings.update_from_args(args)

        if args.salt:
            SALT = args.salt
            logger.info("Using custom salt for checksum")

        if any([args.host, args.port, args.log_dir, args.db_path, args.cybergym_oss_fuzz_path]):
            logger.info("Configuration updated with CLI arguments")

        settings.ensure_directories()
        logger.info(f"Directories created at {settings.log_dir}")

        ArtifactLogger.setup_logger(settings.get_artifact_dir())
        logger.info(f"Artifact logger initialized at {settings.get_artifact_dir()}")

        logger.info(f"Starting server on {settings.server_ip}:{settings.server_port}")
        uvicorn.run(app, host=settings.server_ip, port=settings.server_port)
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)
