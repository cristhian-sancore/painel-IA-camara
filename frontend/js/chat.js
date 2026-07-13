/**
 * Chat Module — Interface de chat RAG com streaming SSE
 */
const Chat = {
    currentConversationId: null,
    isStreaming: false,

    init() {
        document.getElementById('btn-send').addEventListener('click', () => this.sendMessage());
        document.getElementById('btn-new-chat').addEventListener('click', () => this.newConversation());

        const input = document.getElementById('chat-input');
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });

        // Suggestion chips
        document.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                input.value = chip.dataset.question;
                this.sendMessage();
            });
        });

        this.loadConversations();
    },

    async loadConversations() {
        try {
            const conversations = await API.get('/api/chat/conversations');
            this.renderConversations(conversations);
        } catch (err) {
            console.error('Erro ao carregar conversas:', err);
        }
    },

    renderConversations(conversations) {
        const container = document.getElementById('conversations-list');

        if (!conversations.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons-round">forum</span>
                    <p>Nenhuma conversa ainda</p>
                </div>`;
            return;
        }

        container.innerHTML = conversations.map(conv => `
            <div class="conversation-item ${conv.id === this.currentConversationId ? 'active' : ''}"
                 data-id="${conv.id}" onclick="Chat.loadConversation('${conv.id}')">
                <span class="material-icons-round" style="font-size:18px;color:var(--text-muted)">chat_bubble_outline</span>
                <span class="conv-title">${this.escapeHtml(conv.titulo)}</span>
                <button class="conv-delete" onclick="event.stopPropagation();Chat.deleteConversation('${conv.id}')" title="Excluir">
                    <span class="material-icons-round" style="font-size:16px">close</span>
                </button>
            </div>
        `).join('');
    },

    async loadConversation(conversationId) {
        this.closePdfViewer();
        this.currentConversationId = conversationId;
        try {
            const data = await API.get(`/api/chat/conversations/${conversationId}`);
            this.renderMessages(data.messages);
            this.loadConversations(); // refresh active state
        } catch (err) {
            App.toast('Erro ao carregar conversa', 'error');
        }
    },

    renderMessages(messages) {
        const container = document.getElementById('chat-messages');

        if (!messages.length) {
            this.showWelcome();
            return;
        }

        container.innerHTML = messages.map(msg => this.createMessageHTML(msg.role, msg.conteudo, msg.fontes_json)).join('');
        this.scrollToBottom();
    },

    newConversation() {
        this.currentConversationId = null;
        this.closePdfViewer();
        this.showWelcome();
    },

    showWelcome() {
        document.getElementById('chat-messages').innerHTML = `
            <div class="chat-welcome">
                <span class="material-icons-round chat-welcome-icon">auto_awesome</span>
                <h2>Olá! Como posso ajudar?</h2>
                <p>Faça perguntas sobre os documentos legislativos da câmara.</p>
                <div class="chat-suggestions">
                    <button class="suggestion-chip" onclick="document.getElementById('chat-input').value=this.dataset.question;Chat.sendMessage()" data-question="Quais são as leis municipais mais recentes?">📜 Leis recentes</button>
                    <button class="suggestion-chip" onclick="document.getElementById('chat-input').value=this.dataset.question;Chat.sendMessage()" data-question="Qual a lei orgânica do município?">📋 Lei Orgânica</button>
                    <button class="suggestion-chip" onclick="document.getElementById('chat-input').value=this.dataset.question;Chat.sendMessage()" data-question="Quais projetos de lei estão em tramitação?">📄 Projetos em tramitação</button>
                </div>
            </div>`;
    },

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message || this.isStreaming) return;

        // Limpar welcome se for primeira mensagem
        const welcome = document.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        // Mostrar mensagem do usuário
        this.appendMessage('user', message);
        input.value = '';
        input.style.height = 'auto';

        // Mostrar typing indicator
        this.showTyping();
        this.isStreaming = true;
        document.getElementById('btn-send').disabled = true;

        try {
            // Usar streaming SSE
            const token = API.getToken();
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    message,
                    conversation_id: this.currentConversationId,
                }),
            });

            if (!response.ok) {
                throw new Error('Erro ao enviar mensagem');
            }

            let bubbleEl = null;
            let contentEl = null;
            let fullResponse = '';
            let sources = [];

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value);
                const lines = text.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'token') {
                                if (!bubbleEl) {
                                    this.hideTyping();
                                    bubbleEl = this.appendMessage('assistant', '', null, true);
                                    contentEl = bubbleEl.querySelector('.message-text');
                                }
                                fullResponse += data.data;
                                contentEl.textContent = fullResponse;
                                this.scrollToBottom();
                            } else if (data.type === 'error') {
                                if (!bubbleEl) {
                                    this.hideTyping();
                                    bubbleEl = this.appendMessage('assistant', '', null, true);
                                    contentEl = bubbleEl.querySelector('.message-text');
                                }
                                fullResponse += `\n\n⚠️ **[Erro: ${data.data}]**`;
                                contentEl.innerHTML = marked.parse(fullResponse);
                                this.scrollToBottom();
                            } else if (data.type === 'sources') {
                                sources = data.data;
                            } else if (data.type === 'conversation_id') {
                                this.currentConversationId = data.data;
                            } else if (data.type === 'done') {
                                if (!bubbleEl) {
                                    this.hideTyping();
                                    bubbleEl = this.appendMessage('assistant', '', null, true);
                                    contentEl = bubbleEl.querySelector('.message-text');
                                }
                                // Adicionar fontes
                                if (sources.length) {
                                    const sourcesHTML = this.createSourcesHTML(sources);
                                    bubbleEl.querySelector('.message-content').insertAdjacentHTML('beforeend', sourcesHTML);
                                }
                            }
                        } catch (e) { /* ignore parse errors */ }
                    }
                }
            }

            this.loadConversations();

        } catch (err) {
            this.hideTyping();
            this.appendMessage('assistant', 'Desculpe, ocorreu um erro ao processar sua pergunta. Verifique se os serviços estão online.');
            App.toast(err.message, 'error');
        } finally {
            this.isStreaming = false;
            document.getElementById('btn-send').disabled = false;
        }
    },

    appendMessage(role, content, sources = null, returnEl = false) {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = `message-bubble ${role}`;

        const avatarIcon = role === 'user' ? 'person' : 'auto_awesome';
        let sourcesHTML = '';

        if (sources && sources.length) {
            sourcesHTML = this.createSourcesHTML(sources);
        }

        div.innerHTML = `
            <div class="message-avatar">
                <span class="material-icons-round">${avatarIcon}</span>
            </div>
            <div class="message-content">
                <p class="message-text">${this.escapeHtml(content)}</p>
                ${sourcesHTML}
            </div>`;

        container.appendChild(div);
        this.scrollToBottom();

        if (returnEl) return div;
    },

    createMessageHTML(role, content, sources) {
        const avatarIcon = role === 'user' ? 'person' : 'auto_awesome';
        let sourcesHTML = '';

        if (sources && sources.length) {
            sourcesHTML = this.createSourcesHTML(sources);
        }

        return `
            <div class="message-bubble ${role}">
                <div class="message-avatar">
                    <span class="material-icons-round">${avatarIcon}</span>
                </div>
                <div class="message-content">
                    <p class="message-text">${this.escapeHtml(content)}</p>
                    ${sourcesHTML}
                </div>
            </div>`;
    },

    createSourcesHTML(sources) {
        return `
            <div class="message-sources">
                <div class="message-sources-title">📚 Fontes</div>
                ${sources.map(s => `
                    <span class="source-tag" title="${this.escapeHtml(s.trecho || '')}" onclick="Chat.openPdfViewer('${s.document_id || s.doc_id || ''}', ${s.pagina || 1})" style="cursor:pointer;">
                        📄 ${this.escapeHtml(s.doc_nome)}${s.pagina ? ` (p.${s.pagina})` : ''} 
                        <small style="opacity:0.7">${Math.round((s.score || 0) * 100)}%</small>
                    </span>
                `).join('')}
            </div>`;
    },

    openPdfViewer(docId, page) {
        if (!docId) {
            App.toast('ID do documento indisponível na fonte.', 'warning');
            return;
        }
        const panel = document.getElementById('chat-pdf-panel');
        const iframe = document.getElementById('pdf-viewer-iframe');
        panel.classList.add('active');
        
        // Forçar o iframe a recarregar para a nova página (evita cache de hash do navegador)
        const url = `/api/documents/${docId}/file#page=${page}`;
        if (iframe.src.endsWith(url)) {
            // Mesmo arquivo e página, não faz nada
            return;
        }
        iframe.src = 'about:blank';
        setTimeout(() => {
            iframe.src = url;
        }, 50);
    },

    closePdfViewer() {
        const panel = document.getElementById('chat-pdf-panel');
        const iframe = document.getElementById('pdf-viewer-iframe');
        panel.classList.remove('active');
        iframe.src = '';
    },

    showTyping() {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message-bubble assistant';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="message-avatar">
                <span class="material-icons-round">auto_awesome</span>
            </div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>`;
        container.appendChild(div);
        this.scrollToBottom();
    },

    hideTyping() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    },

    async deleteConversation(id) {
        if (!confirm('Excluir esta conversa?')) return;
        try {
            await API.delete(`/api/chat/conversations/${id}`);
            if (this.currentConversationId === id) {
                this.newConversation();
            }
            this.loadConversations();
            App.toast('Conversa excluída', 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    scrollToBottom() {
        const container = document.getElementById('chat-messages');
        container.scrollTop = container.scrollHeight;
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};
