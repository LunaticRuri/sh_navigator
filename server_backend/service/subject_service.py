from functools import lru_cache
import logging
import time
import httpx
from typing import List, Dict, Any
from fastapi import HTTPException
from database.database_manager import DatabaseManager
from core.kdc_cache import get_kdc_cache
from schemas.search import SubjectResponse, SearchResponse, BookListResponse, BookResponse, KDCAccessPointResponse, KDCAccessPointListResponse
from collections import defaultdict
from core.utils import (
    sanitize_query, 
    truncate_string, 
    calculate_pagination, 
    sort_relations_by_priority,
    limit_relations,
    log_search_query,
    safe_json_parse
)
from core.config import (
    MAX_QUERY_LENGTH,
    MODEL_SERVER_URL
)

logger = logging.getLogger(__name__)


class SubjectService:
    """Service class for subject-related operations."""

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize the subject service.
        
        Args:
            embedding_model: SentenceTransformer model for embeddings
            db_connection_manager: Database connection manager function
        """
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.database_manager = database_manager
        self.kdc_cache = get_kdc_cache()
        
    async def search_subjects(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20
    ) -> SearchResponse:
        """
        Search subjects using full-text search.
        
        Args:
            query: Search query
            page: Page number
            per_page: Results per page
            
        Returns:
            SearchResponse with subject results
        """
        try:
            if not query:
                raise HTTPException(status_code=400, detail="검색어를 제공해야 합니다.")
            
            # Sanitize query
            query = sanitize_query(query)

            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Build search queries
                base_query = "SELECT node_id FROM subjects_fts WHERE label MATCH ?"
                count_query = "SELECT COUNT(*) FROM subjects_fts WHERE label MATCH ?"
                params = [query]
                
                # Get total count
                await cursor.execute(count_query, params)
                result = await cursor.fetchone()
                total_count = result[0]
                
                # Calculate pagination
                pagination = calculate_pagination(total_count, page, per_page)
                
                # Get results with pagination
                final_query = f"{base_query} ORDER BY RANK LIMIT ? OFFSET ?"
                await cursor.execute(final_query, params + [per_page, pagination["offset"]])
                result_node_ids = await cursor.fetchall()
                
                # Get detailed subject information
                if result_node_ids:
                    node_id_list = [row['node_id'] for row in result_node_ids]
                    subjects_data = await self._get_subjects_by_node_ids(cursor, node_id_list)
                else:
                    subjects_data = []
                
                # Convert to response models
                subjects = [self._row_to_subject_response(row) for row in subjects_data]
                
                # Log search for analytics
                log_search_query("subject_text_search", query, len(subjects))
                
                return SearchResponse(
                    results=subjects,
                    total_count=total_count,
                    page=page,
                    per_page=per_page,
                    total_pages=pagination["total_pages"]
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in subject search: {e}")
            raise HTTPException(status_code=500, detail=f"검색 중 오류가 발생했습니다: {str(e)}")

    async def get_subject_by_node_id(self, node_id: str) -> SubjectResponse:
        """
        Get a specific subject by node ID with its relations.
        
        Args:
            node_id: Subject node ID
            
        Returns:
            SubjectResponse with subject details and relations
        """
        try:
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Get subject details
                await cursor.execute("SELECT * FROM subjects WHERE node_id = ?", (node_id,))
                subject_data = await cursor.fetchone()
                
                if not subject_data:
                    raise HTTPException(status_code=404, detail="주제를 찾을 수 없습니다.")
                
                # Get relations
                relations = await self._get_subject_relations(cursor, node_id)
                
                return SubjectResponse(
                    node_id=subject_data['node_id'],
                    label=subject_data['label'],
                    definition=subject_data['definition'] or '',
                    relations=relations
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting subject by node_id {node_id}: {e}")
            raise HTTPException(status_code=500, detail="주제 조회 중 오류가 발생했습니다.")

    async def vector_search_subjects(
        self,
        query: str,
        limit: int = 25,
        page: int = 1,
        per_page: int = 20
    ) -> SearchResponse:
        """
        Search subjects using vector similarity.
        
        Args:
            query: Search query for vector search
            limit: Maximum number of results from FAISS
            page: Page number
            per_page: Results per page
            
        Returns:
            SearchResponse with subject results
        """
        try:
            # Validate and truncate query
            query = truncate_string(query, MAX_QUERY_LENGTH)
            
            # Generate query embedding
            time_start = time.time()
            response = await self.http_client.post(
                f"{MODEL_SERVER_URL}/search/subjects",
                json={"query": query, "limit": limit}
            )
            response.raise_for_status()
            search_data = response.json()
            retrieved_node_ids = search_data.get("retrieved_node_ids", [])
            logger.info(f"Query embedding and FAISS search completed in {time.time() - time_start:.2f} seconds")
            
            # Check if results exist
            if not retrieved_node_ids:
                return SearchResponse(
                    results=[],
                    total_count=0,
                    page=page,
                    per_page=per_page,
                    total_pages=0
                )
            
            # Get subject details from database
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Calculate pagination
                total_count = min(len(retrieved_node_ids), limit)
                pagination = calculate_pagination(total_count, page, per_page)
                
                # Get current page data (filter by definition length)
                current_page_limit = min(per_page, max(0, total_count - pagination["offset"]))
                
                final_query = """
                    SELECT node_id, label, definition 
                    FROM subjects 
                    WHERE node_id IN ({}) AND length(definition) > 30
                    LIMIT ? OFFSET ?
                """.format(','.join('?' for _ in retrieved_node_ids))
                
                await cursor.execute(
                    final_query, 
                    (*retrieved_node_ids, current_page_limit, pagination["offset"])
                )
                
                subjects_data = await cursor.fetchall()
                
                # Sort by original FAISS order
                subjects_data = sorted(
                    subjects_data, 
                    key=lambda x: retrieved_node_ids.index(x[0])
                )

                # Convert to response models
                subjects = [self._row_to_subject_response(row) for row in subjects_data]
                
                # Log search for analytics
                log_search_query("subject_vector_search", query, len(subjects))
                
                return SearchResponse(
                    results=subjects,
                    total_count=total_count,
                    page=page,
                    per_page=per_page,
                    total_pages=pagination["total_pages"]
                )
    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Subject vector search error: {e}")
            raise HTTPException(status_code=500, detail=f"벡터 검색 중 오류가 발생했습니다: {str(e)}")

    async def get_kdc_access_points(self, node_id: str) -> KDCAccessPointListResponse:
        """
        Get KDC access points for a specific node.
        
        Args:
            node_id: Subject node ID
        Returns:
            KDCAccessPointListResponse with KDC access points and associated books
        """
        
        try:
            # Validate node_id
            if not node_id:
                raise HTTPException(status_code=400, detail="주제 ID를 제공해야 합니다.")
            async with self.database_manager.get_connection() as book_conn:
                book_cursor = await book_conn.cursor()
                book_subject_index_query = "SELECT isbn FROM book_subject_index WHERE node_id = ?"
                await book_cursor.execute(book_subject_index_query, (node_id,))
                
                retrieved_isbns = await book_cursor.fetchall()
                if not retrieved_isbns:
                    
                    async with self.database_manager.get_connection() as subject_conn:
                        subject_cursor = await subject_conn.cursor()
                        neighbors_dict = await self._get_node_neighbors(subject_cursor, node_id, 10)
                    
                    logger.info(f"Retrieved neighbors for node {node_id}: {neighbors_dict}")
                    
                    retrieved_isbns_indirect = []
                    for neighbor in neighbors_dict:
                        neighbor_node_id = neighbor["neighbor_id"]
                        await book_cursor.execute(book_subject_index_query, (neighbor_node_id,))
                        neighbor_isbns = await book_cursor.fetchall()
                        if not neighbor_isbns:
                            continue
                        retrieved_isbns_indirect.extend(neighbor_isbns)
                    
                    if not retrieved_isbns_indirect:
                        return KDCAccessPointListResponse(
                            access_points=[],
                            total_count=0
                        )
                
                    is_direct = False
                    retrieved_isbns = retrieved_isbns_indirect
                
                else:
                    is_direct = True
                        

                # Flatten the list of tuples to a list of ISBNs
                retrieved_isbns = [row[0] for row in retrieved_isbns]
                
                book_subject_index_query = """
                SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects FROM books 
                WHERE isbn IN ({}) LIMIT 100
                """.format(','.join('?' for _ in retrieved_isbns))

                await book_cursor.execute(book_subject_index_query, (*retrieved_isbns,))

                books_data = await book_cursor.fetchall()

                books = []
                for row in books_data:
                    books.append(
                        BookResponse(
                        isbn=row["isbn"],
                        title=row["title"],
                        kdc=row["kdc"],
                        publication_year=row["publication_year"],
                        intro=row["intro"],
                        toc=row["toc"],
                        nlk_subjects=row["nlk_subjects"]
                    )
                )
                
                log_search_query("subject_related_books", book_subject_index_query, len(books))

                # Group books by KDC (first 3 digits)
                kdc_groups = defaultdict(list)
                for book in books:
                    kdc_code = (book.kdc or "")[:3]
                    kdc_groups[kdc_code].append(book)

                # Build KDC access point responses
                kdc_access_points = []
                for kdc_code, group_books in kdc_groups.items():
                    if not kdc_code: # Skip if KDC code is empty
                        continue
                    kdc_access_points.append(
                        KDCAccessPointResponse(
                            kdc= kdc_code,
                            label= self.kdc_cache.get_kdc_name(kdc_code),
                            is_direct= True if is_direct else False,
                            books= BookListResponse(
                                books=group_books,
                                total_count=len(group_books)
                            )
                        )
                    )

                # Sort by KDC code
                kdc_access_points.sort(key=lambda x: x.kdc)

                return KDCAccessPointListResponse(
                    access_points=kdc_access_points,
                    total_count=len(kdc_access_points)
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in subject related books search: {e}")
            raise HTTPException(status_code=500, detail=f"KDC 엑세스 포인트 탐색 중 오류가 발생했습니다: {str(e)}")

    async def _get_subjects_by_node_ids(self, cursor, node_id_list: List[str]) -> List[Dict]:
        """
        Get subject details by list of node IDs.
        
        Args:
            cursor: Database cursor
            node_id_list: List of node IDs
            
        Returns:
            List of subject data dictionaries
        """
        query = """
            SELECT node_id, label, definition 
            FROM subjects 
            WHERE node_id IN ({})
        """.format(','.join(['?'] * len(node_id_list)))
        
        await cursor.execute(query, node_id_list)
        return await cursor.fetchall()

    async def _get_subject_relations(self, cursor, node_id: str) -> List[Dict[str, Any]]:
        """
        Get relations for a specific subject.
        
        Args:
            cursor: Database cursor
            node_id: Subject node ID
            
        Returns:
            List of relation dictionaries
        """
        await cursor.execute("""
            SELECT 
                r.source_id,
                r.target_id,
                s2.label AS target_label,
                r.relation_type,
                r.metadata
            FROM relations r
            JOIN subjects s1 ON r.source_id = s1.node_id
            LEFT JOIN subjects s2 ON r.target_id = s2.node_id
            WHERE r.source_id = ?
            ORDER BY r.relation_type, s2.label;
        """, (node_id,))
        
        relations = await cursor.fetchall()
        
        # Convert to dictionaries and add similarity scores
        relations_list = []
        for rel in relations:
            relation_dict = {
                "source_id": rel["source_id"],
                "target_id": rel["target_id"],
                "target_label": rel["target_label"],
                "relation_type": rel["relation_type"],
                "metadata": rel["metadata"]
            }
            
            # Add similarity score for cosine relations
            if rel["relation_type"] == "cosine_related":
                metadata = safe_json_parse(rel["metadata"], {})
                relation_dict["_similarity"] = metadata.get("similarity", 0)
            
            relations_list.append(relation_dict)
        
        # Sort and limit relations
        relations_list = sort_relations_by_priority(relations_list)
        relations_list = limit_relations(relations_list, 20)
        
        return relations_list

    async def _get_node_neighbors(self, cursor, node_id: str, limit: int) -> List[Dict]:
        """
        Get neighbor nodes for network visualization and kdc access points.
        
        Args:
            cursor: Database cursor
            node_id: Central node ID
            limit: Maximum number of neighbors
            
        Returns:
            List of neighbor dictionaries
        """
        await cursor.execute("""
            SELECT DISTINCT
                CASE 
                    WHEN r.source_id = ? THEN r.target_id
                    ELSE r.source_id
                END as neighbor_id,
                s.label,
                s.definition,
                r.relation_type,
                r.metadata
            FROM relations r
            JOIN subjects s ON (
                (r.source_id = ? AND s.node_id = r.target_id) OR
                (r.target_id = ? AND s.node_id = r.source_id)
            )
            WHERE r.source_id = ? OR r.target_id = ?
            ORDER BY 
                CASE 
                    WHEN r.relation_type != 'cosine_related' THEN 0 
                    ELSE 1 
                END,
                CASE 
                    WHEN r.relation_type = 'cosine_related' THEN 
                        CAST(json_extract(r.metadata, '$.similarity') AS REAL)
                    ELSE 0
                END DESC
            LIMIT ?
        """, (node_id, node_id, node_id, node_id, node_id, limit))
        
        return await cursor.fetchall()

    def _row_to_subject_response(self, row, include_relations: bool = False) -> SubjectResponse:
        """
        Convert database row to SubjectResponse model.
        
        Args:
            row: Database row
            include_relations: Whether to include relations
            
        Returns:
            SubjectResponse model
        """
        return SubjectResponse(
            node_id=row["node_id"],
            label=row["label"],
            definition=row["definition"] or '',
            relations=[] if not include_relations else None
        )

# 전역 서비스 인스턴스
_subject_service_instance = None

def set_subject_service(database_manager: DatabaseManager):
    """전역 subject service 인스턴스 설정"""
    global _subject_service_instance
    _subject_service_instance = SubjectService(database_manager)

@lru_cache()
def get_subject_service() -> SubjectService:
    """FastAPI 의존성으로 사용할 subject service 인스턴스 반환"""
    if _subject_service_instance is None:
        raise RuntimeError("Subject service not initialized")
    return _subject_service_instance