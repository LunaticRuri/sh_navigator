import logging
import aiosqlite
from typing import Dict, Optional
from core.config import KDC_DB_PATH

logger = logging.getLogger(__name__)


class KDCCache:
    """KDC 코드와 라벨을 메모리에 캐시하는 클래스"""
    
    def __init__(self):
        self._kdc_cache: Dict[str, str] = {}
        self._initialized = False
    
    async def initialize(self):
        """KDC 데이터를 로드하여 메모리에 캐시"""
        if self._initialized:
            return
            
        try:
            async with aiosqlite.connect(KDC_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.cursor()
                
                await cursor.execute("SELECT section_number, section_name, keywords FROM sections")
                rows = await cursor.fetchall()
                
                for section_number, section_name, keywords in rows:
                    self._kdc_cache[section_number] = {
                        "name": section_name,
                        "keywords": keywords if keywords else ""
                    }
                
                logger.info(f"Loaded {len(self._kdc_cache)} KDC labels into cache")
                self._initialized = True
                
        except Exception as e:
            logger.error(f"Failed to initialize KDC cache: {e}")
            # 기본값으로 빈 딕셔너리 사용
            self._kdc_cache = {}
            self._initialized = True
    
    def get_kdc_name(self, kdc_code: str) -> str:
        """
        KDC 코드에 해당하는 라벨 반환
        
        Args:
            kdc_code: KDC 코드 (예: "001", "004")
            
        Returns:
            KDC 라벨 또는 기본값
        """
        if not self._initialized:
            return f"KDC {kdc_code}"
        
        if kdc_code not in self._kdc_cache:
            # KDC 코드가 캐시에 없으면 기본값 반환
            return f"KDC {kdc_code}"
        
        return self._kdc_cache[kdc_code].get("name", f"KDC {kdc_code}")
    
    def get_kdc_keywords(self, kdc_code: str) -> str:
        """
        KDC 코드에 해당하는 키워드 반환
        
        Args:
            kdc_code: KDC 코드 (예: "001", "004")
            
        Returns:
            KDC 키워드 또는 기본값
        """
        if not self._initialized:
            return ""
        
        if kdc_code not in self._kdc_cache:
            # KDC 코드가 캐시에 없으면 빈 문자열 반환
            return ""
        return self._kdc_cache[kdc_code].get("keywords", "") 

    def get_all_cache(self) -> Dict[str, str]:
        """모든 KDC 라벨 반환"""
        return self._kdc_cache.copy()
    
    async def refresh(self):
        """캐시 새로고침"""
        self._initialized = False
        await self.initialize()


# 전역 인스턴스
_kdc_cache_instance: Optional[KDCCache] = None


def get_kdc_cache() -> KDCCache:
    """전역 KDC 캐시 인스턴스 반환"""
    global _kdc_cache_instance
    if _kdc_cache_instance is None:
        _kdc_cache_instance = KDCCache()
    return _kdc_cache_instance


async def initialize_kdc_cache():
    """전역 KDC 캐시 초기화"""
    cache = get_kdc_cache()
    await cache.initialize()