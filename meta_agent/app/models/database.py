import enum
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ────────────────────────────────────────────────────────────────────

class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentType(enum.Enum):
    CODE_GENERATOR = "code_generator"
    API_DESIGNER = "api_designer"
    DATABASE_SCHEMA = "database_schema"
    TESTING_AGENT = "testing_agent"
    DOCUMENTATION_AGENT = "documentation_agent"


# ── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project id={self.id} name={self.name}>"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    agent_type = Column(Enum(AgentType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)

    # Execution order / dependency tracking
    execution_order = Column(Integer, default=0)
    dependency_ids = Column(JSON, default=list)  # List of Task IDs this depends on

    # Data flowing in and out
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="tasks")
    subtasks = relationship("Task", backref="parent_task", remote_side=[id])
    executions = relationship("AgentExecution", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Task id={self.id} agent={self.agent_type} status={self.status}>"


class AgentExecution(Base):
    """
    Logs every LLM call made by an agent.
    Critical for debugging + cost tracking.
    """
    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)

    agent_name = Column(String(100), nullable=False)
    llm_provider = Column(String(50), nullable=False)   # openai / anthropic
    model_used = Column(String(100), nullable=False)

    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Integer, default=0)     # stored as microdollars (x1,000,000)

    execution_time_ms = Column(Integer, default=0)
    success = Column(Integer, default=1)                 # 1=success, 0=failure

    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="executions")

    def __repr__(self):
        return f"<AgentExecution id={self.id} agent={self.agent_name} tokens={self.total_tokens}>"