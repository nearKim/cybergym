import datetime
from pathlib import Path
from typing import Optional
import logging as std_logging

from sqlalchemy import Column, DateTime, Engine, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from cybergym.server.exceptions import (
    DatabaseException,
    RecordNotFoundException,
    DuplicateRecordException,
    ValidationException
)

logger = std_logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def now():
    return datetime.datetime.now(datetime.UTC)


class PoCRecord(Base):
    __tablename__ = "poc_records"
    id = Column(Integer, primary_key=True)
    agent_id = Column(String, index=True)
    task_id = Column(String, index=True)
    poc_id = Column(String, unique=True, index=True)
    poc_hash = Column(String, index=True)
    poc_length = Column(Integer, nullable=True)
    vul_exit_code = Column(Integer, nullable=True)
    fix_exit_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=now, nullable=False)
    updated_at = Column(DateTime, default=now, onupdate=now, nullable=False)
    __table_args__ = (UniqueConstraint("agent_id", "task_id", "poc_hash", name="_agent_task_hash_uc"),)

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "poc_id": self.poc_id,
            "poc_hash": self.poc_hash,
            "poc_length": self.poc_length,
            "vul_exit_code": self.vul_exit_code,
            "fix_exit_code": self.fix_exit_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def get_or_create_poc(
    db: Session, agent_id: str, task_id: str, poc_id: str, poc_hash: str, poc_length: int
) -> PoCRecord:
    if not agent_id or not task_id or not poc_id or not poc_hash:
        logger.error(f"Invalid parameters: agent_id={agent_id}, task_id={task_id}, poc_id={poc_id}, poc_hash={poc_hash}")
        raise ValidationException("parameters", {"agent_id": agent_id, "task_id": task_id}, "Required fields missing")
    
    try:
        logger.debug(f"Querying PoC record: agent_id={agent_id}, task_id={task_id}, poc_hash={poc_hash}")
        record = db.query(PoCRecord).filter_by(agent_id=agent_id, task_id=task_id, poc_hash=poc_hash).first()
        
        if record:
            logger.debug(f"Found existing PoC record: poc_id={record.poc_id}")
            return record
        
        logger.debug(f"Creating new PoC record: poc_id={poc_id}")
        record = PoCRecord(
            agent_id=agent_id,
            task_id=task_id,
            poc_id=poc_id,
            poc_hash=poc_hash,
            poc_length=poc_length,
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        logger.info(f"Created new PoC record: poc_id={poc_id}, agent_id={agent_id}, task_id={task_id}")
        return record
        
    except IntegrityError as e:
        logger.error(f"Integrity error creating PoC record: {e}")
        db.rollback()
        raise DuplicateRecordException("PoCRecord", f"{agent_id}/{task_id}/{poc_hash}") from e
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_or_create_poc: {e}")
        db.rollback()
        raise DatabaseException(f"Failed to create PoC record: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error in get_or_create_poc: {e}")
        db.rollback()
        raise DatabaseException(f"Unexpected error: {str(e)}") from e


def update_poc_output(db: Session, record: PoCRecord, mode: str, exit_code: int):
    if not record:
        logger.error("Attempted to update null PoC record")
        raise ValidationException("record", None, "PoC record is required")
    
    if mode not in ["vul", "fix"]:
        logger.error(f"Invalid mode: {mode}")
        raise ValidationException("mode", mode, "Mode must be 'vul' or 'fix'")
    
    try:
        logger.debug(f"Updating PoC output: poc_id={record.poc_id}, mode={mode}, exit_code={exit_code}")
        
        if mode == "vul":
            record.vul_exit_code = exit_code
        elif mode == "fix":
            record.fix_exit_code = exit_code
        
        db.commit()
        logger.info(f"Updated PoC output: poc_id={record.poc_id}, mode={mode}, exit_code={exit_code}")
        
    except SQLAlchemyError as e:
        logger.error(f"Database error updating PoC output: {e}")
        db.rollback()
        raise DatabaseException(f"Failed to update PoC output: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error updating PoC output: {e}")
        db.rollback()
        raise DatabaseException(f"Unexpected error: {str(e)}") from e


def get_poc_by_hash(
    db: Session,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    poc_hash: Optional[str] = None,
    limit: Optional[int] = None
) -> list[PoCRecord]:
    filters = {}
    if agent_id is not None:
        filters["agent_id"] = agent_id
    if task_id is not None:
        filters["task_id"] = task_id
    if poc_hash is not None:
        filters["poc_hash"] = poc_hash
    
    if not filters:
        logger.warning("get_poc_by_hash called without filters")
        raise ValidationException("filters", filters, "At least one filter must be provided")
    
    try:
        logger.debug(f"Querying PoC records with filters: {filters}")
        query = db.query(PoCRecord).filter_by(**filters)
        
        if limit:
            query = query.limit(limit)
        
        records = query.all()
        logger.debug(f"Found {len(records)} PoC records matching filters")
        
        return records
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_poc_by_hash: {e}")
        raise DatabaseException(f"Failed to query PoC records: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error in get_poc_by_hash: {e}")
        raise DatabaseException(f"Unexpected error: {str(e)}") from e


def init_engine(db_path: Path) -> Engine:
    if not db_path:
        logger.error("Database path is required")
        raise ValidationException("db_path", None, "Database path is required")
    
    try:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing database engine at: {db_path}")
        
        engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
            pool_size=64,
            max_overflow=64,
            pool_pre_ping=True
        )
        
        Base.metadata.create_all(engine)
        logger.info("Database engine initialized successfully")
        
        return engine
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database engine: {e}")
        raise DatabaseException(f"Failed to initialize database: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error initializing database: {e}")
        raise DatabaseException(f"Unexpected error: {str(e)}") from e
