// 모듈 임포트
import { BookSearchModule } from './modules/bookSearch.js';
import { SubjectSearchModule } from './modules/subjectSearch.js';
import { NetworkModule } from './modules/network.js';
import { ChatbotModule } from './modules/chatbot.js';
import { ModalComponent } from './components/modal.js';
import { NavigationComponent } from './components/navigation.js';

// 전역 변수로 모듈 인스턴스들을 저장
let bookSearchModule;
let subjectSearchModule;
let networkModule;
let chatbotModule;
let modalComponent;
let navigationComponent;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function () {
    // 모듈 인스턴스 생성
    bookSearchModule = new BookSearchModule();
    subjectSearchModule = new SubjectSearchModule();
    networkModule = new NetworkModule();
    chatbotModule = new ChatbotModule();
    modalComponent = new ModalComponent();
    navigationComponent = new NavigationComponent();

    // 전역 접근을 위해 window 객체에 할당
    window.bookSearchModule = bookSearchModule;
    window.subjectSearchModule = subjectSearchModule;
    window.networkModule = networkModule;
    window.chatbotModule = chatbotModule;
    window.modalComponent = modalComponent;
    window.navigationComponent = navigationComponent;

    console.log('모든 모듈이 초기화되었습니다.');
});

// 전역 함수들 (HTML에서 직접 호출되는 함수들)
window.switchTab = function(tabType) {
    navigationComponent.switchTab(tabType);
};

window.switchMenu = function(menuType) {
    navigationComponent.switchMenu(menuType);
};

window.performGeneralSearch = function() {
    bookSearchModule.performGeneralSearch();
};

window.performAdvancedSearch = function() {
    bookSearchModule.performAdvancedSearch();
};

window.performVectorSearch = function() {
    bookSearchModule.performVectorSearch();
};

window.performGeneralSubjectSearch = function() {
    subjectSearchModule.performGeneralSearch();
};

window.performVectorSubjectSearch = function() {
    subjectSearchModule.performVectorSearch();
};

window.goToPage = function(page) {
    const activeMenu = document.querySelector('.menu-item.active');
    const menuType = activeMenu ? (activeMenu.getAttribute('data-menu-type') || 'book') : 'book';
    
    if (menuType === 'subject') {
        subjectSearchModule.goToPage(page);
    } else {
        bookSearchModule.goToPage(page);
    }
};

window.closeModal = function(modalType) {
    modalComponent.closeModal(modalType);
};

// 주제 상세 페이지 관련 전역 함수들
window.goBackFromSubjectDetail = function() {
    subjectSearchModule.goBackFromSubjectDetail();
};

// 책 상세 페이지 관련 전역 함수들
window.goBackFromBookDetail = function() {
    bookSearchModule.goBackFromBookDetail();
};

window.openSubjectModal = function(subjectId, subjectLabel) {
    // 파라미터 검증
    if (!subjectId || !subjectLabel) {
        console.warn('openSubjectModal: 잘못된 파라미터', { subjectId, subjectLabel });
        return;
    }
    
    // 주제 검색 모듈의 showSubjectDetails 함수를 우선적으로 사용
    if (window.subjectSearchModule && typeof window.subjectSearchModule.showSubjectDetails === 'function') {
        window.subjectSearchModule.showSubjectDetails(subjectId);
    } else if (window.bookSearchModule && typeof window.bookSearchModule.openSubjectModal === 'function') {
        window.bookSearchModule.openSubjectModal(subjectId, subjectLabel);
    } else {
        console.error('사용 가능한 주제 모달 함수가 없습니다');
    }
};

window.searchSeedNode = function() {
    networkModule.searchSeedNode();
};

window.resetNetwork = function() {
    networkModule.resetNetwork();
};

window.sendMessage = function() {
    chatbotModule.sendMessage();
};

window.startNewChat = function() {
    chatbotModule.startNewChat();
};
