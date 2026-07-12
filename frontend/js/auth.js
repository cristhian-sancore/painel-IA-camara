/**
 * Auth Module — Login/Logout
 */
const Auth = {
    init() {
        const form = document.getElementById('login-form');
        form.addEventListener('submit', (e) => this.handleLogin(e));
    },

    async handleLogin(e) {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const senha = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');
        const btn = document.getElementById('login-btn');

        btn.disabled = true;
        btn.querySelector('.btn-text').classList.add('hidden');
        btn.querySelector('.btn-loader').classList.remove('hidden');
        errorEl.classList.add('hidden');

        try {
            const data = await API.post('/api/auth/login', { email, senha });
            API.setTokens(data.access_token, data.refresh_token);
            API.setUser(data.user);
            App.showApp();
        } catch (err) {
            errorEl.textContent = err.message;
            errorEl.classList.remove('hidden');
        } finally {
            btn.disabled = false;
            btn.querySelector('.btn-text').classList.remove('hidden');
            btn.querySelector('.btn-loader').classList.add('hidden');
        }
    },

    logout() {
        API.clearTokens();
        App.showLogin();
    },

    isLoggedIn() {
        return !!API.getToken();
    },
};
