import { ApiClient } from '../core/api.js';
import { NETWORK_CONFIG } from '../core/config.js';
import { showError, getRelationTypeKorean } from '../core/utils.js';
import {} from './subjectSearch.js'

export class NetworkModule {
    constructor() {
        this.apiClient = new ApiClient();
        this.networkData = { nodes: [], edges: [] };
        this.simulation = null;
        this.svg = null;
        this.g = null;
        this.expandedNodes = new Set();
        this.isInitialized = false;
        this.maxExpansionNodes = 5; // 기본값
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeVisualization();
        this.restoreNetworkState();
    }

    bindEvents() {
        // 씨앗 노드 검색 엔터 키 지원
        const seedQuery = document.getElementById('seed-query');
        if (seedQuery) {
            seedQuery.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.searchSeedNode();
            });
        }

        // 최대 확장 노드 수 설정 변경 이벤트
        const maxExpansionSelect = document.getElementById('max-expansion-nodes');
        if (maxExpansionSelect) {
            maxExpansionSelect.addEventListener('change', (e) => {
                this.maxExpansionNodes = parseInt(e.target.value);
                console.log('최대 확장 노드 수 변경:', this.maxExpansionNodes);
            });
            // 초기값 설정
            this.maxExpansionNodes = parseInt(maxExpansionSelect.value);
        }

        // 윈도우 리사이즈 이벤트
        window.addEventListener('resize', () => {
            if (this.svg) {
                const container = document.getElementById('network-visualization');
                const containerParent = container.parentElement;
                const width = containerParent.clientWidth || NETWORK_CONFIG.width;
                const height = containerParent.clientHeight || NETWORK_CONFIG.height;

                this.svg.attr('width', width).attr('height', height);
                this.simulation.force('center', d3.forceCenter(width / 2, height / 2));
                this.simulation.restart();
            }
        });
    }

    // 네트워크 시각화 초기화
    initializeVisualization() {
        const container = document.getElementById('network-visualization');
        const containerParent = container.parentElement;

        const width = containerParent.clientWidth || NETWORK_CONFIG.width;
        const height = containerParent.clientHeight || NETWORK_CONFIG.height;

        console.log('Network visualization init:', { width, height, containerParent });

        this.svg = d3.select('#network-visualization')
            .append('svg')
            .attr('width', width)
            .attr('height', height);

        // 줌 기능 추가
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(zoom);

        // 그래프 요소들을 담을 그룹
        this.g = this.svg.append('g');

        // 화살표 마커 정의
        this.svg.append('defs').selectAll('marker')
            .data(['end'])
            .enter().append('marker')
            .attr('id', String)
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#999');

        // 포스 시뮬레이션 초기화
        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.node_id).distance(NETWORK_CONFIG.linkDistance))
            .force('charge', d3.forceManyBody().strength(NETWORK_CONFIG.chargeStrength))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(NETWORK_CONFIG.collisionRadius));

        this.updateNetworkStats();
    }


    // 네트워크 상태 저장
    saveNetworkState() {
        try {
            const state = {
                networkData: this.networkData,
                expandedNodes: Array.from(this.expandedNodes),
                maxExpansionNodes: this.maxExpansionNodes,
                timestamp: Date.now()
            };
            sessionStorage.setItem('networkState', JSON.stringify(state));
        } catch (error) {
            console.warn('네트워크 상태 저장 실패:', error);
        }
    }

    // 네트워크 상태 복원
    restoreNetworkState() {
        try {
            const savedState = sessionStorage.getItem('networkState');
            if (savedState) {
                const state = JSON.parse(savedState);
                
                // 1시간 이내 저장된 상태만 복원 (선택적)
                const oneHour = 60 * 60 * 1000;
                if (Date.now() - state.timestamp < oneHour) {
                    this.networkData = state.networkData;
                    this.expandedNodes = new Set(state.expandedNodes);
                    
                    // 최대 확장 노드 수 복원
                    if (state.maxExpansionNodes) {
                        this.maxExpansionNodes = state.maxExpansionNodes;
                        const maxExpansionSelect = document.getElementById('max-expansion-nodes');
                        if (maxExpansionSelect) {
                            maxExpansionSelect.value = state.maxExpansionNodes.toString();
                        }
                    }
                    
                    if (this.networkData.nodes.length > 0) {
                        this.updateNetworkVisualization();
                        this.updateNetworkStats();
                        this.isInitialized = true;
                    }
                } else {
                    // 오래된 상태는 삭제
                    sessionStorage.removeItem('networkState');
                }
            }
        } catch (error) {
            console.warn('네트워크 상태 복원 실패:', error);
            sessionStorage.removeItem('networkState');
        }
    }

    // 네트워크 상태 초기화
    clearNetworkState() {
        sessionStorage.removeItem('networkState');
    }

    // 씨앗 노드 검색
    async searchSeedNode() {
        const query = document.getElementById('seed-query').value.trim();
        if (!query) return;

        const result = await this.apiClient.searchSeedNode(query);
        
        if (result.success) {
            this.displaySeedCandidates(result.data.candidates);
        } else {
            showError(result.error, 'network');
        }
    }

    // 씨앗 후보들 표시
    displaySeedCandidates(candidates) {
        const container = document.getElementById('seed-candidates');

        if (candidates.length === 0) {
            container.innerHTML = '<p>검색 결과가 없습니다.</p>';
            return;
        }

        container.innerHTML = candidates.map(candidate => `
            <div class="seed-candidate" onclick="window.networkModule.selectSeedNode('${candidate.node_id}')">
                <div class="seed-candidate-label">${candidate.label}</div>
                <div class="seed-candidate-definition">${candidate.definition}</div>
            </div>
        `).join('');
    }

    // 씨앗 노드 선택
    async selectSeedNode(nodeId) {
        // 기존 네트워크 초기화
        this.networkData = { nodes: [], edges: [] };
        this.expandedNodes.clear();
        this.expandedNodes.add(nodeId);

        // 씨앗 후보 목록 숨기기
        document.getElementById('seed-candidates').innerHTML = '';

        // 씨앗 노드와 연결된 노드들 가져오기
        await this.expandNode(nodeId);

        // 상태 저장
        this.saveNetworkState();
    }

    // 노드 확장 (연결된 노드들 추가)
    async expandNode(nodeId) {
        // 로딩 표시
        if (!this.networkData.nodes.length) {
            this.showNetworkLoading(true, '네트워크 구성 중...');
        } else {
            this.showNetworkLoading(true, '노드 확장 중...');
        }

        const result = await this.apiClient.getNodeNeighbors(nodeId, this.maxExpansionNodes);

        if (result.success) {
            const data = result.data;

            // 기존 노드와 중복 제거하며 새 노드들 추가
            data.nodes.forEach(node => {
                if (!this.networkData.nodes.find(n => n.node_id === node.node_id)) {
                    this.networkData.nodes.push(node);
                }
            });

            // 기존 연결과 중복 제거하며 새 연결들 추가
            data.edges.forEach(edge => {
                if (!this.networkData.edges.find(e =>
                    (e.source === edge.source && e.target === edge.target) ||
                    (e.source === edge.target && e.target === edge.source)
                )) {
                    this.networkData.edges.push(edge);
                }
            });

            this.updateNetworkVisualization();
            this.updateNetworkStats();

            // 상태 저장
            this.saveNetworkState();

        } else {
            showError(result.error, 'network');
        }

        this.showNetworkLoading(false);
    }

    // 네트워크 로딩 표시
    showNetworkLoading(show, message = '로딩 중...') {
        const container = document.getElementById('network-visualization');

        if (show) {
            const existingSvg = container.querySelector('svg');
            if (existingSvg) {
                existingSvg.style.opacity = '0.3';
            }

            let loadingOverlay = container.querySelector('.network-loading-overlay');
            if (!loadingOverlay) {
                loadingOverlay = document.createElement('div');
                loadingOverlay.className = 'network-loading-overlay';
                container.appendChild(loadingOverlay);
            }

            loadingOverlay.innerHTML = `
                <div class="network-loading-content">
                    <div class="loading-spinner"></div>
                    <span class="loading-text">${message}</span>
                </div>
            `;
            loadingOverlay.style.display = 'flex';
        } else {
            const existingSvg = container.querySelector('svg');
            if (existingSvg) {
                existingSvg.style.opacity = '1';
            }
            
            const loadingOverlay = container.querySelector('.network-loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
                loadingOverlay.innerHTML = '';
            }
        }
    }

    // 네트워크 시각화 업데이트
    updateNetworkVisualization() {
        // 기존 요소들 제거
        this.g.selectAll('*').remove();

        // 연결선 그리기
        const link = this.g.selectAll('.link')
            .data(this.networkData.edges)
            .enter().append('line')
            .attr('class', d => `link ${d.relation_type}`)
            .attr('marker-end', 'url(#end)')
            .on('mouseover', (event, d) => {
                this.showLinkTooltip(event, d);
            })
            .on('mouseout', () => {
                this.hideTooltip();
            });

        // 연결 라벨
        const linkLabel = this.g.selectAll('.link-label')
            .data(this.networkData.edges)
            .enter().append('text')
            .attr('class', 'link-label')
            .text(d => getRelationTypeKorean(d.relation_type));

        // 노드 그리기 (주제 노드는 원형, 도서 노드는 사각형)
        const nodeGroup = this.g.selectAll('.node-group')
            .data(this.networkData.nodes)
            .enter().append('g')
            .attr('class', 'node-group');

        // 주제 노드 (원형)
        const subjectNodes = nodeGroup.filter(d => d.node_type !== 'book')
            .append('circle')
            .attr('class', d => {
                let classes = 'node subject-node';
                if (d.type === 'current') classes += ' current';
                else if (this.expandedNodes.has(d.node_id)) classes += ' expanded';
                else classes += ' neighbor';
                return classes;
            })
            .attr('r', NETWORK_CONFIG.nodeRadius);

        // 도서 노드 (사각형)
        const bookNodes = nodeGroup.filter(d => d.node_type === 'book')
            .append('rect')
            .attr('class', d => {
                let classes = 'node book-node';
                if (d.type === 'current') classes += ' current';
                else if (this.expandedNodes.has(d.node_id)) classes += ' expanded';
                else classes += ' neighbor';
                return classes;
            })
            .attr('width', NETWORK_CONFIG.nodeRadius * 2)
            .attr('height', NETWORK_CONFIG.nodeRadius * 1.5)
            .attr('x', -NETWORK_CONFIG.nodeRadius)
            .attr('y', -NETWORK_CONFIG.nodeRadius * 0.75);

        // 모든 노드에 공통 이벤트 적용
        const allNodes = nodeGroup.selectAll('.node')
            .on('click', (event, d) => {
                event.stopPropagation();
                this.showNodeContextMenu(event, d);
            })
            .on('mouseover', (event, d) => {
                this.showTooltip(event, d);
            })
            .on('mouseout', () => {
                this.hideTooltip();
            });

        const node = allNodes;

        // 노드 라벨
        const nodeLabel = this.g.selectAll('.node-label')
            .data(this.networkData.nodes)
            .enter().append('text')
            .attr('class', 'node-label')
            .text(d => d.label.length > 15 ? d.label.substring(0, 15) + '...' : d.label)
            .attr('dy', -20);

        // 드래그 기능 추가
        node.call(d3.drag()
            .on('start', (event, d) => this.dragstarted(event, d))
            .on('drag', (event, d) => this.dragged(event, d))
            .on('end', (event, d) => this.dragended(event, d)));

        // 시뮬레이션 업데이트
        this.simulation.nodes(this.networkData.nodes);
        this.simulation.force('link').links(this.networkData.edges);

        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            linkLabel
                .attr('x', d => (d.source.x + d.target.x) / 2)
                .attr('y', d => (d.source.y + d.target.y) / 2);

            // 노드 그룹 위치 업데이트
            nodeGroup
                .attr('transform', d => `translate(${d.x},${d.y})`);

            nodeLabel
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        });

        this.simulation.restart();
    }

    // 툴팁 표시
    showTooltip(event, d) {
        const tooltip = document.getElementById('network-tooltip');
        let content = `<strong>${d.label}</strong>`;
        if (d.definition) {
            content += `<br><br>${d.definition}`;
        }
        
        const [x, y] = d3.pointer(event);
        tooltip.innerHTML = content;
        tooltip.className = 'network-tooltip visible';
        tooltip.style.top = y + 'px';
        tooltip.style.left = x + 'px';
    }

    // 연결선 툴팁 표시
    showLinkTooltip(event, d) {
        const tooltip = document.getElementById('network-tooltip');

        let content = `<strong>연결 유형:</strong> ${getRelationTypeKorean(d.relation_type)}`;

        if (d.metadata) {
            try {
                const metadata = typeof d.metadata === 'string' ? JSON.parse(d.metadata) : d.metadata;
                if (metadata.similarity) {
                    content += `<br><strong>유사도:</strong> ${(metadata.similarity * 100).toFixed(2)}%`;
                }
                if (metadata.predicate) {
                    content += `<br><strong>관계:</strong> ${metadata.predicate}`;
                }
                if (metadata.description) {
                    content += `<br><strong>설명:</strong> ${metadata.description}`;
                } 

            } catch (e) {
                // JSON 파싱 실패 시 무시
            }
        }
        
        const [x, y] = d3.pointer(event);
        tooltip.innerHTML = content;
        tooltip.className = 'network-tooltip visible';
        tooltip.style.top = (y + 10) + 'px';
        tooltip.style.left = (x + 15) + 'px';
    }

    // 툴팁 숨기기
    hideTooltip() {
        const tooltip = document.getElementById('network-tooltip');
        tooltip.className = 'network-tooltip';
    }

    // 노드 컨텍스트 메뉴 표시
    showNodeContextMenu(event, d) {
        this.hideNodeContextMenu(); // 기존 메뉴 숨기기

        const contextMenu = document.createElement('div');
        contextMenu.className = 'node-context-menu';
        contextMenu.id = 'node-context-menu';

        const menuItems = [];

        // 노드 타입에 따른 메뉴 구성
        if (d.node_type !== 'book') {
            // 주제 노드인 경우
            menuItems.push({
                text: '주제 세부 정보',
                icon: 'ℹ️',
                action: () => this.showSubjectDetailsFromNetwork(d.node_id)
            });
            
            if (!this.expandedNodes.has(d.node_id)) {
                menuItems.push({
                    text: '노드 확장',
                    icon: '🔍',
                    action: () => this.expandNodeFromMenu(d.node_id)
                });
            }
            menuItems.push({
                text: '관련 도서 보기',
                icon: '📚',
                action: () => this.showRelatedBooks(d.node_id)
            });
        } else {
            // 도서 노드인 경우
            menuItems.push({
                text: '도서 세부 정보',
                icon: 'ℹ️',
                action: () => this.showBookDetailsFromNetwork(d.node_id)
            });
        }

        menuItems.push({
            text: '노드 삭제',
            icon: '🗑️',
            action: () => this.removeNode(d.node_id)
        });

        contextMenu.innerHTML = menuItems.map((item, index) => `
            <div class="context-menu-item" data-action="${index}">
                <span class="menu-icon">${item.icon}</span>
                <span class="menu-text">${item.text}</span>
            </div>
        `).join('');

        // 메뉴 아이템 클릭 이벤트 추가
        contextMenu.addEventListener('click', (e) => {
            e.stopPropagation();
            const actionIndex = e.target.closest('.context-menu-item')?.dataset.action;
            if (actionIndex !== undefined && menuItems[actionIndex]) {
                menuItems[actionIndex].action();
                this.hideNodeContextMenu();
            }
        });

        // 메뉴 위치 설정
        const rect = event.target.getBoundingClientRect();
        const svgRect = this.svg.node().getBoundingClientRect();
        
        contextMenu.style.position = 'absolute';
        contextMenu.style.left = (event.clientX - svgRect.left + 10) + 'px';
        contextMenu.style.top = (event.clientY - svgRect.top + 10) + 'px';
        contextMenu.style.zIndex = '1000';

        // SVG 컨테이너에 추가
        const container = document.getElementById('network-visualization');
        container.appendChild(contextMenu);

        // 외부 클릭 시 메뉴 숨기기
        setTimeout(() => {
            document.addEventListener('click', this.hideNodeContextMenu.bind(this), { once: true });
        }, 0);
    }

    // 노드 컨텍스트 메뉴 숨기기
    hideNodeContextMenu() {
        const contextMenu = document.getElementById('node-context-menu');
        if (contextMenu) {
            contextMenu.remove();
        }
    }

    // 메뉴에서 노드 확장
    async expandNodeFromMenu(nodeId) {
        if (!this.expandedNodes.has(nodeId)) {
            this.expandedNodes.add(nodeId);
            // 노드 스타일 업데이트
            this.g.selectAll('.node-group')
                .filter(d => d.node_id === nodeId)
                .select('.node')
                .attr('class', d => {
                    let classes = d.node_type === 'book' ? 'node book-node expanded' : 'node subject-node expanded';
                    return classes;
                });
            await this.expandNode(nodeId);
            
            // 상태 저장
            this.saveNetworkState();
        }
    }

    // 네트워크에서 주제 세부 정보 표시
    async showSubjectDetailsFromNetwork(nodeId) {
        // 주제 검색 모듈의 showSubjectDetails 함수 사용
        if (window.subjectSearchModule && typeof window.subjectSearchModule.showSubjectDetails === 'function') {
            await window.subjectSearchModule.showSubjectDetails(nodeId);
        } else {
            showError('주제 검색 모듈을 찾을 수 없습니다.', 'network');
        }
    }

    // 네트워크에서 도서 세부 정보 표시
    async showBookDetailsFromNetwork(nodeId) {
        // 도서 검색 모듈의 showBookDetails 함수 사용
        if (window.bookSearchModule && typeof window.bookSearchModule.showBookDetails === 'function') {
            await window.bookSearchModule.showBookDetails(nodeId);
        } else {
            showError('도서 검색 모듈을 찾을 수 없습니다.', 'network');
        }
    }

    // 관련 도서 표시
    async showRelatedBooks(nodeId) {
        this.showNetworkLoading(true, '관련 도서 검색 중...');

        try {
            const result = await this.apiClient.getSubjectRelatedBooks(nodeId, this.maxExpansionNodes);
            
            if (result.success && result.data.books) {
                // 도서 노드들을 네트워크에 추가
                result.data.books.forEach(book => {
                    // 이미 존재하는 노드인지 확인
                    if (!this.networkData.nodes.find(n => n.node_id === book.isbn)) {
                        const bookNode = {
                            node_id: book.isbn,
                            label: book.title,
                            definition: `${book.intro || ''}`,
                            node_type: 'book',
                            type: 'neighbor'
                        };
                        this.networkData.nodes.push(bookNode);

                        // 주제 노드와 도서 노드 간의 연결 생성
                        this.networkData.edges.push({
                            source: nodeId,
                            target: book.isbn,
                            relation_type: 'subject_book',
                            metadata: { description: '주제-도서 관계' }
                        });
                    }
                });

                this.updateNetworkVisualization();
                this.updateNetworkStats();

                // 상태 저장
                this.saveNetworkState();
            } else {
                showError(result.error || '관련 도서를 찾을 수 없습니다.', 'network');
            }
        } catch (error) {
            showError('관련 도서 검색 중 오류가 발생했습니다.', 'network');
        }

        this.showNetworkLoading(false);
    }

    // 노드 삭제
    removeNode(nodeId) {
        // 노드 삭제
        this.networkData.nodes = this.networkData.nodes.filter(n => n.node_id !== nodeId);
        
        // 해당 노드와 연결된 엣지들 삭제 (source/target이 객체인 경우도 고려)
        this.networkData.edges = this.networkData.edges.filter(e => {
            const sourceId = typeof e.source === 'object' ? e.source.node_id : e.source;
            const targetId = typeof e.target === 'object' ? e.target.node_id : e.target;
            return sourceId !== nodeId && targetId !== nodeId;
        });

        // 확장된 노드 목록에서도 제거
        this.expandedNodes.delete(nodeId);

        // 시각화 업데이트
        this.updateNetworkVisualization();
        this.updateNetworkStats();

        // 상태 저장
        this.saveNetworkState();
    }

    // 네트워크 통계 업데이트
    updateNetworkStats() {
        const nodeCount = document.getElementById('node-count');
        const edgeCount = document.getElementById('edge-count');
        const resetBtn = document.getElementById('reset-network');

        if (nodeCount) nodeCount.textContent = `노드: ${this.networkData.nodes.length}개`;
        if (edgeCount) edgeCount.textContent = `연결: ${this.networkData.edges.length}개`;
        if (resetBtn) resetBtn.disabled = this.networkData.nodes.length === 0;
    }

    // 네트워크 리셋
    resetNetwork() {
        this.networkData = { nodes: [], edges: [] };
        this.expandedNodes.clear();

        this.g.selectAll('*').remove();
        this.simulation.nodes([]);
        this.simulation.force('link').links([]);

        document.getElementById('seed-candidates').innerHTML = '';
        document.getElementById('seed-query').value = '';

        this.updateNetworkStats();

        // 저장된 상태 삭제
        this.clearNetworkState();
        this.isInitialized = false;
    }

    // 드래그 이벤트 핸들러들
    dragstarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    dragended(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    // 메뉴 전환 시 재초기화
    reinitialize() {
        setTimeout(() => {
            if (this.svg) {
                this.svg.remove();
            }
            this.initializeVisualization();
            
            // 기존 네트워크 데이터가 있으면 다시 그리기
            if (this.networkData.nodes.length > 0) {
                this.updateNetworkVisualization();
                this.updateNetworkStats();
            }
        }, 100);
    }
}
