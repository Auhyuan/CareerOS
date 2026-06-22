from datetime import datetime

from sqlmodel import Field, SQLModel

from app.server.job.src.models.job_model import now_time


class JobSkill(SQLModel, table=True):
    """岗位技能标准表模型，对应 job_skills。"""

    __tablename__ = "job_skills"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    normalized_name: str = Field(max_length=255, unique=True)
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=now_time)
    updated_at: datetime = Field(default_factory=now_time)
