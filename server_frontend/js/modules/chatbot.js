import { ApiClient } from '../core/api.js';
import { renderMarkdown, formatTime } from '../core/utils.js';

/**
 * ChatbotModule handles chatbot UI interactions and API communication.
 */
export class ChatbotModule {
    constructor() {
        this.apiClient = new ApiClient();
        this.currentSessionId = null;
        this.init();
    }

    /**
     * Initializes the chatbot module by binding events and checking status.
     */
    init() {
        this.bindEvents();
        this.initializeChatbot();
        this.bindReferenceClickHandler();
    }

    /**
     * Binds UI events for chat input and message sending.
     */
    bindEvents() {
        const chatInput = document.getElementById('chat-input');
        
        if (chatInput) {
            // Send message on Enter key (without Shift)
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Auto-resize textarea as user types
            chatInput.addEventListener('input', () => {
                this.adjustTextareaHeight(chatInput);
            });
        }
    }

    /**
     * Binds the reference click handler to the global scope for inline onclick handlers.
     */
    bindReferenceClickHandler() {
        window.handleReferenceClick = this.handleReferenceClick.bind(this);
    }

    /**
     * Initializes chatbot session and updates status indicators.
     */
    async initializeChatbot() {
        try {
            // Create a new chat session
            const sessionResult = await this.apiClient.createNewSession();
            
            if (sessionResult.success) {
                this.currentSessionId = sessionResult.data.session_id;
                console.log('새 세션 생성됨:', this.currentSessionId);
            }
            
            // Check chatbot status and update UI
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
            // Handle errors and update UI accordingly
            console.error('챗봇 상태 확인 오류:', error);
            
            const statusIndicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            const sendButton = document.getElementById('send-button');
            
            if (statusIndicator) statusIndicator.className = 'status-indicator inactive';
            if (statusText) statusText.textContent = '연결 오류';
            if (sendButton) sendButton.disabled = true;
        }
    }

    /**
     * Sends a user message to the chatbot and displays the response.
     */
    async sendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        
        if (!message) return;
        
        // Add user message to chat
        this.addMessage(message, 'user');
        chatInput.value = '';
        this.adjustTextareaHeight(chatInput);
        
        // Show typing indicator while waiting for response
        this.showTypingIndicator();
        
        const result = await this.apiClient.sendChatMessage(message, this.currentSessionId);
        
        // Remove typing indicator after response
        this.hideTypingIndicator();
        
        if (result.success) {
            // Update session ID and add bot response
            this.currentSessionId = result.data.session_id;
            this.addMessage(result.data.response, 'bot');
        } else {
            // Show error message from bot
            this.addMessage(`오류: ${result.error}`, 'bot');
        }
    }

    /**
     * Adds a message to the chat UI.
     * @param {string} content - Message text or markdown.
     * @param {string} role - 'user' or 'bot'.
     */
    addMessage(content, role) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        // Render markdown for bot messages
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
        
        // Render math equations for bot messages
        if (role === 'bot' && window.MathJax) {
            MathJax.typesetPromise([contentDiv]).then(() => {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }).catch((err) => {
                console.log('MathJax rendering error:', err);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            });
        } else {
            // Scroll to bottom after adding message
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    /**
     * Displays a typing indicator in the chat UI.
     */
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

    /**
     * Removes the typing indicator from the chat UI.
     */
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    /**
     * Starts a new chat session and resets the chat UI.
     */
    async startNewChat() {
        const result = await this.apiClient.createNewSession();
        
        if (result.success) {
            this.currentSessionId = result.data.session_id;
            console.log('새 채팅 세션 시작:', this.currentSessionId);
            
            // Reset chat messages and show welcome message
            const messagesContainer = document.getElementById('chat-messages');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div class="message bot-message">
                        <div class="message-content">
                            안녕하세요! 
                        </div>
                        <div class="message-time">${formatTime()}</div>
                    </div>
                `;
            }
        } else {
            console.error('새 채팅 시작 오류:', result.error);
        }
    }

    /**
     * Handles clicks on reference links (subject or book references).
     * @param {Event} event - The click event
     * @param {string} referenceCode - The reference code (ISBN or subject code)
     * @param {string} referenceType - 'subject' or 'book'
     */
    async handleReferenceClick(event, referenceCode, referenceType) {
        event.preventDefault();
        console.log(`${referenceType} 참조 클릭됨:`, referenceCode);
        
        // alert(`${referenceType === 'subject' ? '주제' : '도서'} 참조: ${referenceCode}\n(아직 구현되지 않음)`);
        
        
        if (referenceType === 'subject') {
            let message = `주제 ${referenceCode} ?`;
            
            // Add user message to chat
            this.addMessage(message, 'user');
            
            // Show typing indicator while waiting for response
            this.showTypingIndicator();
            
            const result = await this.apiClient.sendChatRequestBySubject(referenceCode, this.currentSessionId);
            
            // Remove typing indicator after response
            this.hideTypingIndicator();
            
            if (result.success) {
                // Update session ID and add bot response
                this.currentSessionId = result.data.session_id;
                this.addMessage(result.data.response, 'bot');
            } else {
                // Show error message from bot
                this.addMessage(`오류: ${result.error}`, 'bot');
            }
        }
        else if (referenceType === 'book') {
            let message = `도서 ${referenceCode} ?`;
            
            // Add user message to chat
            this.addMessage(message, 'user');
            
            // Show typing indicator while waiting for response
            this.showTypingIndicator();
            
            const result = await this.apiClient.sendChatRequestByBook(referenceCode, this.currentSessionId);
            
            // Remove typing indicator after response
            this.hideTypingIndicator();
            
            if (result.success) {
                // Update session ID and add bot response
                this.currentSessionId = result.data.session_id;
                this.addMessage(result.data.response, 'bot');
            } else {
                // Show error message from bot
                this.addMessage(`오류: ${result.error}`, 'bot');
            }
            
        }
        else {
            console.error('알 수 없는 참조 유형:', referenceType);
            return;
        }
    }

    /**
     * Automatically adjusts the height of the chat input textarea.
     * @param {HTMLTextAreaElement} textarea 
     */
    adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

}
