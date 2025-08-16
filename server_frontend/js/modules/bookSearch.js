import { ApiClient } from '../core/api.js';
import { showLoading, clearResults, showError, truncateText, escapeHtml, getRelationTypeKorean} from '../core/utils.js';

/**
 * BookSearchModule
 * - Handles book searching, displaying results, pagination, and book details.
 * - Supports general, advanced, and vector-based search.
 * - Integrates with subject search and book detail page.
 */
export class BookSearchModule {
    constructor() {
        this.apiClient = new ApiClient();
        this.currentSearch = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.init();
    }

    /**
     * Initialize module (bind events)
     */
    init() {
        this.bindEvents();
    }

    /**
     * Bind search input events (Enter key for search)
     */
    bindEvents() {
        // General search input
        const generalQuery = document.getElementById('general-query');
        if (generalQuery) {
            generalQuery.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.performGeneralSearch();
            });
        }

        // Advanced search fields (title, isbn, vector)
        ['title-search', 'isbn-search', 'vector-query'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        if (id === 'vector-query') {
                            this.performVectorSearch();
                        } else {
                            this.performAdvancedSearch();
                        }
                    }
                });
            }
        });
    }

    /**
     * Perform general search (by keyword)
     */
    async performGeneralSearch() {
        const query = document.getElementById('general-query').value.trim();
        if (!query) {
            alert('검색어를 입력해주세요.');
            return;
        }

        this.currentSearch = { type: 'general', query: query };
        this.currentPage = 1;
        await this.searchBooks();
    }

    /**
     * Perform advanced search (by title and/or ISBN)
     */
    async performAdvancedSearch() {
        const title = document.getElementById('title-search').value.trim();
        const isbn = document.getElementById('isbn-search').value.trim();

        if (!title && !isbn) {
            alert('최소 하나의 검색 조건을 입력해주세요.');
            return;
        }

        this.currentSearch = { type: 'advanced', title, isbn };
        this.currentPage = 1;
        await this.searchBooks();
    }

    /**
     * Perform vector-based search
     */
    async performVectorSearch() {
        const query = document.getElementById('vector-query').value.trim();
        const limit = document.getElementById('vector-limit').value;

        if (!query) {
            alert('검색어를 입력해주세요.');
            return;
        }

        this.currentSearch = { type: 'vector', query, limit: parseInt(limit) };
        this.currentPage = 1;
        await this.searchBooks();
    }

    /**
     * Execute book search using currentSearch parameters
     */
    async searchBooks() {
        if (!this.currentSearch) return;

        showLoading(true, 'book');
        clearResults('book');

        const params = {
            ...this.currentSearch,
            page: this.currentPage,
            perPage: 20
        };

        const result = await this.apiClient.searchBooks(params);

        if (result.success) {
            this.displayResults(result.data);
            this.updatePagination(result.data);
        } else {
            showError(result.error, 'book');
        }

        showLoading(false, 'book');
    }

    /**
     * Display search results in the UI
     * @param {Object} data - Search result data
     */
    displayResults(data) {
        const container = document.getElementById('results-book-container');
        const searchInfo = document.getElementById('search-book-info');

        // Show search info
        if (data.total_count === 0) {
            searchInfo.innerHTML = `<strong>검색 결과:</strong> 총 0권의 도서가 검색되었습니다.`;
        } else {
            searchInfo.innerHTML = `
                <strong>검색 결과:</strong> 총 ${data.total_count.toLocaleString()}권의 도서가 검색되었습니다. 
                (${data.page}/${data.total_pages} 페이지)
            `;
        }

        // No results
        if (data.results.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <h3>검색 결과가 없습니다</h3>
                    <p>다른 검색어로 시도해보세요.</p>
                </div>
            `;
            return;
        }

        // Render book list
        container.innerHTML = data.results.map(book => `
            <div class="book-item" onclick="window.bookSearchModule.showBookDetails('${book.isbn}')">
                <div class="book-title">${book.title || '제목 없음'}</div>
                <div class="book-meta">
                    <span><strong>ISBN:</strong> ${book.isbn}</span>
                </div>
                ${book.intro ? `<div class="book-intro">${truncateText(book.intro, 200)}</div>` : ''}
            </div>
        `).join('');

        this.totalPages = data.total_pages;
    }

    /**
     * Update pagination controls
     * @param {Object} data - Search result data
     */
    updatePagination(data) {
        const pagination = document.getElementById('pagination-book');
        const totalPages = data.total_pages;
        const currentPage = data.page;

        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let paginationHTML = '';

        // Previous page button
        paginationHTML += `
            <button onclick="window.bookSearchModule.goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                ← 이전
            </button>
        `;

        // Page number buttons
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        if (startPage > 1) {
            paginationHTML += `<button onclick="window.bookSearchModule.goToPage(1)">1</button>`;
            if (startPage > 2) {
                paginationHTML += `<span>...</span>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <button onclick="window.bookSearchModule.goToPage(${i})" class="${i === currentPage ? 'active' : ''}">
                    ${i}
                </button>
            `;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += `<span>...</span>`;
            }
            paginationHTML += `<button onclick="window.bookSearchModule.goToPage(${totalPages})">${totalPages}</button>`;
        }

        // Next page button
        paginationHTML += `
            <button onclick="window.bookSearchModule.goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                다음 →
            </button>
        `;

        pagination.innerHTML = paginationHTML;
    }

    /**
     * Go to a specific page in pagination
     * @param {number} page - Target page number
     */
    async goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        await this.searchBooks();
    }

    /**
     * Show book details in modal
     * @param {string} isbn - Book ISBN
     */
    async showBookDetails(isbn) {
        const result = await this.apiClient.getBookDetails(isbn);

        if (result.success) {
            const book = result.data;
            const modal = document.getElementById('book-modal');
            const details = document.getElementById('book-details');

            // Render book details modal
            details.innerHTML = `
                <h2 class="book-detail-title">${book.title || '제목 없음'}</h2>
                
                <div class="book-detail-meta">
                    <div class="meta-item">
                        <strong>ISBN:</strong> ${book.isbn}
                    </div>
                    ${book.kdc ? `
                        <div class="meta-item">
                            <strong>분류번호:</strong> ${book.kdc}
                        </div>
                    ` : ''}
                    ${book.publication_year ? `
                        <div class="meta-item">
                            <strong>출간년도:</strong> ${book.publication_year}년
                        </div>
                    ` : ''}
                </div>

                <!-- Button to go to detail page -->
                <div class="modal-actions">
                    <button class="detail-page-button" onclick="window.bookSearchModule.goToBookDetailPage('${book.isbn}')">
                        📖 상세 페이지에서 더 보기
                    </button>
                </div>

                ${book.nlk_subjects ? `
                    <div class="book-detail-section">
                        <h3>주제 분류</h3>
                        <div class="nlk-subjects-list">
                            ${this.formatNlkSubjects(book.nlk_subjects)}
                        </div>
                    </div>
                ` : ''}
                
                ${book.intro ? `
                    <div class="book-detail-section">
                        <h3>소개</h3>
                        <p>${truncateText(book.intro, 200)}</p>
                        ${book.intro.length > 200 ? '<p class="more-info">전체 내용은 상세 페이지에서 확인하세요.</p>' : ''}
                    </div>
                ` : ''}
                
                ${book.toc ? `
                    <div class="book-detail-section">
                        <h3>목차</h3>
                        <p>${truncateText(book.toc, 200)}</p>
                        ${book.toc.length > 200 ? '<p class="more-info">전체 목차는 상세 페이지에서 확인하세요.</p>' : ''}
                    </div>
                ` : ''}
            `;

            modal.style.display = 'block';
        } else {
            showError(result.error, 'book');
        }
    }

    /**
     * Format NLK subjects for modal display
     * @param {Array|string} subjects - NLK subjects data
     * @returns {string} HTML
     */
    formatNlkSubjects(subjects) {
        try {
            // Parse if string
            const subjectsData = typeof subjects === 'string' ? JSON.parse(subjects) : subjects;
            if (!Array.isArray(subjectsData)) {
                return `<p>${subjects}</p>`;
            }
            if (subjectsData.length === 0) {
                return '';
            }
            // Render clickable subject items
            return subjectsData.map(subject => {
                const label = subject.label || '주제명 없음';
                const type = subject.type || '';
                const id = subject.id || '';

                // Escape HTML
                const safeId = escapeHtml(id);
                const safeLabel = escapeHtml(label);
                const safeType = escapeHtml(type);

                return `
                    <div class="nlk-subject-item clickable-subject" onclick="window.openSubjectModal('${safeId}', '${safeLabel}')" title="클릭하여 주제 상세보기">
                    ${safeType ? `<span class="subject-type">[${safeType.toUpperCase()}]</span>` : ''}    
                    <span class="subject-label">${safeLabel}</span>
                    ${safeId ? `<span class="subject-id">${safeId}</span>` : ''}
                    </div>
                `;
            }).join('');

        } catch (error) {
            // Fallback on parse error
            console.warn('NLK subjects 파싱 실패:', error);
            return `<p>${subjects}</p>`;
        }
    }

    /**
     * Open subject modal (delegates to subjectSearchModule if available)
     * @param {string} subjectId 
     * @param {string} subjectLabel 
     */
    async openSubjectModal(subjectId, subjectLabel) {
        try {
            // Use subjectSearchModule if available
            if (window.subjectSearchModule && typeof window.subjectSearchModule.showSubjectDetails === 'function') {
                await window.subjectSearchModule.showSubjectDetails(subjectId);
            } else {
                console.error('주제 검색 모듈을 찾을 수 없습니다');
                // Fallback: show basic subject modal
                this.showSubjectExploreModal({
                    node_id: subjectId,
                    label: subjectLabel,
                    relations: [],
                    definition: null
                });
            }
        } catch (error) {
            console.error('주제 정보 로드 실패:', error);
            // Fallback on error
            this.showSubjectExploreModal({
                node_id: subjectId,
                label: subjectLabel,
                relations: [],
                definition: null
            });
        }
    }

    /**
     * Show subject explore modal (basic subject info)
     * @param {Object} subject 
     */
    showSubjectExploreModal(subject) {
        const modal = document.getElementById('subject-explore-modal');
        const content = document.getElementById('subject-explore-content');
        content.innerHTML = `
            <div class="subject-explore-header">
                <h2 class="subject-explore-title">${escapeHtml(subject.label) || '주제명 없음'}</h2>
                <span class="subject-id-badge">${escapeHtml(subject.node_id)}</span>
            </div>
            
            ${subject.definition ? `
                <div class="subject-detail-section">
                    <h3>정의</h3>
                    <p>${escapeHtml(subject.definition)}</p>
                </div>
            ` : ''}
            
            ${subject.relations && subject.relations.length > 0 ? `
                <div class="subject-detail-section">
                    <h3>관련 주제들</h3>
                    <div class="relations-list">
                        ${subject.relations.map(relation => {
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
                                } catch (e) {
                                    // Ignore parse error
                                }
                            }

                            return `
                                <div class="relation-item ${relation.relation_type}" onclick="window.openSubjectModal('${escapeHtml(relation.target_id)}', '${escapeHtml(relation.target_label)}')" title="클릭하여 상세보기">
                                    <div class="relation-header">
                                        <span class="relation-type-badge ${relation.relation_type}">${relationTypeKorean}</span>
                                        <span class="relation-target">
                                            ${escapeHtml(relation.target_label)}${metadataInfo}
                                        </span>
                                    </div>
                                    ${relation.target_id ? `
                                        <div class="relation-meta">
                                            <small>ID: ${escapeHtml(relation.target_id)}</small>
                                        </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            ` : `
                <div class="subject-detail-section">
                    <p>관련 주제 정보가 없습니다.</p>
                </div>
            `}
            
            <div class="modal-actions">
                <button onclick="window.bookSearchModule.searchRelatedBooks('${escapeHtml(subject.node_id)}', '${escapeHtml(subject.label)}')" class="btn-primary">
                    관련 도서 검색
                </button>
            </div>
        `;
        
        modal.style.display = 'block';
    }

    /**
     * Search books related to a subject (by subject label)
     * @param {string} subjectId 
     * @param {string} subjectLabel 
     */
    async searchRelatedBooks(subjectId, subjectLabel) {
        // Close subject explore modal
        document.getElementById('subject-explore-modal').style.display = 'none';
        
        // Close subject modal (if exists)
        const subjectModal = document.getElementById('subject-modal');
        if (subjectModal) {
            subjectModal.style.display = 'none';
        }
        
        // Close book modal
        document.getElementById('book-modal').style.display = 'none';
        
        // Search books by subject label
        document.getElementById('general-query').value = subjectLabel;
        await this.performGeneralSearch();
    }

    /**
     * Go to book detail page (switch UI and load details)
     * @param {string} isbn 
     */
    async goToBookDetailPage(isbn) {
        // Close all modals
        document.getElementById('subject-modal').style.display = 'none';
        document.getElementById('subject-explore-modal').style.display = 'none';
        document.getElementById('book-modal').style.display = 'none';
        
        // Save previous menu for back navigation
        this.previousMenu = 'book';
        
        // Switch to book detail page
        this.switchToBookDetailPage();
        
        // Load book details
        await this.loadBookDetailPage(isbn);
    }

    /**
     * Switch UI to book detail page
     */
    switchToBookDetailPage() {
        // Hide all content sections
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        // Show book detail page
        document.getElementById('book-detail-page').classList.add('active');
        
        // Update sidebar menu state (optional)
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });
    }

    /**
     * Load book detail page content
     * @param {string} isbn 
     */
    async loadBookDetailPage(isbn) {
        const content = document.getElementById('book-detail-content');
        const title = document.getElementById('book-detail-page-title');
        
        // Show loading spinner
        content.innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <p>도서 정보를 불러오는 중...</p>
            </div>
        `;
        
        try {
            const result = await this.apiClient.getBookDetails(isbn);
            
            if (result.success) {
                const book = result.data;
                
                // Update page title
                title.textContent = book.title || '도서 상세 정보';
                
                // Render book detail content
                content.innerHTML = `
                    <div class="book-detail-container">
                        <!-- Basic book info -->
                        <div class="detail-section">
                            <h2>기본 정보</h2>
                            <div class="info-grid">
                                <div class="info-item">
                                    <strong>제목:</strong>
                                    <span>${book.title || '정보 없음'}</span>
                                </div>
                                <div class="info-item">
                                    <strong>ISBN:</strong>
                                    <span>${book.isbn}</span>
                                </div>
                                ${book.kdc ? `
                                    <div class="info-item">
                                        <strong>분류번호(KDC):</strong>
                                        <span>${book.kdc}</span>
                                    </div>
                                ` : ''}
                                ${book.publication_year ? `
                                    <div class="info-item">
                                        <strong>출간년도:</strong>
                                        <span>${book.publication_year}년</span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>

                        ${book.nlk_subjects ? `
                            <div class="detail-section">
                                <h2>주제 분류</h2>
                                <div class="nlk-subjects-detailed">
                                    ${this.formatNlkSubjectsDetailed(book.nlk_subjects)}
                                </div>
                            </div>
                        ` : ''}
                        
                        ${book.intro ? `
                            <div class="detail-section">
                                <h2>소개</h2>
                                <div class="book-content">
                                    <p>${book.intro.replace(/\n/g, '<br>')}</p>
                                </div>
                            </div>
                        ` : ''}
                        
                        ${book.toc ? `
                            <div class="detail-section">
                                <h2>목차</h2>
                                <div class="book-content">
                                    <pre>${book.toc}</pre>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `;
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            // Show error and back button
            content.innerHTML = `
                <div class="error-container">
                    <h2>❌ 오류가 발생했습니다</h2>
                    <p>${error.message}</p>
                    <button onclick="window.bookSearchModule.goBackFromBookDetail()" class="back-button">
                        돌아가기
                    </button>
                </div>
            `;
        }
    }
    
    /**
     * Format NLK subjects for detail page
     * @param {Array|string} nlkSubjects 
     * @returns {string} HTML
     */
    formatNlkSubjectsDetailed(nlkSubjects) {
        try {
            let subjectsData;
            
            // Parse if string
            if (typeof nlkSubjects === 'string') {
                subjectsData = JSON.parse(nlkSubjects);
            } else {
                subjectsData = nlkSubjects;
            }
            
            if (!Array.isArray(subjectsData)) {
                console.warn('주제 데이터가 배열이 아닙니다:', subjectsData);
                return '<div class="no-subjects">주제 분류 정보가 없습니다.</div>';
            }
            if (subjectsData.length === 0) {
                return '<div class="no-subjects">주제 분류 정보가 없습니다.</div>';
            }
            
            // Render subject cards
            return subjectsData.map(subject => {
                const label = subject.label || '주제명 없음';
                const id = subject.id || '';
                const type = subject.type || '';
                
                // Escape HTML
                const safeId = escapeHtml(id);
                const safeLabel = escapeHtml(label);
                const safeType = escapeHtml(type);
                
                return `
                    <div class="nlk-subject-detailed" onclick="window.openSubjectModal('${safeId}', '${safeLabel}')" title="클릭하여 주제 상세보기">
                        <div class="subject-id">${safeId}</div>
                        <div class="subject-label">${safeLabel}</div>
                        ${safeType ? `<div class="subject-type">${safeType.toUpperCase()}</div>` : ''}
                    </div>
                `;
            }).join('');
            
        } catch (error) {
            console.error('NLK subjects 파싱 오류:', error);
            console.error('원본 데이터:', nlkSubjects);
            return '<div class="parse-error">주제 정보를 표시할 수 없습니다.</div>';
        }
    }

    /**
     * Go back from book detail page to previous menu
     */
    goBackFromBookDetail() {
        // Hide book detail page
        document.getElementById('book-detail-page').classList.remove('active');
        
        // Restore previous menu section (default: book)
        const previousMenu = this.previousMenu || 'book';
        
        // Hide all sections
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        // Show previous section
        document.getElementById(`${previousMenu}-section`).classList.add('active');
        
        // Update sidebar menu state
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });
        
        const targetMenuItem = document.querySelector(`[data-menu-type="${previousMenu}"]`);
        if (targetMenuItem) {
            targetMenuItem.classList.add('active');
        }
    }

    /**
     * Clear search results and reset state (on tab switch)
     */
    clearSearchResults() {
        clearResults('book');
        this.currentSearch = null;
        this.currentPage = 1;
        this.totalPages = 1;
    }
}
