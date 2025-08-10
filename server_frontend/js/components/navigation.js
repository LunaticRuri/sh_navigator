import { clearResults } from '../core/utils.js';

export class NavigationComponent {
    constructor() {
        this.init();
    }

    init() {
        // 초기화 시 필요한 작업
    }

    // 탭 전환
    switchTab(tabType) {
        // 탭 버튼 활성화 상태 변경
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });

        // 클릭된 탭 버튼 찾기
        const clickedButton = event.target;
        if (clickedButton) {
            clickedButton.classList.add('active');
        }

        // 검색 폼 표시/숨김
        document.querySelectorAll('.search-form').forEach(form => {
            form.classList.remove('active');
        });

        const targetFormId = `${tabType}-search`;
        const targetForm = document.getElementById(targetFormId);
        if (targetForm) {
            targetForm.classList.add('active');
        }

        // 탭 전환 시 검색 결과 초기화
        this.clearSearchResults();
    }

    // 메뉴 전환
    switchMenu(menuType) {
        // 사이드바 메뉴 활성화 상태 변경
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });

        // 클릭된 메뉴 활성화
        const clickedMenu = event.target.closest('.menu-item');
        if (clickedMenu) {
            clickedMenu.classList.add('active');
            // data-menu-type 속성 설정
            clickedMenu.setAttribute('data-menu-type', menuType);
        }

        // 모든 섹션 숨기기
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });

        // 해당 섹션 표시
        const targetSection = document.getElementById(`${menuType}-section`);
        if (targetSection) {
            targetSection.classList.add('active');

            // 네트워크 섹션이 활성화될 때 시각화 재초기화
            if (menuType === 'network' && window.networkModule) {
                window.networkModule.reinitialize();
            }
        }
    }

    // 검색 결과 초기화
    clearSearchResults() {
        // 현재 활성 메뉴 타입 확인
        const activeMenu = document.querySelector('.menu-item.active');
        let menuType = 'book'; // 기본값

        if (activeMenu) {
            menuType = activeMenu.getAttribute('data-menu-type') || 'book';
        }

        // 해당 메뉴 타입의 결과 초기화
        clearResults(menuType);

        // 각 모듈의 검색 결과 초기화
        if (menuType === 'book' && window.bookSearchModule) {
            window.bookSearchModule.clearSearchResults();
        } else if (menuType === 'subject' && window.subjectSearchModule) {
            window.subjectSearchModule.clearSearchResults();
        }
    }
}
