from pydantic import BaseModel, Field
from typing import List, Optional


class NetworkNode(BaseModel):
    """Model for network visualization nodes"""
    node_id: str = Field(..., description="Node identifier")
    label: str = Field(..., description="Node label")
    definition: str = Field(default="", description="Node definition")
    type: str = Field(..., description="Node type (current/neighbor)")


class NetworkEdge(BaseModel):
    """Model for network visualization edges"""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relation_type: str = Field(..., description="Type of relationship")
    metadata: Optional[str] = Field(None, description="Additional metadata")


class NetworkResponse(BaseModel):
    """Model for network visualization responses"""
    nodes: List[NetworkNode] = Field(..., description="Network nodes")
    edges: List[NetworkEdge] = Field(..., description="Network edges")
    center_node: str = Field(..., description="Central node ID")


class SeedNodeCandidate(BaseModel):
    """Model for seed node search candidates"""
    node_id: str = Field(..., description="Node identifier")
    label: str = Field(..., description="Node label")
    definition: str = Field(default="", description="Node definition")


class SeedNodeResponse(BaseModel):
    """Model for seed node search responses"""
    candidates: List[SeedNodeCandidate] = Field(..., description="Candidate nodes")
    

class PoolStatus(BaseModel):
    """Model for database connection pool status"""
    current_connections: int = Field(..., description="Current active connections")
    max_connections: int = Field(..., description="Maximum allowed connections")
    pool_size: int = Field(..., description="Current pool size")
    pool_available: bool = Field(..., description="Pool availability status")
