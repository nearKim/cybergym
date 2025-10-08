from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from cybergym.server.env_utils import ensure_server_env
    env_path = ensure_server_env()
except:
    env_path = Path('.env')


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # Server settings
    server_ip: str = Field(default='0.0.0.0', alias='SERVER_IP')
    server_port: int = Field(default=8666, alias='SERVER_PORT')
    
    # Directories
    poc_save_dir: Path = Field(default=Path('./server_poc'), alias='POC_SAVE_DIR')
    log_dir: Path = Field(default=Path('./logs'), alias='LOG_DIR')
    db_path: Path = Field(default=Path('./poc.db'), alias='DB_PATH')
    oss_fuzz_path: Path = Field(default=Path('./oss-fuzz-data'), alias='OSS_FUZZ_PATH')
    cybergym_data_dir: Path = Field(default=Path('./cybergym_data/data'), alias='CYBERGYM_DATA_DIR')
    cybergym_server_data_dir: Path = Field(default=Path('./oss-fuzz-data'), alias='CYBERGYM_SERVER_DATA_DIR')
    out_dir: Path = Field(default=Path('./cybergym_tmp'), alias='OUT_DIR')
    
    # API settings
    cybergym_api_key: str = Field(
        default='cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d', 
        alias='CYBERGYM_API_KEY'
    )
    
    # Task settings
    task_id: Optional[str] = Field(default=None, alias='TASK_ID')
    
    def get_artifact_dir(self) -> Path:
        return self.log_dir / "artifacts"
    
    def ensure_directories(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.poc_save_dir.mkdir(parents=True, exist_ok=True)
        if self.db_path.parent != Path('.'):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.get_artifact_dir().mkdir(parents=True, exist_ok=True)
    
    def update_from_args(self, args) -> None:
        if hasattr(args, 'host') and args.host:
            self.server_ip = args.host
        if hasattr(args, 'port') and args.port:
            self.server_port = args.port
        if hasattr(args, 'log_dir') and args.log_dir:
            self.log_dir = Path(args.log_dir)
        if hasattr(args, 'db_path') and args.db_path:
            self.db_path = Path(args.db_path)
        if hasattr(args, 'cybergym_oss_fuzz_path') and args.cybergym_oss_fuzz_path:
            self.oss_fuzz_path = Path(args.cybergym_oss_fuzz_path)


settings = Settings()