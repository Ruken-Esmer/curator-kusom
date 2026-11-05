"""
CURATOR — Pydantic Models
Domain models, request/response schemas, and graph node types.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


#  Enumerations

class Language(str, Enum):
    EN = "en"
    TR = "tr"


class QueryType(str, Enum):
    FACTUAL = "factual"          # "What topics are in Y2B1?"
    RELATIONAL = "relational"    # "How does anatomy connect to physiology?"
    PATHWAY = "pathway"          # "What should I study before cardiology?"
    ADVISORY = "advisory"        # "What should I review for Year 4?"
    UNKNOWN = "unknown"


class NodeType(str, Enum):
    YEAR = "Year"
    BLOCK = "Block"
    TOPIC = "Topic"
    COMPETENCY = "Competency"
    DEPARTMENT = "Department"
    LEARNING_OBJECTIVE = "LearningObjective"
    ASSESSMENT = "Assessment"


class RelationType(str, Enum):
    PREREQUISITE_OF = "PREREQUISITE_OF"
    CONTAINS = "CONTAINS"
    COVERS_TOPIC = "COVERS_TOPIC"
    ASSESSES_COMPETENCY = "ASSESSES_COMPETENCY"
    TAUGHT_BY = "TAUGHT_BY"
    INTEGRATES_WITH = "INTEGRATES_WITH"
    LEADS_TO = "LEADS_TO"


#  Knowledge Graph Node Models

class YearNode(BaseModel):
    id: str
    year_number: int
    name_en: str
    name_tr: str
    description_en: str = ""
    description_tr: str = ""
    institution: str = "koc_university"


class BlockNode(BaseModel):
    id: str                     # e.g. "Y2B1"
    year: int
    block_number: int
    name_en: str
    name_tr: str
    weeks: str
    departments: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    prerequisite_ids: list[str] = Field(default_factory=list)
    competencies: list[str] = Field(default_factory=list)
    description_en: str = ""
    description_tr: str = ""


class TopicNode(BaseModel):
    id: str
    name_en: str
    name_tr: str = ""
    block_ids: list[str] = Field(default_factory=list)
    department: str = ""


class CompetencyNode(BaseModel):
    id: str
    name_en: str
    name_tr: str = ""
    domain: str = ""


#  RAG Pipeline Models

class RetrievedChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    source: str                 # block_id or topic_id
    source_type: str            # "block" | "topic" | "graph"
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    block_id: str
    block_name: str
    year: int
    relevance: float = 0.0


class PathwayStep(BaseModel):
    order: int
    block_id: str
    block_name: str
    year: int
    reason: str = ""


#  API Request / Response Schemas

class ChatMessage(BaseModel):
    role: str                   # "user" | "assistant"
    content: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    language: Language = Language.EN
    institution: str = "koc_university"
    conversation_history: list[ChatMessage] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    query_type: QueryType
    citations: list[Citation] = Field(default_factory=list)
    pathway: list[PathwayStep] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)   # pathway links the student can report
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    language: Language
    processing_time_ms: float = 0.0


class CurriculumTreeResponse(BaseModel):
    institution: str
    years: list[dict[str, Any]]


class GraphQueryRequest(BaseModel):
    node_id: str
    depth: int = Field(default=2, ge=1, le=4)


class GraphQueryResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    neo4j: bool = False
    vector_store: bool = False
    llm: str = ""
