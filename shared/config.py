import os
from pydantic_settings import BaseSettings

def read_secret(file_path: str) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Secret file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

class Settings(BaseSettings):
    compose_project_name: str = "secubrief"
    
    proxy_port: int = 80
    backend_port: int = 8000
    frontend_port: int = 3000
    
    batch_times: str = "09:00,21:00"
    batch_limit_news: int = 100
    batch_limit_papers: int = 30
    
    translator_model: str = "Qwen/Qwen2.5-7B-Instruct"
    translator_dtype: str = "fp16"
    translator_workers: int = 4
    translator_gpus_per_worker: int = 2
    
    # Secrets
    db_password: str = ""
    jwt_secret: str = ""
    naver_client_secret: str = ""
    admin_initial_password: str = ""
    
    db_password_file: str = ""
    jwt_secret_file: str = ""
    naver_client_secret_file: str = ""
    admin_initial_password_file: str = ""
    
    # Database
    db_user: str = "postgres"
    db_host: str = "db"
    db_port: str = "5432"
    db_name: str = "postgres"

    def model_post_init(self, __context):
        # DB Password
        if self.db_password_file:
            self.db_password = read_secret(self.db_password_file)
        elif not self.db_password:
            raise ValueError("db_password or db_password_file must be provided")

        # JWT Secret
        if self.jwt_secret_file:
            self.jwt_secret = read_secret(self.jwt_secret_file)
        elif not self.jwt_secret:
            raise ValueError("jwt_secret or jwt_secret_file must be provided")

        # Optional or empty external secrets might be allowed if we just need to run services
        if self.naver_client_secret_file and os.path.isfile(self.naver_client_secret_file):
            with open(self.naver_client_secret_file, "r", encoding="utf-8") as f:
                self.naver_client_secret = f.read().strip()
        
        if self.admin_initial_password_file and os.path.isfile(self.admin_initial_password_file):
            with open(self.admin_initial_password_file, "r", encoding="utf-8") as f:
                self.admin_initial_password = f.read().strip()

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
