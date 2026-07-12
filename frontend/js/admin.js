/**
 * Admin Module — Dashboard com métricas
 */
const Admin = {
    init() {
        document.getElementById('btn-refresh-dashboard').addEventListener('click', () => this.loadDashboard());
    },

    async loadDashboard() {
        try {
            const data = await API.get('/api/admin/dashboard');
            this.renderStats(data);
            this.renderServices(data.servicos);
        } catch (err) {
            console.error('Erro ao carregar dashboard:', err);
        }
    },

    renderStats(data) {
        this.animateCounter('stat-docs-value', data.total_documentos);
        this.animateCounter('stat-chunks-value', data.total_chunks);
        this.animateCounter('stat-users-value', data.total_usuarios);
        this.animateCounter('stat-messages-value', data.total_mensagens);
    },

    animateCounter(elementId, target) {
        const el = document.getElementById(elementId);
        const current = parseInt(el.textContent) || 0;
        const increment = Math.max(1, Math.floor((target - current) / 30));
        let value = current;

        const timer = setInterval(() => {
            value += increment;
            if (value >= target) {
                value = target;
                clearInterval(timer);
            }
            el.textContent = value.toLocaleString('pt-BR');
        }, 30);
    },

    renderServices(services) {
        for (const [name, info] of Object.entries(services)) {
            const card = document.getElementById(`service-${name}`);
            if (!card) continue;

            const dot = card.querySelector('.service-status-dot');
            const text = card.querySelector('.service-status-text');

            const isOnline = info.status === 'online';
            dot.className = `service-status-dot ${isOnline ? 'online' : 'offline'}`;

            if (isOnline) {
                let extra = '';
                if (info.points_count !== undefined) extra = ` | ${info.points_count} vetores`;
                if (info.models) extra = ` | ${info.models.length} modelos`;
                text.textContent = `Online${extra}`;
            } else {
                text.textContent = 'Offline';
            }
        }
    },
};
