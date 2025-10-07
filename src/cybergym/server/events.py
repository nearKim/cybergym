from sqlalchemy import event

from .pocdb import PoCRecord
from .logging import get_artifact_logger


@event.listens_for(PoCRecord, 'after_insert')
def log_poc_creation(mapper, connection, target: PoCRecord):
    logger = get_artifact_logger()
    try:
        logger.log_poc_record(target.to_dict())
    except Exception as e:
        print(f"Error logging poc creation: {e}")


@event.listens_for(PoCRecord, 'after_update')
def log_poc_update(mapper, connection, target: PoCRecord):
    logger = get_artifact_logger()
    try:
        logger.update_poc_record(target.to_dict())
    except Exception as e:
        print(f"Error logging poc creation: {e}")
