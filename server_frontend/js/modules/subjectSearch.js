import { ApiClient } from '../core/api.js';
import { showLoading, clearResults, showError, truncateText, getRelationTypeKorean } from '../core/utils.js';

export class SubjectSearchModule {
    constructor() {
        this.apiClient = new ApiClient();
        this.currentSearch = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // 주제 검색 필드들에 엔터 키 지원
        ['general-subject-query', 'vector-subject-query'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        if (id === 'vector-subject-query') {
                            this.performVectorSearch();
                        } else {
                            this.performGeneralSearch();
                        }
                    }
                });
            }
        });
    }

    // 일반 주제 검색
    async performGeneralSearch() {
        const query = document.getElementById('general-subject-query').value.trim();
        if (!query) {
            alert('검색어를 입력해주세요.');
            return;
        }

        this.currentSearch = { type: 'general', query: query };
        this.currentPage = 1;
        await this.searchSubjects();
    }

    // 벡터 주제 검색
    async performVectorSearch() {
        const query = document.getElementById('vector-subject-query').value.trim();
        const limit = document.getElementById('vector-subject-limit').value;

        if (!query) {
            alert('검색어를 입력해주세요.');
            return;
        }

        this.currentSearch = { type: 'vector', query: query, limit: parseInt(limit) };
        this.currentPage = 1;
        await this.searchSubjects();
    }

    // 주제 검색 실행
    async searchSubjects() {
        if (!this.currentSearch) return;

        showLoading(true, 'subject');
        clearResults('subject');

        const params = {
            ...this.currentSearch,
            page: this.currentPage,
            perPage: 20
        };

        const result = await this.apiClient.searchSubjects(params);

        if (result.success) {
            this.displayResults(result.data);
            this.updatePagination(result.data);
        } else {
            showError(result.error, 'subject');
        }

        showLoading(false, 'subject');
    }

    // 검색 결과 표시
    displayResults(data) {
        const container = document.getElementById('results-subject-container');
        const searchInfo = document.getElementById('search-subject-info');

        // 검색 정보 표시
        if (data.total_count === 0) {
            searchInfo.innerHTML = `<strong>검색 결과:</strong> 총 0개의 주제가 검색되었습니다.`;
        } else {
            searchInfo.innerHTML = `
                <strong>검색 결과:</strong> 총 ${data.total_count.toLocaleString()}개의 주제가 검색되었습니다. 
                (${data.page}/${data.total_pages} 페이지)
            `;
        }

        // 결과가 없는 경우
        if (data.results.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <h3>검색 결과가 없습니다</h3>
                    <p>다른 검색어로 시도해보세요.</p>
                </div>
            `;
            return;
        }

        // 주제 목록 표시
        container.innerHTML = data.results.map(subject => `
            <div class="subject-item" onclick="window.subjectSearchModule.showSubjectDetails('${subject.node_id}')">
                <div class="subject-title">${subject.label || '주제명 없음'}</div>
                <div class="subject-meta">
                    <span><strong>주제 ID:</strong> ${subject.node_id}</span>
                </div>
                ${subject.definition ? `<div class="subject-definition">${truncateText(subject.definition, 200)}</div>` : ''}
            </div>
        `).join('');

        this.totalPages = data.total_pages;
    }

    // 페이지네이션 업데이트
    updatePagination(data) {
        const pagination = document.getElementById('pagination-subject');
        const totalPages = data.total_pages;
        const currentPage = data.page;

        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let paginationHTML = '';

        // 이전 페이지 버튼
        paginationHTML += `
            <button onclick="window.subjectSearchModule.goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                ← 이전
            </button>
        `;

        // 페이지 번호 버튼들
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        if (startPage > 1) {
            paginationHTML += `<button onclick="window.subjectSearchModule.goToPage(1)">1</button>`;
            if (startPage > 2) {
                paginationHTML += `<span>...</span>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <button onclick="window.subjectSearchModule.goToPage(${i})" class="${i === currentPage ? 'active' : ''}">
                    ${i}
                </button>
            `;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += `<span>...</span>`;
            }
            paginationHTML += `<button onclick="window.subjectSearchModule.goToPage(${totalPages})">${totalPages}</button>`;
        }

        // 다음 페이지 버튼
        paginationHTML += `
            <button onclick="window.subjectSearchModule.goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                다음 →
            </button>
        `;

        pagination.innerHTML = paginationHTML;
    }

    // 페이지 이동
    async goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        await this.searchSubjects();
    }

    // 주제 상세 정보 표시
    async showSubjectDetails(nodeId) {
        const result = await this.apiClient.getSubjectDetails(nodeId);

        if (result.success) {
            const subject = result.data;
            const modal = document.getElementById('subject-modal');
            const details = document.getElementById('subject-details');

            // 관련 도서 정보 가져오기
            let relatedBooksHTML = '';
            try {
                const booksResult = await this.apiClient.getSubjectRelatedBooks(nodeId, 10);
                if (booksResult.success && booksResult.data.books && booksResult.data.books.length > 0) {
                    relatedBooksHTML = `
                        <div class="subject-detail-section">
                            <h3>관련 도서 (${booksResult.data.books.length}개)</h3>
                            <div class="related-books-list">
                                ${booksResult.data.books.map(book => `
                                    <div class="related-book-item">
                                        <div class="book-title">${book.title}</div>
                                        <div class="book-meta">
                                            <span><strong>출간연도:</strong> ${book.publication_year || '정보 없음'}</span>
                                            ${book.kdc ? `<span><strong>KDC:</strong> ${book.kdc}</span>` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }
            } catch (error) {
                console.warn('관련 도서 정보를 가져오는데 실패했습니다:', error);
            }

            details.innerHTML = `
                <h2 class="subject-detail-title">${subject.label || '주제명 없음'}</h2>
                
                <div class="subject-detail-meta">
                    <div class="meta-item">
                        <strong>주제 ID:</strong> ${subject.node_id}
                    </div>
                    ${subject.relations && subject.relations.length > 0 ? `
                        <div class="meta-item">
                            <strong>관련 주제 수(최대 20개로 제한):</strong> ${subject.relations.length}개
                        </div>
                    ` : ''}
                    ${subject.definition ? `
                        <div class="meta-item">
                            <strong>설명:</strong>
                            <p>${subject.definition}</p>
                        </div>
                    ` : ''}
                </div>

                <!-- 상세 페이지로 이동 버튼 -->
                <div class="modal-actions">
                    <button class="detail-page-button" onclick="window.subjectSearchModule.goToSubjectDetailPage('${subject.node_id}')">
                        📄 상세 페이지에서 더 보기
                    </button>
                </div>
                
                ${relatedBooksHTML}

                ${subject.relations && subject.relations.length > 0 ? `
                    <div class="subject-detail-section">
                        <h3>관련 주제들 (일부)</h3>
                        <div class="relations-list">
                            ${subject.relations.slice(0, 5).map(relation => {
                const relationTypeKorean = getRelationTypeKorean(relation.relation_type);

                let metadataInfo = '';
                if (relation.metadata) {
                    try {
                        const metadata = typeof relation.metadata === 'string'
                            ? JSON.parse(relation.metadata)
                            : relation.metadata;

                        if (metadata.similarity) {
                            metadataInfo += ` <span class="metadata-info">(유사도: ${(metadata.similarity * 100).toFixed(1)}%)</span>`;
                        }
                        if (metadata.source === 'nlk') {
                            metadataInfo += ' <span class="metadata-info">(출처: NLSH)</span>';
                        }
                        if (metadata.source === 'cosine') {
                            metadataInfo += ' <span class="metadata-info">(출처: Embeddings)</span>';
                        }
                    } catch (e) {
                        // JSON 파싱 실패 시 무시
                    }
                }

                return `
                                    <div class="relation-item ${relation.relation_type}" onclick="window.subjectSearchModule.showSubjectDetails('${relation.target_id}')" title="클릭하여 상세보기">
                                        <div class="relation-header">
                                            <span class="relation-type-badge ${relation.relation_type}">${relationTypeKorean}</span>
                                            <span class="relation-target">
                                                ${relation.target_label}${metadataInfo}
                                            </span>
                                        </div>
                                        ${relation.target_id ? `
                                            <div class="relation-meta">
                                                <small>ID: ${relation.target_id}</small>
                                            </div>
                                        ` : ''}
                                    </div>
                                `;
            }).join('')}
                        </div>
                        ${subject.relations.length > 5 ? `
                            <p class="more-info">더 많은 관련 주제는 상세 페이지에서 확인하세요.</p>
                        ` : ''}
                    </div>
                ` : ''}
            `;

            modal.style.display = 'block';
        } else {
            showError(result.error, 'subject');
        }
    }

    // 주제 상세 페이지로 이동
    async goToSubjectDetailPage(nodeId) {
        // 모달 닫기
        document.getElementById('subject-modal').style.display = 'none';
        document.getElementById('subject-explore-modal').style.display = 'none';
        document.getElementById('book-modal').style.display = 'none';

        // 현재 메뉴 상태 저장 (돌아가기 기능을 위해)
        this.previousMenu = 'subject';

        // 주제 상세 페이지로 전환
        this.switchToSubjectDetailPage();

        // 상세 정보 로드
        await this.loadSubjectDetailPage(nodeId);
    }

    // 주제 상세 페이지로 전환
    switchToSubjectDetailPage() {
        // 모든 섹션 숨기기
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });

        // 주제 상세 페이지 표시
        document.getElementById('subject-detail-page').classList.add('active');

        // 사이드바 메뉴 상태 업데이트 (선택적)
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });
    }

    // 주제 상세 페이지 로드
    async loadSubjectDetailPage(nodeId) {
        const content = document.getElementById('subject-detail-content');
        const title = document.getElementById('subject-detail-page-title');

        // 로딩 표시
        content.innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <p>주제 정보를 불러오는 중...</p>
            </div>
        `;

        try {
            const result = await this.apiClient.getSubjectDetails(nodeId);

            if (result.success) {
                const subject = result.data;

                // 페이지 제목 업데이트
                title.textContent = subject.label || '주제 상세 정보';

                // KDC 접근점 정보 가져오기
                let kdcAccessPointsHTML = '';
                try {
                    const kdcResult = await this.apiClient.getKdcAccessPoints(nodeId);
                    if (kdcResult.success && kdcResult.data.access_points && kdcResult.data.access_points.length > 0) {
                        const sortedAccessPoints = kdcResult.data.access_points.sort((a, b) => {
                            const countA = a.books?.total_count || 0;
                            const countB = b.books?.total_count || 0;
                            return countB - countA; // 내림차순 정렬
                        });
                        kdcAccessPointsHTML = `
                            <div class="detail-section">
                                <h2>KDC 접근점 (${kdcResult.data.access_points.length}개)</h2>
                                <div class="kdc-access-points-grid">
                                    ${sortedAccessPoints.map(accessPoint => {
                            // KDC 번호의 첫 번째 자리 추출
                            const firstDigit = accessPoint.kdc.charAt(0);
                            const kdcColorClass = `kdc-${firstDigit}`;

                            return `
                    <div class="kdc-access-point-card ${kdcColorClass}">
                        <div class="kdc-header">
                            <span class="kdc-number">${accessPoint.kdc}</span>
                            <span class="kdc-type-badge ${accessPoint.is_direct ? 'direct' : 'indirect'}">
                                ${accessPoint.is_direct ? '직접' : '간접'}
                            </span>
                        </div>
                        <div class="kdc-label">${accessPoint.label}</div>
                        ${accessPoint.books && accessPoint.books.books && accessPoint.books.books.length > 0 ? `
                            <div class="kdc-books-preview">
                                <div class="books-count">관련 도서 ${accessPoint.books.total_count}권</div>
                                <div class="sample-books">
                                    ${accessPoint.books.books.slice(0, 2).map(book => `
                                        <div class="sample-book" onclick="window.bookSearchModule.showBookDetails('${book.isbn}')" title="클릭하여 상세보기">
                                            <div class="book-title">${truncateText(book.title, 50)}</div>
                                            <div class="book-year">${book.publication_year || '연도 미상'}</div>
                                        </div>
                                    `).join('')}
                                    ${accessPoint.books.total_count > 2 ? `
                                        <div class="more-books">외 ${accessPoint.books.total_count - 2}권</div>
                                    ` : ''}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `;
                        }).join('')}
        </div>
    </div>
                        `;
                    }
                } catch (error) {
                    console.warn('KDC 접근점 정보를 가져오는데 실패했습니다:', error);
                }

                // 관련 도서 정보 가져오기
                let relatedBooksHTML = '';
                try {
                    const booksResult = await this.apiClient.getSubjectRelatedBooks(nodeId, 20);
                    if (booksResult.success && booksResult.data.books && booksResult.data.books.length > 0) {
                        relatedBooksHTML = `
                            <div class="detail-section">
                                <h2>관련 도서 (${booksResult.data.books.length}개)</h2>
                                <div class="related-books-grid">
                                    ${booksResult.data.books.map(book => `
                                        <div class="related-book-card", onclick="window.bookSearchModule.showBookDetails('${book.isbn}')" title="클릭하여 상세보기">
                                            <h3 class="book-title">${book.title}</h3>
                                            <div class="book-meta">
                                                <span><strong>출간연도:</strong> ${book.publication_year || '정보 없음'}</span>
                                                ${book.kdc ? `<span><strong>KDC:</strong> ${book.kdc}</span>` : ''}
                                                ${book.isbn ? `<span><strong>ISBN:</strong> ${book.isbn}</span>` : ''}
                                            </div>
                                            ${book.intro ? `<div class="book-intro">${truncateText(book.intro, 150)}</div>` : ''}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `;
                    }
                } catch (error) {
                    console.warn('관련 도서 정보를 가져오는데 실패했습니다:', error);
                }

                // 상세 페이지 내용 렌더링
                content.innerHTML = `
                    <div class="subject-detail-container">
                        <!-- 주제 기본 정보 -->
                        <div class="detail-section">
                            <h2>기본 정보</h2>
                            <div class="info-grid">
                                <div class="info-item">
                                    <strong>주제명:</strong>
                                    <span>${subject.label || '정보 없음'}</span>
                                </div>
                                <div class="info-item">
                                    <strong>주제 ID:</strong>
                                    <span>${subject.node_id}</span>
                                </div>
                                ${subject.relations ? `
                                    <div class="info-item">
                                        <strong>관련 주제 수:</strong>
                                        <span>${subject.relations.length}개</span>
                                    </div>
                                ` : ''}
                            </div>
                            ${subject.definition ? `
                                <div class="subject-definition-full">
                                    <h3>정의</h3>
                                    <p>${subject.definition}</p>
                                </div>
                            ` : ''}
                        </div>

                        ${kdcAccessPointsHTML}

                        ${relatedBooksHTML}

                        ${subject.relations && subject.relations.length > 0 ? `
                            <div class="detail-section">
                                <h2>관련 주제들 (${subject.relations.length}개)</h2>
                                <div class="relations-grid">
                                    ${subject.relations.map(relation => {
                    const relationTypeKorean = getRelationTypeKorean(relation.relation_type);

                    let metadataInfo = '';
                    if (relation.metadata) {
                        try {
                            const metadata = typeof relation.metadata === 'string'
                                ? JSON.parse(relation.metadata)
                                : relation.metadata;

                            if (metadata.similarity) {
                                metadataInfo += `<div class="similarity-score">유사도: ${(metadata.similarity * 100).toFixed(1)}%</div>`;
                            }
                            if (metadata.source === 'nlk') {
                                metadataInfo += '<div class="source-info">출처: NLSH</div>';
                            }
                            if (metadata.source === 'cosine') {
                                metadataInfo += '<div class="source-info">출처: Embeddings</div>';
                            }
                            if (metadata.predicate) {
                                metadataInfo += `<div class="predicate-info">관계: ${metadata.predicate}</div>`;
                            }
                            if (metadata.description) {
                                metadataInfo += `<div class="description-info">${truncateText(metadata.description, 100)}</div>`;
                            }
                        } catch (e) {
                            // JSON 파싱 실패 시 무시
                        }
                    }

                    return `
                                            <div class="relation-card ${relation.relation_type}" onclick="window.subjectSearchModule.loadSubjectDetailPage('${relation.target_id}')" title="클릭하여 상세보기">
                                                <div class="relation-header">
                                                    <span class="relation-type-badge ${relation.relation_type}">${relationTypeKorean}</span>
                                                </div>
                                                <div class="relation-content">
                                                    <h4 class="relation-target">${relation.target_label}</h4>
                                                    ${relation.target_id ? `<div class="relation-id">ID: ${relation.target_id}</div>` : ''}
                                                    ${metadataInfo}
                                                </div>
                                            </div>
                                        `;
                }).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `;
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            content.innerHTML = `
                <div class="error-container">
                    <h2>❌ 오류가 발생했습니다</h2>
                    <p>${error.message}</p>
                    <button onclick="window.subjectSearchModule.goBackFromSubjectDetail()" class="back-button">
                        돌아가기
                    </button>
                </div>
            `;
        }
    }

    // 주제 상세 페이지에서 돌아가기
    goBackFromSubjectDetail() {
        // 주제 상세 페이지 숨기기
        document.getElementById('subject-detail-page').classList.remove('active');

        // 이전 메뉴로 돌아가기 (기본값: 주제 검색)
        const previousMenu = this.previousMenu || 'subject';

        // 모든 섹션 숨기기
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });

        // 이전 섹션 표시
        document.getElementById(`${previousMenu}-section`).classList.add('active');

        // 사이드바 메뉴 상태 업데이트
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });

        const targetMenuItem = document.querySelector(`[data-menu-type="${previousMenu}"]`);
        if (targetMenuItem) {
            targetMenuItem.classList.add('active');
        }
    }

    // 탭 전환 시 검색 결과 초기화
    clearSearchResults() {
        clearResults('subject');
        this.currentSearch = null;
        this.currentPage = 1;
        this.totalPages = 1;
    }
}
