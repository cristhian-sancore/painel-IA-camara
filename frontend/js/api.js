/**
 * API Client — HTTP client com JWT interceptor
 */
const API = {
    baseUrl: '',

    getToken() {
        return localStorage.getItem('access_token');
    },

    setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    },

    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
    },

    getUser() {
        const u = localStorage.getItem('user');
        return u ? JSON.parse(u) : null;
    },

    setUser(user) {
        localStorage.setItem('user', JSON.stringify(user));
    },

    async request(url, options = {}) {
        const token = this.getToken();
        const headers = {
            ...(options.headers || {}),
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const response = await fetch(`${this.baseUrl}${url}`, {
            ...options,
            headers,
        });

        // Token expirado → tenta refresh
        if (response.status === 401 && localStorage.getItem('refresh_token')) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${this.getToken()}`;
                return fetch(`${this.baseUrl}${url}`, { ...options, headers });
            } else {
                this.clearTokens();
                window.location.reload();
                return response;
            }
        }

        return response;
    },

    async refreshToken() {
        try {
            const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    refresh_token: localStorage.getItem('refresh_token'),
                }),
            });

            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access_token, data.refresh_token);
                this.setUser(data.user);
                return true;
            }
            return false;
        } catch {
            return false;
        }
    },

    async get(url) {
        const res = await this.request(url);
        if (!res.ok) throw await this.handleError(res);
        return res.json();
    },

    async post(url, data) {
        const res = await this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await this.handleError(res);
        return res.json();
    },

    async put(url, data) {
        const res = await this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
        if (!res.ok) throw await this.handleError(res);
        return res.json();
    },

    async delete(url) {
        const res = await this.request(url, { method: 'DELETE' });
        if (!res.ok) throw await this.handleError(res);
        return res.json();
    },

    async upload(url, file) {
        const formData = new FormData();
        formData.append('file', file);

        const res = await this.request(url, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) throw await this.handleError(res);
        return res.json();
    },

    async handleError(res) {
        try {
            const data = await res.json();
            return new Error(data.detail || 'Erro desconhecido');
        } catch {
            return new Error(`Erro ${res.status}`);
        }
    },
};
