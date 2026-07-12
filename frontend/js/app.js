/**
 * App — Orquestrador principal do SPA
 */
const App = {
    currentPage: 'chat',
    user: null,

    async init() {
        // Carregar branding público (antes do login)
        await this.loadBranding();

        // Inicializar módulos
        Auth.init();
        Chat.init();
        Documents.init();
        Reports.init();
        Admin.init();
        Users.init();
        Groups.init();
        Settings.init();

        // Setup sidebar navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigateTo(item.dataset.page);
            });
        });

        // Sidebar toggle
        document.getElementById('sidebar-toggle').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('collapsed');
        });

        // Logout
        document.getElementById('btn-logout').addEventListener('click', () => Auth.logout());

        // Check auth
        if (Auth.isLoggedIn()) {
            this.user = API.getUser();
            this.showApp();
        } else {
            this.showLogin();
        }

        // Hide loading
        setTimeout(() => {
            document.getElementById('loading-screen').classList.add('fade-out');
            setTimeout(() => document.getElementById('loading-screen').classList.add('hidden'), 500);
        }, 600);
    },

    showLogin() {
        document.getElementById('page-login').classList.remove('hidden');
        document.getElementById('page-app').classList.add('hidden');
    },

    showApp() {
        this.user = API.getUser();
        document.getElementById('page-login').classList.add('hidden');
        document.getElementById('page-app').classList.remove('hidden');

        // Update user info in sidebar
        if (this.user) {
            document.getElementById('user-name').textContent = this.user.nome;
            document.getElementById('user-role').textContent = this.user.role;
            document.getElementById('user-avatar').textContent = this.user.nome.slice(0, 2).toUpperCase();
        }

        // Hide nav items based on permissions
        this.updateNavVisibility();

        // Navigate to default page
        this.navigateTo('chat');
    },

    updateNavVisibility() {
        if (!this.user) return;
        const perms = new Set(this.user.permissions || []);
        const role = this.user.role;

        // SuperAdmin vê tudo
        if (role === 'superadmin') {
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('hidden'));
            return;
        }

        // Esconder itens sem permissão
        const navPermissions = {
            'nav-chat': ['chat.use'],
            'nav-documents': ['documents.view'],
            'nav-dashboard': ['dashboard.view'],
            'nav-users': ['users.view'],
            'nav-groups': ['groups.manage'],
            'nav-settings': ['settings.view', 'settings.edit'],
        };

        for (const [navId, requiredPerms] of Object.entries(navPermissions)) {
            const el = document.getElementById(navId);
            if (el) {
                const hasAccess = requiredPerms.some(p => perms.has(p));
                el.classList.toggle('hidden', !hasAccess);
            }
        }

        // Esconder botões de ação sem permissão
        const uploadBtn = document.getElementById('btn-upload-doc');
        if (uploadBtn) uploadBtn.classList.toggle('hidden', !perms.has('documents.upload'));

        const newUserBtn = document.getElementById('btn-new-user');
        if (newUserBtn) newUserBtn.classList.toggle('hidden', !perms.has('users.manage'));

        const newGroupBtn = document.getElementById('btn-new-group');
        if (newGroupBtn) newGroupBtn.classList.toggle('hidden', !perms.has('groups.manage'));
    },

    navigateTo(page) {
        this.currentPage = page;

        // Update nav active state
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.page === page);
        });

        // Show/hide sections
        document.querySelectorAll('.content-section').forEach(el => {
            el.classList.add('hidden');
        });
        const section = document.getElementById(`section-${page}`);
        if (section) {
            section.classList.remove('hidden');
        }

        // Load data for the page
        switch (page) {
            case 'chat':
                Chat.loadConversations();
                break;
            case 'documents':
                Documents.loadDocuments();
                break;
            case 'reports':
                Reports.loadDocuments();
                break;
            case 'dashboard':
                Admin.loadDashboard();
                break;
            case 'users':
                Users.loadUsers();
                break;
            case 'groups':
                Groups.loadGroups();
                break;
            case 'settings':
                Settings.loadSettings();
                break;
        }
    },

    async loadBranding() {
        try {
            const config = await fetch('/api/settings/public').then(r => r.json());

            // Título
            document.title = `${config.nome_camara}${config.cidade ? ' — ' + config.cidade : ''}`;
            document.getElementById('login-title').textContent = config.nome_camara || 'Painel RAG';
            document.getElementById('login-subtitle').textContent = config.cidade ? `${config.cidade}${config.estado ? ' - ' + config.estado : ''}` : 'Câmara de Vereadores';
            document.getElementById('sidebar-title').textContent = config.nome_camara || 'Painel RAG';

            // Logo
            if (config.logo_url) {
                document.getElementById('login-logo').src = config.logo_url;
                document.getElementById('sidebar-logo').src = config.logo_url;
            }

            // Favicon
            if (config.favicon_url) {
                document.getElementById('dynamic-favicon').href = config.favicon_url;
            }

            // Cores dinâmicas
            const root = document.documentElement;
            if (config.cor_primaria) {
                root.style.setProperty('--primary', config.cor_primaria);
                root.style.setProperty('--gradient-primary', `linear-gradient(135deg, ${config.cor_primaria}, var(--accent))`);
            }
            if (config.cor_secundaria) {
                root.style.setProperty('--secondary', config.cor_secundaria);
                root.style.setProperty('--gradient-accent', `linear-gradient(135deg, ${config.cor_secundaria}, ${this.lightenColor(config.cor_secundaria, 20)})`);
            }
            if (config.cor_fundo) {
                root.style.setProperty('--bg-main', config.cor_fundo);
                root.style.setProperty('--gradient-bg', `linear-gradient(135deg, ${config.cor_fundo} 0%, ${this.lightenColor(config.cor_fundo, 5)} 50%, ${this.lightenColor(config.cor_fundo, 8)} 100%)`);
            }
            if (config.cor_texto) {
                root.style.setProperty('--text-primary', config.cor_texto);
            }
        } catch (err) {
            console.log('Branding padrão carregado');
        }
    },

    lightenColor(hex, percent) {
        const num = parseInt(hex.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.min(255, (num >> 16) + amt);
        const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
        const B = Math.min(255, (num & 0x0000FF) + amt);
        return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
    },

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const icons = {
            success: 'check_circle',
            error: 'error',
            warning: 'warning',
            info: 'info',
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="material-icons-round toast-icon">${icons[type] || 'info'}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <span class="material-icons-round">close</span>
            </button>`;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-out');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },
};

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => App.init());
