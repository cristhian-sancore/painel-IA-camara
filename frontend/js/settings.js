/**
 * Settings Module — Configurações do sistema
 */
const Settings = {
    init() {
        // Identity form
        document.getElementById('settings-identity-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveIdentity();
        });

        // Appearance form
        document.getElementById('settings-appearance-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveAppearance();
        });

        // LLM form
        document.getElementById('settings-llm-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveLLM();
        });

        // Color inputs live preview
        ['cfg-cor-primaria', 'cfg-cor-secundaria', 'cfg-cor-fundo', 'cfg-cor-texto'].forEach(id => {
            const input = document.getElementById(id);
            input.addEventListener('input', () => {
                input.closest('.color-input-wrapper').querySelector('.color-value').textContent = input.value;
            });
        });

        // Temperature slider
        document.getElementById('cfg-temperatura').addEventListener('input', (e) => {
            document.getElementById('temperatura-value').textContent = e.target.value;
        });

        // Logo upload
        document.getElementById('btn-upload-logo').addEventListener('click', () => {
            document.getElementById('input-logo').click();
        });
        document.getElementById('input-logo').addEventListener('change', (e) => {
            if (e.target.files.length) this.uploadLogo(e.target.files[0]);
        });

        // Favicon upload
        document.getElementById('btn-upload-favicon').addEventListener('click', () => {
            document.getElementById('input-favicon').click();
        });
        document.getElementById('input-favicon').addEventListener('change', (e) => {
            if (e.target.files.length) this.uploadFavicon(e.target.files[0]);
        });

        // Refresh models
        document.getElementById('btn-refresh-models').addEventListener('click', () => this.loadModels());
    },

    async loadSettings() {
        try {
            const config = await API.get('/api/settings');
            this.populateForm(config);
        } catch (err) {
            console.error('Erro ao carregar configurações:', err);
        }
    },

    populateForm(config) {
        document.getElementById('cfg-nome-camara').value = config.nome_camara || '';
        document.getElementById('cfg-cidade').value = config.cidade || '';
        document.getElementById('cfg-estado').value = config.estado || '';

        document.getElementById('cfg-cor-primaria').value = config.cor_primaria || '#1a237e';
        document.getElementById('cfg-cor-secundaria').value = config.cor_secundaria || '#c9a84c';
        document.getElementById('cfg-cor-fundo').value = config.cor_fundo || '#0f0f1a';
        document.getElementById('cfg-cor-texto').value = config.cor_texto || '#e0e0e0';

        // Update color labels
        ['cfg-cor-primaria', 'cfg-cor-secundaria', 'cfg-cor-fundo', 'cfg-cor-texto'].forEach(id => {
            const el = document.getElementById(id);
            const label = el.closest('.color-input-wrapper').querySelector('.color-value');
            if (label) label.textContent = el.value;
        });

        if (config.modelo_llm) document.getElementById('cfg-modelo-llm').value = config.modelo_llm;
        if (config.temperatura !== null) {
            document.getElementById('cfg-temperatura').value = config.temperatura;
            document.getElementById('temperatura-value').textContent = config.temperatura;
        }
        if (config.max_tokens) document.getElementById('cfg-max-tokens').value = config.max_tokens;
        if (config.system_prompt) document.getElementById('cfg-system-prompt').value = config.system_prompt;

        // Preview images
        if (config.logo_url) {
            document.getElementById('preview-logo').src = config.logo_url;
        }
        if (config.favicon_url) {
            document.getElementById('preview-favicon').src = config.favicon_url;
        }

        this.loadModels();
    },

    async saveIdentity() {
        try {
            await API.put('/api/settings', {
                nome_camara: document.getElementById('cfg-nome-camara').value,
                cidade: document.getElementById('cfg-cidade').value,
                estado: document.getElementById('cfg-estado').value,
            });
            App.toast('Identidade salva!', 'success');
            App.loadBranding();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async saveAppearance() {
        try {
            await API.put('/api/settings', {
                cor_primaria: document.getElementById('cfg-cor-primaria').value,
                cor_secundaria: document.getElementById('cfg-cor-secundaria').value,
                cor_fundo: document.getElementById('cfg-cor-fundo').value,
                cor_texto: document.getElementById('cfg-cor-texto').value,
            });
            App.toast('Cores salvas!', 'success');
            App.loadBranding();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async saveLLM() {
        try {
            await API.put('/api/settings', {
                modelo_llm: document.getElementById('cfg-modelo-llm').value,
                temperatura: parseFloat(document.getElementById('cfg-temperatura').value),
                max_tokens: parseInt(document.getElementById('cfg-max-tokens').value),
                system_prompt: document.getElementById('cfg-system-prompt').value,
            });
            App.toast('Configuração de IA salva!', 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async uploadLogo(file) {
        try {
            await API.upload('/api/settings/logo', file);
            App.toast('Logo atualizado!', 'success');
            document.getElementById('preview-logo').src = '/api/settings/logo?' + Date.now();
            App.loadBranding();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async uploadFavicon(file) {
        try {
            await API.upload('/api/settings/favicon', file);
            App.toast('Favicon atualizado!', 'success');
            document.getElementById('preview-favicon').src = '/api/settings/favicon?' + Date.now();
            App.loadBranding();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async loadModels() {
        try {
            const data = await API.get('/api/settings/models');
            const select = document.getElementById('cfg-modelo-llm');
            const currentValue = select.value;

            select.innerHTML = data.models.map(m =>
                `<option value="${m}" ${m === currentValue ? 'selected' : ''}>${m}</option>`
            ).join('');

            if (!data.models.length) {
                select.innerHTML = '<option value="llama3">llama3 (padrão)</option>';
            }
        } catch (err) {
            console.error('Erro ao carregar modelos:', err);
        }
    },
};
