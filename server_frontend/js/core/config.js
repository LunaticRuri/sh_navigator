// API 설정
export const API_BASE_URL = window.location.origin;

// 페이지네이션 설정
export const DEFAULT_PER_PAGE = 20;

// 네트워크 시각화 설정
export const NETWORK_CONFIG = {
    width: 800,
    height: 600,
    nodeRadius: 15,
    linkDistance: 100,
    chargeStrength: -300,
    collisionRadius: 30
};

// 관계 유형 한글 매핑
export const RELATION_TYPE_KOREAN = {
    'broader': '상위 주제',
    'narrower': '하위 주제',
    'related': '관련 주제',
    'cosine_related': '유사 벡터 주제',
    'generated': '생성된 관계',
    'subject_book': '주제-도서'
};
