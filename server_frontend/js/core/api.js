import { API_BASE_URL } from './config.js';

export class ApiClient {
    constructor() {
        this.baseUrl = API_BASE_URL;
    }
    // 도서 검색
    async searchBooks(params) {
        const { type, page = 1, perPage = 20, ...searchParams } = params;
        
        let url = `${this.baseUrl}/books/search?page=${page}&per_page=${perPage}`;
        
        if (type === 'general') {
            url += `&query=${encodeURIComponent(searchParams.query)}`;
        } else if (type === 'advanced') {
            if (searchParams.title) url += `&title=${encodeURIComponent(searchParams.title)}`;
            if (searchParams.isbn) url += `&isbn=${encodeURIComponent(searchParams.isbn)}`;
        } else if (type === 'vector') {
            url = `${this.baseUrl}/books/vector-search?page=${page}&per_page=${perPage}`;
            url += `&query=${encodeURIComponent(searchParams.query)}`;
            url += `&limit=${searchParams.limit}`;
        }

        return this.makeRequest(url);
    }

    // 주제 검색
    async searchSubjects(params) {
        const { type, page = 1, perPage = 20, ...searchParams } = params;
        
        let url = `${this.baseUrl}/subjects/search?page=${page}&per_page=${perPage}`;
        
        if (type === 'general') {
            url += `&query=${encodeURIComponent(searchParams.query)}`;
        } else if (type === 'vector') {
            url = `${this.baseUrl}/subjects/vector-search?page=${page}&per_page=${perPage}`;
            url += `&query=${encodeURIComponent(searchParams.query)}`;
            url += `&limit=${searchParams.limit}`;
        }

        return this.makeRequest(url);
    }
    // 주제어와 관련된 도서 조회
    async getSubjectRelatedBooks(nodeId, limit = 10) {
        try {
            const response = await fetch(`${this.baseUrl}/books/subject-related-books?node_id=${encodeURIComponent(nodeId)}&limit=${limit}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return { success: true, data };
        } catch (error) {
            console.error('Error fetching subject related books:', error);
            return { 
                success: false, 
                error: error.message || '관련 도서 조회 중 오류가 발생했습니다.' 
            };
        }
    }

    // 도서 상세 정보
    async getBookDetails(isbn) {
        const url = `${this.baseUrl}/books/isbn/${isbn}`;
        return this.makeRequest(url);
    }

    // 주제 상세 정보
    async getSubjectDetails(nodeId) {
        const url = `${this.baseUrl}/subjects/node_id/${nodeId}`;
        return this.makeRequest(url);
    }

    // KDC 접근점 조회
    async getKdcAccessPoints(nodeId) {
        const url = `${this.baseUrl}/subjects/kdc-access-points?node_id=${encodeURIComponent(nodeId)}`;
        return this.makeRequest(url);
    }

    // 네트워크 관련 API
    async searchSeedNode(query) {
        const url = `${this.baseUrl}/network/search-seed?query=${encodeURIComponent(query)}`;
        return this.makeRequest(url);
    }

    async getNodeNeighbors(nodeId, limit = null) {
        let url = `${this.baseUrl}/network/node/${nodeId}/neighbors`;
        if (limit) {
            url += `?limit=${limit}`;
        }
        return this.makeRequest(url);
    }

    // 챗봇 관련 API
    async getChatbotStatus() {
        const url = `${this.baseUrl}/chatbot/status`;
        return this.makeRequest(url);
    }

    async createNewSession() {
        const url = `${this.baseUrl}/chatbot/session/new`;
        return this.makeRequest(url, {
            method: 'POST'
        });
    }

    async sendChatMessage(message, sessionId) {
        const url = `${this.baseUrl}/chatbot/chat`;
        return this.makeRequest(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                role: 'user',
                content: message,
                session_id: sessionId
            })
        });
    }

    // 공통 요청 메서드
    async makeRequest(url, options = {}) {
        try {
            const response = await fetch(url, options);
            const data = await response.json();
            
            if (response.ok) {
                return { success: true, data };
            } else {
                return { success: false, error: data.detail || '요청 처리 중 오류가 발생했습니다.' };
            }
        } catch (error) {
            console.error('API 요청 오류:', error);
            return { success: false, error: '서버와의 연결에 실패했습니다.' };
        }
    }
}
