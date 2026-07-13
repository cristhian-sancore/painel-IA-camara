/**
 * Reports Module — Relatórios Automáticos
 */
const Reports = {
    init() {
        document.getElementById('btn-generate-summary').addEventListener('click', () => this.generateSummary());
        document.getElementById('btn-generate-cross').addEventListener('click', () => this.generateCrossAnalysis());
        
        // Carregar opções de documentos ao abrir a aba
        document.getElementById('nav-reports').addEventListener('click', () => this.loadDocuments());
    },

    async loadDocuments() {
        try {
            const data = await API.get('/api/documents?page=1&per_page=100'); // Pega todos para o seletor simplificado
            const docs = data.documents || [];
            
            // Popular select do sumário
            const sumSelect = document.getElementById('report-summary-doc');
            sumSelect.innerHTML = docs.map(d => `<option value="${d.id}">${d.nome}</option>`).join('');
            
            // Popular select da análise cruzada
            const crossSelect = document.getElementById('report-cross-docs');
            crossSelect.innerHTML = docs.map(d => `<option value="${d.id}">${d.nome}</option>`).join('');
        } catch (err) {
            console.error('Erro ao carregar documentos para relatórios:', err);
        }
    },

    async generateSummary() {
        const docId = document.getElementById('report-summary-doc').value;
        const focus = document.getElementById('report-summary-focus').value;
        const btn = document.getElementById('btn-generate-summary');
        
        if (!docId) return App.toast('Selecione um documento.', 'warning');
        
        this.setLoading(btn, true);
        document.getElementById('report-result-content').innerHTML = '<p>Gerando relatório. Isso pode levar alguns minutos...</p>';
        document.getElementById('report-result-container').classList.remove('hidden');

        try {
            const response = await fetch('/api/reports/summarize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${API.getToken()}`
                },
                body: JSON.stringify({ document_id: docId, focus: focus })
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            await this.processStream(response);
            
        } catch (err) {
            document.getElementById('report-result-content').innerHTML = `<p class="text-danger">Erro: ${err.message}</p>`;
            App.toast('Erro ao gerar relatório', 'error');
        } finally {
            this.setLoading(btn, false);
        }
    },

    async generateCrossAnalysis() {
        const selectEl = document.getElementById('report-cross-docs');
        const selectedOptions = Array.from(selectEl.selectedOptions).map(opt => opt.value);
        const topic = document.getElementById('report-cross-topic').value;
        const btn = document.getElementById('btn-generate-cross');
        
        if (selectedOptions.length < 2) return App.toast('Selecione pelo menos 2 documentos.', 'warning');
        if (!topic.trim()) return App.toast('Descreva o tema da análise cruzada.', 'warning');
        
        this.setLoading(btn, true);
        document.getElementById('report-result-content').innerHTML = '<p>Cruzando informações e gerando relatório. Isso pode levar alguns minutos...</p>';
        document.getElementById('report-result-container').classList.remove('hidden');

        try {
            const response = await fetch('/api/reports/cross-analysis', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${API.getToken()}`
                },
                body: JSON.stringify({ document_ids: selectedOptions, topic: topic })
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            await this.processStream(response);
            
        } catch (err) {
            document.getElementById('report-result-content').innerHTML = `<p class="text-danger">Erro: ${err.message}</p>`;
            App.toast('Erro ao gerar análise cruzada', 'error');
        } finally {
            this.setLoading(btn, false);
        }
    },
    
    async processStream(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let fullMarkdown = '';
        let buffer = '';
        
        document.getElementById('report-result-content').innerHTML = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop();
            
            for (const part of parts) {
                if (part.startsWith('data: ')) {
                    const jsonStr = part.substring(6);
                    try {
                        const data = JSON.parse(jsonStr);
                        if (data.type === 'token') {
                            fullMarkdown += data.data;
                            this.renderResult(fullMarkdown);
                        } else if (data.type === 'error') {
                            fullMarkdown += `\n\n⚠️ **[Erro: ${data.data}]**`;
                            this.renderResult(fullMarkdown);
                        }
                    } catch(e) {
                        console.error('SSE JSON parse error:', e);
                    }
                }
            }
        }
    },
    
    renderResult(markdown) {
        let html = markdown;
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/## (.*)/g, '<h2>$1</h2>');
        html = html.replace(/# (.*)/g, '<h1>$1</h1>');
        html = html.replace(/\n\n/g, '<br><br>');
        
        // Add marked support if available
        if (typeof marked !== 'undefined') {
            html = marked.parse(markdown);
        }
        
        document.getElementById('report-result-content').innerHTML = html;
    },

    setLoading(btn, isLoading) {
        if (isLoading) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-ring" style="width:16px;height:16px;border-width:2px;display:inline-block;margin-right:8px;border-color:white;border-top-color:transparent;"></span> Gerando...';
        } else {
            btn.disabled = false;
            // Restore original text based on button
            if (btn.id === 'btn-generate-summary') {
                btn.innerHTML = '<span class="material-icons-round">summarize</span> Gerar Sumário';
            } else {
                btn.innerHTML = '<span class="material-icons-round">compare_arrows</span> Gerar Análise';
            }
        }
    }
};
