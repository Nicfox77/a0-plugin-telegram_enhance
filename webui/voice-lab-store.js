import { createStore } from "/js/AlpineStore.js";

const API_BASE = "/api/plugins/telegram_enhance";

export const store = createStore("voiceLabStore", {
    // State
    voices: [],          // All available voice names from npz
    savedBlends: [],     // Saved blend recipes [{name, voices, display_name}]
    selectedVoices: [],  // Active blend editor [{name, weight}]
    sampleText: "Hey there! This is a quick test of my custom voice blend. How does it sound?",
    speed: 1.1,
    generatedAudio: null,   // base64 audio data
    audioFormat: "mp3",
    audioDuration: 0,
    isGenerating: false,
    isSaving: false,
    saveName: "",
    errorMsg: "",
    loaded: false,
    audioElement: null,
    searchQuery: "",

    onOpen() {
        this.loadVoices();
    },

    cleanup() {
        this.voices = [];
        this.savedBlends = [];
        this.selectedVoices = [];
        this.generatedAudio = null;
        this.audioFormat = "mp3";
        this.audioDuration = 0;
        this.isGenerating = false;
        this.isSaving = false;
        this.saveName = "";
        this.errorMsg = "";
        this.loaded = false;
        this.searchQuery = "";
        this._stopAudio();
    },

    _stopAudio() {
        if (this.audioElement) {
            this.audioElement.pause();
            this.audioElement = null;
        }
    },

    async loadVoices() {
        try {
            const resp = await fetch(`${API_BASE}/list_voices`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            if (resp.ok) {
                const data = await resp.json();
                this.voices = data.voices || [];
                this.savedBlends = data.saved_blends || [];
            }
        } catch (e) {
            console.error("Failed to load voices:", e);
            this.errorMsg = "Failed to load voices";
        }
        this.loaded = true;
    },

    // Voice classification helpers
    _voiceGender(name) {
        if (name.startsWith("af_") || name.startsWith("bf_") || name.startsWith("jf_") || name.startsWith("hf_") || name.startsWith("pf_") || name.startsWith("zf_")) return "female";
        if (name.startsWith("am_") || name.startsWith("bm_") || name.startsWith("jm_") || name.startsWith("hm_") || name.startsWith("pm_") || name.startsWith("zm_")) return "male";
        return "unknown";
    },

    _voiceLang(name) {
        const prefix = name.substring(0, 2);
        const langs = {
            af: "American English", am: "American English",
            bf: "British English", bm: "British English",
            jf: "Japanese", jm: "Japanese",
            hf: "Hindi", hm: "Hindi",
            pf: "Portuguese", pm: "Portuguese",
            zf: "Mandarin Chinese", zm: "Mandarin Chinese",
            if: "Indonesian", im: "Indonesian",
            ef: "Spanish", em: "Spanish",
            ff: "French", fm: "French",
        };
        return langs[prefix] || "Unknown";
    },

    _voiceDesc(name) {
        const gender = this._voiceGender(name);
        const lang = this._voiceLang(name);
        const short = name.substring(3);
        return `${short} (${gender}, ${lang})`;
    },

    get filteredVoices() {
        if (!this.searchQuery) return this.voices;
        const q = this.searchQuery.toLowerCase();
        return this.voices.filter(v => v.toLowerCase().includes(q) || this._voiceDesc(v).toLowerCase().includes(q));
    },

    // Blend editor operations
    addVoice(name) {
        if (this.selectedVoices.some(v => v.name === name)) return;
        const count = this.selectedVoices.length + 1;
        const weight = Math.round(100 / count);
        this.selectedVoices.push({ name, weight });
        // Redistribute evenly
        this._redistributeEven();
    },

    removeVoice(index) {
        this.selectedVoices.splice(index, 1);
        this._normalizeWeights();
    },

    updateWeight(index, newWeight) {
        newWeight = Math.max(0, Math.min(100, parseInt(newWeight) || 0));
        const oldWeight = this.selectedVoices[index].weight;
        const diff = newWeight - oldWeight;
        this.selectedVoices[index].weight = newWeight;

        // Proportionally adjust other weights
        const others = this.selectedVoices.filter((_, i) => i !== index);
        const othersTotal = others.reduce((s, v) => s + v.weight, 0);
        if (othersTotal > 0 && diff !== 0) {
            const scale = Math.max(0, othersTotal - diff) / othersTotal;
            others.forEach(v => {
                v.weight = Math.round(v.weight * scale);
            });
        }
        this._normalizeWeights();
    },

    _normalizeWeights() {
        const total = this.selectedVoices.reduce((s, v) => s + v.weight, 0);
        if (total > 0 && total !== 100) {
            const scale = 100 / total;
            let remaining = 100;
            this.selectedVoices.forEach((v, i) => {
                if (i === this.selectedVoices.length - 1) {
                    v.weight = remaining;
                } else {
                    v.weight = Math.round(v.weight * scale);
                    remaining -= v.weight;
                }
            });
        }
    },

    _redistributeEven() {
        if (this.selectedVoices.length === 0) return;
        const each = Math.floor(100 / this.selectedVoices.length);
        let remainder = 100 - each * this.selectedVoices.length;
        this.selectedVoices.forEach((v, i) => {
            v.weight = each + (i < remainder ? 1 : 0);
        });
    },

    isSelected(name) {
        return this.selectedVoices.some(v => v.name === name);
    },

    get totalWeight() {
        return this.selectedVoices.reduce((s, v) => s + v.weight, 0);
    },

    get weightStatus() {
        const t = this.totalWeight;
        if (t === 100) return "ok";
        if (t > 100) return "over";
        return "under";
    },

    // Load a saved blend recipe into the editor
    loadBlend(blend) {
        this.selectedVoices = blend.voices.map(v => ({ name: v.name, weight: v.weight }));
        this._normalizeWeights();
    },

    // Generate audio sample
    async generateSample() {
        if (this.selectedVoices.length === 0) {
            this.errorMsg = "Add at least one voice to the blend";
            return;
        }
        if (!this.sampleText.trim()) {
            this.errorMsg = "Enter some text to speak";
            return;
        }

        this._stopAudio();
        this.isGenerating = true;
        this.errorMsg = "";
        this.generatedAudio = null;

        try {
            const resp = await fetch(`${API_BASE}/generate_sample`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    voices: this.selectedVoices.map(v => ({ name: v.name, weight: v.weight })),
                    text: this.sampleText,
                    speed: this.speed,
                }),
            });
            const data = await resp.json();
            if (data.error) {
                this.errorMsg = data.error;
            } else {
                this.generatedAudio = data.audio;
                this.audioFormat = data.format || "mp3";
                this.audioDuration = data.duration || 0;
            }
        } catch (e) {
            this.errorMsg = "Failed to generate audio: " + e.message;
        }
        this.isGenerating = false;
    },

    playAudio() {
        if (!this.generatedAudio) return;
        this._stopAudio();
        const mime = this.audioFormat === "mp3" ? "audio/mpeg" : "audio/wav";
        const audio = new Audio(`data:${mime};base64,${this.generatedAudio}`);
        this.audioElement = audio;
        audio.play().catch(e => {
            console.error("Audio play error:", e);
            this.errorMsg = "Failed to play audio";
        });
    },

    stopPlayback() {
        this._stopAudio();
    },

    // Save blend
    async saveBlend() {
        if (this.selectedVoices.length === 0) return;
        const name = this.saveName.trim();
        if (!name) {
            this.errorMsg = "Enter a name for the blend";
            return;
        }

        this.isSaving = true;
        this.errorMsg = "";

        try {
            const resp = await fetch(`${API_BASE}/save_blend`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: name,
                    voices: this.selectedVoices.map(v => ({ name: v.name, weight: v.weight })),
                }),
            });
            const data = await resp.json();
            if (data.error) {
                this.errorMsg = data.error;
            } else {
                window.toastFrontendSuccess?.(`Blend "${data.name}" saved!`);
                this.saveName = "";
                // Reload voices and blends
                await this.loadVoices();
            }
        } catch (e) {
            this.errorMsg = "Failed to save blend: " + e.message;
        }
        this.isSaving = false;
    },

    // Delete saved blend
    async deleteBlend(name) {
        try {
            const resp = await fetch(`${API_BASE}/delete_blend`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
            });
            const data = await resp.json();
            if (data.error) {
                this.errorMsg = data.error;
            } else {
                window.toastFrontendSuccess?.(`Blend "${name}" deleted`);
                await this.loadVoices();
            }
        } catch (e) {
            this.errorMsg = "Failed to delete blend: " + e.message;
        }
    },
});
