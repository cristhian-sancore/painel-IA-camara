/**
 * Groups Module — CRUD de grupos com permissões granulares
 */
const Groups = {
    permissions: [],

    init() {
        document.getElementById('btn-new-group').addEventListener('click', () => this.showModal());

        document.getElementById('group-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveGroup();
        });

        document.querySelectorAll('#group-modal .modal-close, #group-modal .modal-overlay').forEach(el => {
            el.addEventListener('click', () => this.hideModal());
        });
    },

    async loadGroups() {
        try {
            const [groups, permissions] = await Promise.all([
                API.get('/api/groups'),
                API.get('/api/groups/permissions'),
            ]);
            this.permissions = permissions;
            this.renderGroups(groups);
        } catch (err) {
            console.error('Erro ao carregar grupos:', err);
        }
    },

    renderGroups(groups) {
        const container = document.getElementById('groups-container');

        container.innerHTML = groups.map(group => {
            const isBuiltin = group.is_builtin;
            const permChips = group.permissions.map(p =>
                `<span class="perm-chip">${p.codename}</span>`
            ).join('');

            return `
                <div class="group-card glass-card">
                    <div class="group-card-header">
                        <div>
                            <h3>${group.nome} ${isBuiltin ? '<span class="badge badge-muted" style="font-size:0.65rem;margin-left:0.5rem">PADRÃO</span>' : ''}</h3>
                            <div class="group-card-meta">${group.descricao || 'Sem descrição'} · ${group.user_count} usuário(s)</div>
                        </div>
                        ${!isBuiltin ? `
                        <div class="group-card-actions">
                            <button onclick="Groups.editGroup('${group.id}')" title="Editar">
                                <span class="material-icons-round" style="font-size:18px">edit</span>
                            </button>
                            <button onclick="Groups.deleteGroup('${group.id}')" title="Excluir">
                                <span class="material-icons-round" style="font-size:18px">delete</span>
                            </button>
                        </div>` : ''}
                    </div>
                    <div class="group-permissions-list">
                        ${permChips || '<span style="color:var(--text-muted);font-size:0.8rem">Nenhuma permissão</span>'}
                    </div>
                </div>`;
        }).join('');
    },

    showModal(groupData = null) {
        document.getElementById('group-modal-title').textContent = groupData ? 'Editar Grupo' : 'Novo Grupo';
        document.getElementById('group-edit-id').value = groupData ? groupData.id : '';
        document.getElementById('group-nome').value = groupData ? groupData.nome : '';
        document.getElementById('group-descricao').value = groupData ? (groupData.descricao || '') : '';

        // Render permissions grid por categoria
        const container = document.getElementById('permissions-grid');
        const activePerms = groupData ? groupData.permissions.map(p => p.codename) : [];

        const categories = {};
        this.permissions.forEach(p => {
            if (!categories[p.categoria]) categories[p.categoria] = [];
            categories[p.categoria].push(p);
        });

        const categoryNames = {
            chat: '💬 Chat',
            documents: '📄 Documentos',
            users: '👥 Usuários',
            groups: '🔐 Grupos',
            dashboard: '📊 Dashboard',
            settings: '⚙️ Configurações',
            llm: '🧠 Modelo IA',
        };

        container.innerHTML = Object.entries(categories).map(([cat, perms]) => `
            <div class="permission-category">
                <div class="permission-category-title">${categoryNames[cat] || cat}</div>
                <div class="permission-items">
                    ${perms.map(p => `
                        <label class="checkbox-item">
                            <input type="checkbox" name="perm" value="${p.codename}" ${activePerms.includes(p.codename) ? 'checked' : ''}>
                            ${p.descricao}
                        </label>
                    `).join('')}
                </div>
            </div>
        `).join('');

        document.getElementById('group-modal').classList.remove('hidden');
    },

    hideModal() {
        document.getElementById('group-modal').classList.add('hidden');
    },

    async editGroup(groupId) {
        try {
            const groups = await API.get('/api/groups');
            const group = groups.find(g => g.id === groupId);
            if (group) this.showModal(group);
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async saveGroup() {
        const editId = document.getElementById('group-edit-id').value;
        const permCheckboxes = document.querySelectorAll('#permissions-grid input[name="perm"]:checked');

        const data = {
            nome: document.getElementById('group-nome').value,
            descricao: document.getElementById('group-descricao').value,
            permission_codenames: Array.from(permCheckboxes).map(cb => cb.value),
        };

        try {
            if (editId) {
                await API.put(`/api/groups/${editId}`, data);
                App.toast('Grupo atualizado', 'success');
            } else {
                await API.post('/api/groups', data);
                App.toast('Grupo criado', 'success');
            }
            this.hideModal();
            this.loadGroups();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async deleteGroup(groupId) {
        if (!confirm('Excluir este grupo?')) return;
        try {
            await API.delete(`/api/groups/${groupId}`);
            App.toast('Grupo excluído', 'success');
            this.loadGroups();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },
};
