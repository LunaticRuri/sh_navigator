from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union


class BookResponse(BaseModel):
    """Model for book data responses"""
    isbn: str = Field(..., description="Book ISBN")
    title: Optional[str] = Field(None, description="Book title")
    kdc: Optional[str] = Field(None, description="Korean Decimal Classification")
    publication_year: Optional[str] = Field(None, description="Publication year")
    intro: Optional[str] = Field(None, description="Book introduction")
    toc: Optional[str] = Field(None, description="Table of contents")
    nlk_subjects: Optional[str] = Field(None, description="NLK subject headings")

class BookListResponse(BaseModel):
    """Model for a list of books"""
    books: List[BookResponse] = Field(..., description="List of books")
    total_count: int = Field(..., description="Total number of books")

class SubjectResponse(BaseModel):
    """Model for subject heading responses"""
    node_id: str = Field(..., description="Subject node ID")
    label: str = Field(..., description="Subject label")
    definition: Optional[str] = Field(None, description="Subject definition")
    relations: Optional[List[Dict[str, Any]]] = Field(None, description="Related subjects")

class SearchResponse(BaseModel):
    """Model for paginated search responses"""
    results: List[Union[BookResponse, SubjectResponse]] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total number of results")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Results per page")
    total_pages: int = Field(..., description="Total number of pages")

class KDCAccessPointResponse(BaseModel):
    """Model for KDC access point responses"""
    kdc: str = Field(..., description="KDC code")
    label: str = Field(..., description="KDC label")
    is_direct: bool = Field(..., description="Indicates if this is a direct KDC access point")
    books: BookListResponse = Field(..., description="List of books associated with this KDC access point")

class KDCAccessPointListResponse(BaseModel):
    """Model for a list of KDC access points"""
    access_points: List[KDCAccessPointResponse] = Field(..., description="List of KDC access points")
    total_count: int = Field(..., description="Total number of KDC access points")