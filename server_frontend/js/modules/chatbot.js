import { ApiClient } from '../core/api.js';
import { renderMarkdown, formatTime } from '../core/utils.js';

export class ChatbotModule {
    constructor() {
        this.apiClient = new ApiClient();
        this.currentSessionId = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeChatbot();
    }

    bindEvents() {
        const chatInput = document.getElementById('chat-input');
        
        if (chatInput) {
            // 엔터 키로 메시지 전송
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // 텍스트 영역 자동 크기 조절
            chatInput.addEventListener('input', () => {
                this.adjustTextareaHeight(chatInput);
            });
        }
    }

    // 챗봇 초기화 및 상태 확인
    async initializeChatbot() {
        try {
            // 새 세션 생성
            const sessionResult = await this.apiClient.createNewSession();
            
            if (sessionResult.success) {
                this.currentSessionId = sessionResult.data.session_id;
                console.log('새 세션 생성됨:', this.currentSessionId);
            }
            
            // 챗봇 상태 확인
            const statusResult = await this.apiClient.getChatbotStatus();
            
            const statusIndicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            const sendButton = document.getElementById('send-button');
            
            if (statusResult.success && statusResult.data.status === 'active') {
                if (statusIndicator) statusIndicator.className = 'status-indicator';
                if (statusText) statusText.textContent = '챗봇이 활성화되었습니다';
                if (sendButton) sendButton.disabled = false;
            } else {
                if (statusIndicator) statusIndicator.className = 'status-indicator inactive';
                if (statusText) statusText.textContent = '챗봇이 비활성화되었습니다';
                if (sendButton) sendButton.disabled = true;
            }
        } catch (error) {
            console.error('챗봇 상태 확인 오류:', error);
            
            const statusIndicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            const sendButton = document.getElementById('send-button');
            
            if (statusIndicator) statusIndicator.className = 'status-indicator inactive';
            if (statusText) statusText.textContent = '연결 오류';
            if (sendButton) sendButton.disabled = true;
        }
    }

    // 메시지 전송
    async sendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        
        if (!message) return;
        
        // 사용자 메시지 추가
        this.addMessage(message, 'user');
        chatInput.value = '';
        this.adjustTextareaHeight(chatInput);
        
        // 타이핑 인디케이터 표시
        this.showTypingIndicator();
        
        const result = await this.apiClient.sendChatMessage(message, this.currentSessionId);
        
        // 타이핑 인디케이터 제거
        this.hideTypingIndicator();
        
        if (result.success) {
            // 세션 ID 업데이트
            this.currentSessionId = result.data.session_id;
            // 봇 응답 추가
            this.addMessage(result.data.response, 'bot');
        } else {
            this.addMessage(`오류: ${result.error}`, 'bot');
        }
    }

    // 메시지 추가
    addMessage(content, role) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        // 봇 메시지의 경우 마크다운 렌더링 적용
        if (role === 'bot') {
            contentDiv.innerHTML = renderMarkdown(content);
        } else {
            contentDiv.textContent = content;
        }

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = formatTime();
        
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);
        messagesContainer.appendChild(messageDiv);
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 타이핑 인디케이터 표시
    showTypingIndicator() {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;

        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.className = 'typing-indicator';
        
        typingDiv.innerHTML = `
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // 타이핑 인디케이터 숨기기
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    // 새로운 채팅 시작
    async startNewChat() {
        const result = await this.apiClient.createNewSession();
        
        if (result.success) {
            this.currentSessionId = result.data.session_id;
            console.log('새 채팅 세션 시작:', this.currentSessionId);
            
            // 채팅 메시지 초기화
            const messagesContainer = document.getElementById('chat-messages');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div class="message bot-message">
                        <div class="message-content">
                            안녕하세요! 도서관과 주제명표목에 대한 질문이 있으시면 언제든 물어보세요. 📚
                        </div>
                        <div class="message-time">${formatTime()}</div>
                    </div>
                `;
            }
        } else {
            console.error('새 채팅 시작 오류:', result.error);
        }
    }

    // 텍스트 영역 자동 크기 조절
    adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
}
