import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = "ai-career-copilot-secret"

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://"
        f"{os.getenv('TIDB_USER')}:"
        f"{os.getenv('TIDB_PASSWORD')}@"
        f"{os.getenv('TIDB_HOST')}:"
        f"{os.getenv('TIDB_PORT', '4000')}/"
        f"{os.getenv('TIDB_DATABASE')}"
        f"?ssl_verify_cert=true"
        f"&ssl_verify_identity=true"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False


