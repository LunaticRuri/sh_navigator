import { RELATION_TYPE_KOREAN } from './config.js';

// 로딩 표시/숨김
export function showLoading(show, type) {
    const loading = document.getElementById(`loading-${type}`);
    if (show) {
        loading.innerHTML = `
            <div class="loading-spinner"></div>
            <span class="loading-text">검색 중...</span>
        `;
        loading.style.display = 'flex';
    } else {
        loading.style.display = 'none';
        loading.innerHTML = '';
    }
}

// 결과 초기화
export function clearResults(type) {
    const elements = [
        `results-${type}-container`,
        `pagination-${type}`,
        `search-${type}-info`
    ];

    elements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.innerHTML = '';
        }
    });
}

// 에러 메시지 표시
export function showError(message, type = 'book') {
    let containerId;

    switch (type) {
        case 'book':
            containerId = 'results-book-container';
            break;
        case 'subject':
            containerId = 'results-subject-container';
            break;
        case 'network':
            containerId = 'seed-candidates';
            break;
        default:
            containerId = 'results-book-container';
    }
    
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `
            <div class="error-message">
                <strong>오류:</strong> ${message}
            </div>
        `;
    }
}

// 성공 메시지 표시
export function showSuccess(message, type = 'book') {
    let containerId;

    switch (type) {
        case 'book':
            containerId = 'results-book-container';
            break;
        case 'subject':
            containerId = 'results-subject-container';
            break;
        case 'network':
            containerId = 'seed-candidates';
            break;
        default:
            containerId = 'results-book-container';
    }

    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `
            <div class="success-message">
                ${message}
            </div>
        `;
    }
}

// 관계 유형 한글 변환
export function getRelationTypeKorean(relationType) {
    return RELATION_TYPE_KOREAN[relationType] || relationType;
}

// 현재 활성 메뉴 타입 가져오기
export function getCurrentMenuType() {
    const activeMenu = document.querySelector('.menu-item.active');
    return activeMenu ? (activeMenu.getAttribute('data-menu-type') || 'book') : 'book';
}

// 텍스트 자르기
export function truncateText(text, maxLength) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// 마크다운을 HTML로 변환
export function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
        });
        return marked.parse(text);
    } else {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
}

// 시간 포맷팅
export function formatTime() {
    return new Date().toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// HTML 이스케이프 함수 추가
export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}