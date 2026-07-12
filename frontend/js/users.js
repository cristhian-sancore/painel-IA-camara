/**
 * Users Module — CRUD de usuários
 */
const Users = {
    groups: [],

    init() {
        document.getElementById('btn-new-user').addEventListener('click', () => this.showModal());

        document.getElementById('user-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveUser();
        });

        // Modal close
        document.querySelectorAll('#user-modal .modal-close, #user-modal .modal-overlay').forEach(el => {
            el.addEventListener('click', () => this.hideModal());
        });
    },

    async loadUsers() {
        try {
            const [users, groups] = await Promise.all([
                API.get('/api/users'),
                API.get('/api/groups').catch(() => []),
            ]);
            this.groups = groups;
            this.renderTable(users);
        } catch (err) {
            console.error('Erro ao carregar usuários:', err);
        }
    },

    renderTable(users) {
        const tbody = document.getElementById('users-table-body');

        tbody.innerHTML = users.map(user => {
            const roleBadge = {
                superadmin: '<span class="badge badge-danger">SuperAdmin</span>',
                admin: '<span class="badge badge-warning">Admin</span>',
                user: '<span class="badge badge-info">Usuário</span>',
            }[user.role] || '<span class="badge badge-muted">—</span>';

            const statusBadge = user.ativo
                ? '<span class="badge badge-success">Ativo</span>'
                : '<span class="badge badge-muted">Inativo</span>';

            return `
                <tr>
                    <td>
                        <div style="display:flex;align-items:center;gap:0.75rem">
                            <div class="user-avatar" style="width:32px;height:32px;font-size:0.7rem">${user.nome.slice(0, 2).toUpperCase()}</div>
                            ${user.nome}
                        </div>
                    </td>
                    <td>${user.email}</td>
                    <td>${roleBadge}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <div style="display:flex;gap:0.5rem">
                            <button class="btn btn-sm btn-outline" onclick="Users.editUser('${user.id}')" title="Editar">
                                <span class="material-icons-round" style="font-size:16px">edit</span>
                            </button>
                            <button class="btn btn-sm btn-outline" onclick="Users.toggleUser('${user.id}', ${user.ativo})" title="${user.ativo ? 'Desativar' : 'Ativar'}"
                                style="${!user.ativo ? 'color:var(--success);border-color:var(--success)' : 'color:var(--danger);border-color:var(--danger)'}">
                                <span class="material-icons-round" style="font-size:16px">${user.ativo ? 'person_off' : 'person'}</span>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    },

    showModal(userData = null) {
        document.getElementById('user-modal-title').textContent = userData ? 'Editar Usuário' : 'Novo Usuário';
        document.getElementById('user-edit-id').value = userData ? userData.id : '';
        document.getElementById('user-nome').value = userData ? userData.nome : '';
        document.getElementById('user-email').value = userData ? userData.email : '';
        document.getElementById('user-senha').value = '';
        document.getElementById('user-senha').required = !userData;
        document.getElementById('user-role-select').value = userData ? userData.role : 'user';

        // Render groups checkboxes
        const container = document.getElementById('user-groups-checkboxes');
        const userGroupIds = userData ? userData.groups.map(g => g.id) : [];

        container.innerHTML = this.groups
            .filter(g => !g.is_builtin)
            .map(g => `
                <label class="checkbox-item">
                    <input type="checkbox" value="${g.id}" ${userGroupIds.includes(g.id) ? 'checked' : ''}>
                    ${g.nome}
                </label>
            `).join('') || '<span style="color:var(--text-muted);font-size:0.85rem">Nenhum grupo personalizado criado</span>';

        document.getElementById('user-modal').classList.remove('hidden');
    },

    hideModal() {
        document.getElementById('user-modal').classList.add('hidden');
    },

    async editUser(userId) {
        try {
            const users = await API.get('/api/users');
            const user = users.find(u => u.id === userId);
            if (user) this.showModal(user);
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async saveUser() {
        const editId = document.getElementById('user-edit-id').value;
        const groupCheckboxes = document.querySelectorAll('#user-groups-checkboxes input:checked');
        const groupIds = Array.from(groupCheckboxes).map(cb => cb.value);

        const data = {
            nome: document.getElementById('user-nome').value,
            email: document.getElementById('user-email').value,
            role: document.getElementById('user-role-select').value,
            group_ids: groupIds,
        };

        const senha = document.getElementById('user-senha').value;
        if (senha) data.senha = senha;

        try {
            if (editId) {
                await API.put(`/api/users/${editId}`, data);
                App.toast('Usuário atualizado', 'success');
            } else {
                data.senha = senha;
                await API.post('/api/users', data);
                App.toast('Usuário criado', 'success');
            }
            this.hideModal();
            this.loadUsers();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async toggleUser(userId, isActive) {
        const action = isActive ? 'desativar' : 'ativar';
        if (!confirm(`Deseja ${action} este usuário?`)) return;

        try {
            if (isActive) {
                await API.delete(`/api/users/${userId}`);
            } else {
                await API.put(`/api/users/${userId}`, { ativo: true });
            }
            App.toast(`Usuário ${action === 'desativar' ? 'desativado' : 'ativado'}`, 'success');
            this.loadUsers();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },
};
