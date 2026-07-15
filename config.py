import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "school-system-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///school.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False



   