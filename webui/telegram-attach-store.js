import { createStore } from "/js/AlpineStore.js";

export const store = createStore("telegramAttachStore", {
    contextId: '',
    chatName: '',
    attachCommand: '',
    telegramLinked: false,
    linkedBotName: '',
    linkedUsername: '',
    activeSessions: [],
    allChats: [],
    showAllChats: false,
    detaching: false,
    loaded: false,

    onOpen() {
        this.contextId = (typeof globalThis !== 'undefined' && globalThis.getContext) ? globalThis.getContext() : '';
        this.loadChatName();
        this.checkLinkStatus();
        this.loadAllChats();
    },

    cleanup() {
        this.contextId = '';
        this.chatName = '';
        this.attachCommand = '';
        this.telegramLinked = false;
        this.linkedBotName = '';
        this.linkedUsername = '';
        this.loaded = false;
        this.activeSessions = [];
        this.allChats = [];
        this.showAllChats = false;
    },

    async loadChatName() {
        if (!this.contextId) return;
        try {
            const resp = await fetch('/api/plugins/telegram_enhance/list_chats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_context_id: this.contextId })
            });
            if (resp.ok) {
                const data = await resp.json();
                const current = (data.chats || []).find(c => c.id === this.contextId);
                if (current) {
                    this.chatName = current.name;
                    this.attachCommand = '/attach ' + current.name;
                }
            }
        } catch (e) {}
    },

    async checkLinkStatus() {
        if (!this.contextId) return;
        try {
            const resp = await fetch('/api/plugins/telegram_enhance/context_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ context_id: this.contextId })
            });
            if (resp.ok) {
                const data = await resp.json();
                this.telegramLinked = !!(data && data.linked);
                this.linkedBotName = data?.bot_name || '';
                this.linkedUsername = data?.telegram_username || '';
            }
        } catch (e) {}
        this.loaded = true;
    },

    async loadAllChats() {
        try {
            const resp = await fetch('/api/plugins/telegram_enhance/list_chats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_context_id: this.contextId })
            });
            if (resp.ok) {
                const data = await resp.json();
                this.allChats = data.chats || [];
                this.activeSessions = (data.chats || []).filter(c => c.linked && c.id !== this.contextId);
            }
        } catch (e) {}
    },

    async detachChat() {
        this.detaching = true;
        try {
            const resp = await fetch('/api/plugins/telegram_enhance/detach_chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ context_id: this.contextId })
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.success) {
                    this.telegramLinked = false;
                    this.linkedBotName = '';
                    this.loadAllChats();
                    window.toastFrontendSuccess?.('Detached from Telegram');
                } else {
                    window.toastFrontendError?.(data.error || 'Detach failed');
                }
            }
        } catch (e) {
            window.toastFrontendError?.('Detach request failed');
        }
        this.detaching = false;
    },

    async redirectSession(session) {
        try {
            const resp = await fetch('/api/plugins/telegram_enhance/attach_chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    context_id: this.contextId,
                    bot_name: session.telegram_bot,
                    user_id: session.telegram_user_id,
                    chat_id: session.telegram_chat_id,
                    username: session.telegram_username
                })
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.success) {
                    this.telegramLinked = true;
                    this.linkedBotName = session.telegram_bot;
                    this.linkedUsername = session.telegram_username;
                    this.loadAllChats();
                    window.toastFrontendSuccess?.('Telegram session redirected to this chat');
                } else {
                    window.toastFrontendError?.(data.error || 'Redirect failed');
                }
            }
        } catch (e) {
            window.toastFrontendError?.('Redirect request failed');
        }
    },

    copyText(text, label) {
        navigator.clipboard.writeText(text).then(() => {
            window.toastFrontendSuccess?.((label || 'Text') + ' copied!');
        }).catch(() => {
            const el = document.createElement('textarea');
            el.value = text;
            el.style.position = 'fixed';
            el.style.opacity = '0';
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
            window.toastFrontendSuccess?.((label || 'Text') + ' copied!');
        });
    }
});
