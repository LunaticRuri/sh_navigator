export class ModalComponent {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // 클릭시 모달 닫기
        window.addEventListener('click', (event) => {
            const modals = ['book', 'subject', 'subject-explore'];
            
            modals.forEach(modalType => {
                const modalId = modalType === 'subject-explore' ? 'subject-explore-modal' : `${modalType}-modal`;
                const modal = document.getElementById(modalId);
                if (modal && event.target === modal) {
                    this.closeModal(modalType);
                }
            });
        });
    }

    // 모달 닫기
    closeModal(type) {
        const modalId = type === 'subject-explore' ? 'subject-explore-modal' : `${type}-modal`;
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // 모달 열기
    openModal(type) {
        const modalId = type === 'subject-explore' ? 'subject-explore-modal' : `${type}-modal`;
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'block';
        }
    }
}
