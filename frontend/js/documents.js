/**
 * Documents Module — Upload e gestão de documentos
 */
const Documents = {
    currentPage: 1,

    init() {
        document.getElementById('btn-upload-doc').addEventListener('click', () => this.showUploadModal());
        document.getElementById('doc-search').addEventListener('input', App.debounce(() => this.loadDocuments(), 400));

        // Drop zone
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');

        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length) this.uploadFiles(e.dataTransfer.files);
        });
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) this.uploadFiles(fileInput.files);
        });

        // Modal close
        document.querySelectorAll('#upload-modal .modal-close, #upload-modal .modal-overlay').forEach(el => {
            el.addEventListener('click', () => this.hideUploadModal());
        });
    },

    async loadDocuments() {
        const search = document.getElementById('doc-search').value;
        try {
            const data = await API.get(`/api/documents?page=${this.currentPage}&per_page=20&search=${encodeURIComponent(search)}`);
            this.renderTable(data.documents);
            this.renderPagination(data.total, data.page, data.per_page);
        } catch (err) {
            console.error('Erro ao carregar documentos:', err);
        }
    },

    renderTable(documents) {
        const tbody = document.getElementById('documents-table-body');

        if (!documents.length) {
            tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="6">
                        <div class="empty-state">
                            <span class="material-icons-round">folder_open</span>
                            <p>Nenhum documento encontrado</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = documents.map(doc => {
            const statusBadge = {
                indexado: '<span class="badge badge-success">Indexado</span>',
                processando: '<span class="badge badge-warning">Processando</span>',
                pendente: '<span class="badge badge-info">Pendente</span>',
                erro: `<span class="badge badge-danger" title="${doc.erro_msg || ''}">Erro</span>`,
            }[doc.status] || '<span class="badge badge-muted">—</span>';

            const date = new Date(doc.criado_em).toLocaleDateString('pt-BR');
            const size = this.formatFileSize(doc.tamanho_bytes);

            return `
                <tr>
                    <td>
                        <div style="display:flex;align-items:center;gap:0.5rem">
                            <span class="material-icons-round" style="color:var(--secondary);font-size:20px">description</span>
                            <span>${doc.nome}</span>
                        </div>
                    </td>
                    <td><span class="badge badge-muted">${doc.tipo.toUpperCase()}</span></td>
                    <td>${doc.total_chunks}</td>
                    <td>${statusBadge}</td>
                    <td>${date}</td>
                    <td>
                        <div class="toggle-switch">
                            <input type="checkbox" id="toggle-${doc.id}" ${doc.ativo !== false ? 'checked' : ''} onchange="Documents.toggleActive('${doc.id}')">
                            <label for="toggle-${doc.id}"></label>
                        </div>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-outline" onclick="Documents.deleteDoc('${doc.id}')" title="Excluir"
                            style="color:var(--danger);border-color:var(--danger)">
                            <span class="material-icons-round" style="font-size:16px">delete</span>
                        </button>
                    </td>
                </tr>`;
        }).join('');
    },

    renderPagination(total, page, perPage) {
        const container = document.getElementById('documents-pagination');
        const totalPages = Math.ceil(total / perPage);

        if (totalPages <= 1) { container.innerHTML = ''; return; }

        let html = '';
        for (let i = 1; i <= totalPages; i++) {
            html += `<button class="${i === page ? 'active' : ''}" onclick="Documents.goToPage(${i})">${i}</button>`;
        }
        container.innerHTML = html;
    },

    goToPage(page) {
        this.currentPage = page;
        this.loadDocuments();
    },

    showUploadModal() {
        document.getElementById('upload-modal').classList.remove('hidden');
        document.getElementById('upload-progress').classList.add('hidden');
        document.getElementById('file-input').value = '';
    },

    hideUploadModal() {
        document.getElementById('upload-modal').classList.add('hidden');
    },

    async uploadFiles(files) {
        const progressEl = document.getElementById('upload-progress');
        const progressFill = document.getElementById('progress-fill');
        const statusEl = document.getElementById('upload-status');

        progressEl.classList.remove('hidden');
        
        let successCount = 0;
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const percent = ((i) / files.length) * 100;
            progressFill.style.width = `${percent}%`;
            statusEl.textContent = `Enviando ${file.name} (${i + 1}/${files.length})...`;

            try {
                await API.upload('/api/documents/upload', file);
                successCount++;
            } catch (err) {
                App.toast(`Erro em ${file.name}: ${err.message}`, 'error');
            }
        }

        progressFill.style.width = '100%';
        if (successCount === files.length) {
            statusEl.textContent = 'Todos os uploads concluídos! Processando em background...';
            App.toast('Documentos enviados com sucesso!', 'success');
        } else {
            statusEl.textContent = `Upload concluído com falhas (${successCount}/${files.length}).`;
        }

        setTimeout(() => {
            this.hideUploadModal();
            this.loadDocuments();
        }, 1500);
    },

    async toggleActive(id) {
        try {
            const res = await API.put(`/api/documents/${id}/toggle-active`);
            App.toast(res.message, 'success');
            // Recarrega silenciosamente para atualizar estado local se necessário
            this.loadDocuments();
        } catch (err) {
            App.toast(err.message, 'error');
            this.loadDocuments(); // Reverte checkbox visualmente
        }
    },

    async deleteDoc(id) {
        if (!confirm('Excluir este documento e todos os seus chunks?')) return;
        try {
            await API.delete(`/api/documents/${id}`);
            App.toast('Documento excluído', 'success');
            this.loadDocuments();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    },
};
