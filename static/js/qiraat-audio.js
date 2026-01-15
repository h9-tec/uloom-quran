/**
 * Qiraat Audio Player - Audio functionality for Qiraat pages
 * Provides audio playback for different reciters and riwayat
 */

class QiraatAudioPlayer {
    constructor() {
        this.currentAudio = null;
        this.currentPlayingId = null;
        this.reciters = [];
        this.selectedReciter = null;
        this.playMode = 'verse'; // 'verse' or 'surah'
        this.playlist = [];
        this.playlistIndex = 0;
        this.isPlaying = false;

        // Riwayat configuration with audio mapping
        this.riwayat = [
            { code: 'hafs', name: 'حفص', narrator: 'عن عاصم', number: '١' },
            { code: 'warsh', name: 'ورش', narrator: 'عن نافع', number: '٢' },
            { code: 'qaloon', name: 'قالون', narrator: 'عن نافع', number: '٣' },
            { code: 'shuba', name: 'شعبة', narrator: 'عن عاصم', number: '٤' },
            { code: 'doori', name: 'الدوري', narrator: 'عن أبي عمرو', number: '٥' },
            { code: 'soosi', name: 'السوسي', narrator: 'عن أبي عمرو', number: '٦' },
            { code: 'bazzi', name: 'البزي', narrator: 'عن ابن كثير', number: '٧' },
            { code: 'qunbul', name: 'قنبل', narrator: 'عن ابن كثير', number: '٨' }
        ];

        // Known reciter audio folders (everyayah.com compatible)
        this.reciterFolders = {
            'hafs': {
                'Abdul_Basit_Murattal': 'Abdul_Basit_Murattal_64kbps',
                'Abdul_Basit_Mujawwad': 'Abdul_Basit_Mujawwad_128kbps',
                'Mishary_Rashid_Alafasy': 'Alafasy_128kbps',
                'Mahmoud_Khalil_Al-Husary': 'Husary_128kbps',
                'Al-Minshawi_Murattal': 'Minshawy_Murattal_128kbps',
                'Al-Minshawi_Mujawwad': 'Minshawi_Mujawwad_64kbps',
                'Saad_Al-Ghamdi': 'Ghamadi_40kbps',
                'Muhammad_Ayyub': 'Muhammad_Ayyoub_128kbps',
                'Hani_Al-Rifai': 'Rifai_64kbps',
                'Maher_Al-Muaiqly': 'MauroMuaiqly_128kbps'
            },
            'warsh': {
                'Ibrahim_Al-Dosari': 'warsh/warsh_ibrahim_aldosary_128kbps',
                'Khalil_Al-Husary': 'warsh/warsh_Husary_128kbps'
            },
            'qaloon': {
                'Mohamed_Jibril': 'Qaloon/Qaloon_Jibril_128kbps'
            }
        };

        this.defaultRecitersByRiwaya = {
            'hafs': 'Abdul_Basit_Murattal',
            'warsh': 'Ibrahim_Al-Dosari',
            'qaloon': 'Mohamed_Jibril',
            'shuba': 'Abdul_Basit_Murattal',
            'doori': 'Abdul_Basit_Murattal',
            'soosi': 'Abdul_Basit_Murattal',
            'bazzi': 'Abdul_Basit_Murattal',
            'qunbul': 'Abdul_Basit_Murattal'
        };
    }

    /**
     * Initialize the audio player
     */
    async init() {
        await this.loadReciters();
        this.setupEventListeners();
    }

    /**
     * Load available reciters from API
     */
    async loadReciters() {
        try {
            const response = await fetch('/api/qiraat/audio/reciters');
            if (response.ok) {
                const data = await response.json();
                this.reciters = data.reciters || [];
            }
        } catch (error) {
            console.log('Using default reciter configuration');
            // Use built-in reciter list if API fails
            this.reciters = this.getDefaultReciters();
        }
    }

    /**
     * Get default reciters list
     */
    getDefaultReciters() {
        return [
            { id: 1, name_arabic: 'عبد الباسط عبد الصمد - مرتل', name_english: 'Abdul Basit Murattal', riwaya: 'hafs', folder: 'Abdul_Basit_Murattal_64kbps' },
            { id: 2, name_arabic: 'عبد الباسط عبد الصمد - مجود', name_english: 'Abdul Basit Mujawwad', riwaya: 'hafs', folder: 'Abdul_Basit_Mujawwad_128kbps' },
            { id: 3, name_arabic: 'مشاري راشد العفاسي', name_english: 'Mishary Rashid Alafasy', riwaya: 'hafs', folder: 'Alafasy_128kbps' },
            { id: 4, name_arabic: 'محمود خليل الحصري', name_english: 'Mahmoud Khalil Al-Husary', riwaya: 'hafs', folder: 'Husary_128kbps' },
            { id: 5, name_arabic: 'المنشاوي - مرتل', name_english: 'Al-Minshawi Murattal', riwaya: 'hafs', folder: 'Minshawy_Murattal_128kbps' },
            { id: 6, name_arabic: 'سعد الغامدي', name_english: 'Saad Al-Ghamdi', riwaya: 'hafs', folder: 'Ghamadi_40kbps' },
            { id: 7, name_arabic: 'إبراهيم الدوسري - ورش', name_english: 'Ibrahim Al-Dosari Warsh', riwaya: 'warsh', folder: 'warsh/warsh_ibrahim_aldosary_128kbps' },
            { id: 8, name_arabic: 'الحصري - ورش', name_english: 'Al-Husary Warsh', riwaya: 'warsh', folder: 'warsh/warsh_Husary_128kbps' }
        ];
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Listen for keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch(e.key) {
                case ' ':
                    e.preventDefault();
                    this.togglePlayPause();
                    break;
                case 'ArrowLeft':
                    if (this.playMode === 'surah') {
                        this.playNext();
                    }
                    break;
                case 'ArrowRight':
                    if (this.playMode === 'surah') {
                        this.playPrevious();
                    }
                    break;
            }
        });
    }

    /**
     * Build audio URL for a verse
     */
    getAudioUrl(surahId, ayahNumber, reciterFolder) {
        const paddedSurah = String(surahId).padStart(3, '0');
        const paddedAyah = String(ayahNumber).padStart(3, '0');
        return `https://everyayah.com/data/${reciterFolder}/${paddedSurah}${paddedAyah}.mp3`;
    }

    /**
     * Play audio for a specific verse
     */
    playVerse(surahId, ayahNumber, riwayaCode = 'hafs', reciterKey = null) {
        // Stop current audio if playing
        this.stopAudio();

        // Get reciter folder
        let folder;
        if (reciterKey && this.reciterFolders[riwayaCode] && this.reciterFolders[riwayaCode][reciterKey]) {
            folder = this.reciterFolders[riwayaCode][reciterKey];
        } else {
            // Use default for this riwaya
            const defaultReciter = this.defaultRecitersByRiwaya[riwayaCode];
            folder = this.reciterFolders[riwayaCode]?.[defaultReciter] ||
                     this.reciterFolders['hafs']['Abdul_Basit_Murattal'];
        }

        const audioUrl = this.getAudioUrl(surahId, ayahNumber, folder);

        this.currentAudio = new Audio(audioUrl);
        this.currentPlayingId = `${surahId}:${ayahNumber}`;
        this.isPlaying = true;

        this.currentAudio.onplay = () => {
            this.updatePlayingState(true);
        };

        this.currentAudio.onended = () => {
            this.isPlaying = false;
            this.updatePlayingState(false);

            // If in surah mode, play next verse
            if (this.playMode === 'surah' && this.playlist.length > 0) {
                this.playNext();
            }
        };

        this.currentAudio.onerror = () => {
            console.log('Audio not available for this recitation');
            this.isPlaying = false;
            this.updatePlayingState(false);
            this.showError('التسجيل الصوتي غير متاح لهذه القراءة');
        };

        this.currentAudio.play().catch(err => {
            console.log('Could not play audio:', err);
            this.showError('حدث خطأ في تشغيل الصوت');
        });

        return this.currentAudio;
    }

    /**
     * Play full surah
     */
    async playSurah(surahId, riwayaCode = 'hafs', reciterKey = null, startAyah = 1) {
        this.playMode = 'surah';

        // Build playlist
        try {
            const response = await fetch(`/api/qiraat/audio/surah/${surahId}`);
            if (response.ok) {
                const data = await response.json();
                const totalAyahs = data.total_ayahs || this.getSurahAyahCount(surahId);

                this.playlist = [];
                for (let i = startAyah; i <= totalAyahs; i++) {
                    this.playlist.push({
                        surahId: surahId,
                        ayahNumber: i
                    });
                }

                this.playlistIndex = 0;
                this.selectedReciter = reciterKey;
                this.playCurrentInPlaylist(riwayaCode, reciterKey);
            }
        } catch (error) {
            // Fallback: use local ayah count
            const totalAyahs = this.getSurahAyahCount(surahId);

            this.playlist = [];
            for (let i = startAyah; i <= totalAyahs; i++) {
                this.playlist.push({
                    surahId: surahId,
                    ayahNumber: i
                });
            }

            this.playlistIndex = 0;
            this.selectedReciter = reciterKey;
            this.playCurrentInPlaylist(riwayaCode, reciterKey);
        }
    }

    /**
     * Play current item in playlist
     */
    playCurrentInPlaylist(riwayaCode, reciterKey) {
        if (this.playlistIndex >= 0 && this.playlistIndex < this.playlist.length) {
            const item = this.playlist[this.playlistIndex];
            this.playVerse(item.surahId, item.ayahNumber, riwayaCode, reciterKey);
            this.updatePlaylistUI();
        }
    }

    /**
     * Play next in playlist
     */
    playNext() {
        if (this.playlistIndex < this.playlist.length - 1) {
            this.playlistIndex++;
            const riwayaCode = this.getCurrentRiwayaCode();
            this.playCurrentInPlaylist(riwayaCode, this.selectedReciter);
        } else {
            this.isPlaying = false;
            this.updatePlayingState(false);
        }
    }

    /**
     * Play previous in playlist
     */
    playPrevious() {
        if (this.playlistIndex > 0) {
            this.playlistIndex--;
            const riwayaCode = this.getCurrentRiwayaCode();
            this.playCurrentInPlaylist(riwayaCode, this.selectedReciter);
        }
    }

    /**
     * Stop audio playback
     */
    stopAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
        this.isPlaying = false;
        this.updatePlayingState(false);
    }

    /**
     * Toggle play/pause
     */
    togglePlayPause() {
        if (this.currentAudio) {
            if (this.isPlaying) {
                this.currentAudio.pause();
                this.isPlaying = false;
            } else {
                this.currentAudio.play();
                this.isPlaying = true;
            }
            this.updatePlayingState(this.isPlaying);
        }
    }

    /**
     * Update UI to reflect playing state
     */
    updatePlayingState(isPlaying) {
        // Update all play buttons
        document.querySelectorAll('.audio-play-btn, .audio-btn, .audio-item-icon').forEach(btn => {
            if (btn.dataset.verseKey === this.currentPlayingId) {
                btn.classList.toggle('playing', isPlaying);
                const icon = btn.querySelector('.play-icon, .audio-icon');
                if (icon) {
                    icon.textContent = isPlaying ? '\u275A\u275A' : '\u25B6';
                }
            } else {
                btn.classList.remove('playing');
                const icon = btn.querySelector('.play-icon, .audio-icon');
                if (icon) {
                    icon.textContent = '\u25B6';
                }
            }
        });

        // Update main player if exists
        const mainPlayBtn = document.getElementById('main-play-btn');
        if (mainPlayBtn) {
            mainPlayBtn.classList.toggle('playing', isPlaying);
            const icon = mainPlayBtn.querySelector('.play-icon');
            if (icon) {
                icon.textContent = isPlaying ? '\u275A\u275A' : '\u25B6';
            }
        }
    }

    /**
     * Update playlist UI
     */
    updatePlaylistUI() {
        const currentVerse = document.getElementById('current-verse-display');
        if (currentVerse && this.playlist[this.playlistIndex]) {
            const item = this.playlist[this.playlistIndex];
            currentVerse.textContent = `الآية ${item.ayahNumber}`;
        }

        // Highlight current playing verse
        document.querySelectorAll('.verse-item, .verse-row').forEach(el => {
            el.classList.remove('playing');
        });

        if (this.currentPlayingId) {
            const playingEl = document.querySelector(`[data-verse-key="${this.currentPlayingId}"]`);
            if (playingEl) {
                playingEl.classList.add('playing');
                playingEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    /**
     * Get current riwaya code
     */
    getCurrentRiwayaCode() {
        const select = document.getElementById('riwaya-select');
        return select ? select.value : 'hafs';
    }

    /**
     * Get surah ayah count
     */
    getSurahAyahCount(surahId) {
        const counts = {
            1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
            11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
            21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
            31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
            41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45,
            51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
            61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
            71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
            81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
            91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
            101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3,
            111: 5, 112: 4, 113: 5, 114: 6
        };
        return counts[surahId] || 0;
    }

    /**
     * Show error message
     */
    showError(message) {
        const toast = document.createElement('div');
        toast.className = 'audio-toast error';
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
        }, 100);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Get reciters for a specific riwaya
     */
    getRecitersForRiwaya(riwayaCode) {
        return this.reciters.filter(r => r.riwaya === riwayaCode);
    }

    /**
     * Create reciter dropdown HTML
     */
    createReciterDropdown(riwayaCode, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const recitersForRiwaya = this.getRecitersForRiwaya(riwayaCode);

        if (recitersForRiwaya.length === 0) {
            // Use default reciters for hafs
            const defaultReciters = this.getDefaultReciters().filter(r => r.riwaya === 'hafs');
            recitersForRiwaya.push(...defaultReciters);
        }

        let html = `
            <select id="reciter-select" class="styled-select reciter-dropdown">
                <option value="">اختر القارئ...</option>
        `;

        recitersForRiwaya.forEach(reciter => {
            html += `<option value="${reciter.folder || reciter.id}">${reciter.name_arabic}</option>`;
        });

        html += '</select>';
        container.innerHTML = html;
    }

    /**
     * Render audio player component
     */
    renderAudioPlayer(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const {
            surahId = null,
            verseKey = null,
            riwayaCode = 'hafs',
            showReciterSelect = true,
            showPlayModeToggle = true,
            compact = false
        } = options;

        const html = `
            <div class="qiraat-audio-player ${compact ? 'compact' : ''}">
                <div class="audio-player-header">
                    <h3 class="audio-player-title">
                        <span class="audio-icon-title">&#9836;</span>
                        الاستماع للتلاوة
                    </h3>
                </div>

                <div class="audio-player-controls">
                    ${showReciterSelect ? `
                        <div class="control-group">
                            <label>القارئ</label>
                            <div id="reciter-dropdown-container"></div>
                        </div>
                    ` : ''}

                    ${showPlayModeToggle ? `
                        <div class="control-group">
                            <label>نوع التشغيل</label>
                            <div class="play-mode-toggle">
                                <button class="mode-btn active" data-mode="verse" onclick="qiraatAudioPlayer.setPlayMode('verse')">
                                    آية واحدة
                                </button>
                                <button class="mode-btn" data-mode="surah" onclick="qiraatAudioPlayer.setPlayMode('surah')">
                                    السورة كاملة
                                </button>
                            </div>
                        </div>
                    ` : ''}
                </div>

                <div class="audio-player-main">
                    <button class="main-audio-btn" id="main-play-btn" onclick="qiraatAudioPlayer.handleMainPlayClick()">
                        <span class="play-icon">&#9654;</span>
                    </button>

                    <div class="audio-info">
                        <div class="audio-title" id="current-verse-display">
                            ${verseKey ? `الآية ${verseKey.split(':')[1]}` : 'اضغط للتشغيل'}
                        </div>
                        <div class="audio-progress">
                            <div class="progress-bar" id="audio-progress-bar">
                                <div class="progress-fill" id="audio-progress-fill"></div>
                            </div>
                            <span class="audio-time" id="audio-time">0:00</span>
                        </div>
                    </div>

                    ${!compact ? `
                        <div class="audio-actions">
                            <button class="audio-action-btn" onclick="qiraatAudioPlayer.playPrevious()" title="السابق">
                                &#9664;&#9664;
                            </button>
                            <button class="audio-action-btn" onclick="qiraatAudioPlayer.stopAudio()" title="إيقاف">
                                &#9632;
                            </button>
                            <button class="audio-action-btn" onclick="qiraatAudioPlayer.playNext()" title="التالي">
                                &#9654;&#9654;
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        container.innerHTML = html;

        // Initialize reciter dropdown
        if (showReciterSelect) {
            this.createReciterDropdown(riwayaCode, 'reciter-dropdown-container');
        }

        // Setup progress tracking
        this.setupProgressTracking();
    }

    /**
     * Setup audio progress tracking
     */
    setupProgressTracking() {
        setInterval(() => {
            if (this.currentAudio && !this.currentAudio.paused) {
                const progress = (this.currentAudio.currentTime / this.currentAudio.duration) * 100;
                const progressFill = document.getElementById('audio-progress-fill');
                const timeDisplay = document.getElementById('audio-time');

                if (progressFill) {
                    progressFill.style.width = `${progress}%`;
                }

                if (timeDisplay) {
                    const current = this.formatTime(this.currentAudio.currentTime);
                    const total = this.formatTime(this.currentAudio.duration);
                    timeDisplay.textContent = `${current} / ${total}`;
                }
            }
        }, 100);
    }

    /**
     * Format time in mm:ss
     */
    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Set play mode
     */
    setPlayMode(mode) {
        this.playMode = mode;

        // Update UI
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
    }

    /**
     * Handle main play button click
     */
    handleMainPlayClick() {
        if (this.isPlaying) {
            this.togglePlayPause();
        } else {
            // Get current context from page
            const surahSelect = document.getElementById('surah-select');
            const verseSelect = document.getElementById('verse-select');
            const reciterSelect = document.getElementById('reciter-select');
            const riwayaSelect = document.getElementById('riwaya-select');

            const surahId = surahSelect ? parseInt(surahSelect.value) : 1;
            const verseKey = verseSelect ? verseSelect.value : null;
            const reciterFolder = reciterSelect ? reciterSelect.value : null;
            const riwayaCode = riwayaSelect ? riwayaSelect.value : 'hafs';

            if (this.playMode === 'surah') {
                const startAyah = verseKey ? parseInt(verseKey.split(':')[1]) : 1;
                this.playSurah(surahId, riwayaCode, reciterFolder, startAyah);
            } else {
                const ayahNumber = verseKey ? parseInt(verseKey.split(':')[1]) : 1;
                this.playVerse(surahId, ayahNumber, riwayaCode, reciterFolder);
            }
        }
    }
}

// Styles for the audio player
const audioPlayerStyles = `
<style>
/* Audio Player Styles */
.qiraat-audio-player {
    background: white;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    margin-bottom: 24px;
}

.qiraat-audio-player.compact {
    padding: 16px;
}

.audio-player-header {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.audio-player-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--primary-color, #1a5f4a);
    margin: 0;
    font-size: 1.3rem;
}

.audio-icon-title {
    font-size: 1.5rem;
}

.audio-player-controls {
    display: flex;
    gap: 20px;
    margin-bottom: 24px;
    flex-wrap: wrap;
}

.control-group {
    flex: 1;
    min-width: 200px;
}

.control-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: bold;
    color: var(--primary-color, #1a5f4a);
    font-size: 0.95rem;
}

.reciter-dropdown {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid var(--border-color, #e0e0e0);
    border-radius: 10px;
    font-size: 15px;
    font-family: inherit;
    background: white;
    cursor: pointer;
    transition: all 0.2s ease;
}

.reciter-dropdown:focus {
    outline: none;
    border-color: var(--primary-color, #1a5f4a);
    box-shadow: 0 0 0 3px rgba(26, 95, 74, 0.1);
}

.play-mode-toggle {
    display: flex;
    border-radius: 10px;
    overflow: hidden;
    border: 2px solid var(--border-color, #e0e0e0);
}

.mode-btn {
    flex: 1;
    padding: 12px 16px;
    border: none;
    background: white;
    color: var(--text-color, #333);
    font-family: inherit;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.mode-btn:first-child {
    border-left: 1px solid var(--border-color, #e0e0e0);
}

.mode-btn.active {
    background: var(--primary-color, #1a5f4a);
    color: white;
}

.mode-btn:hover:not(.active) {
    background: rgba(26, 95, 74, 0.1);
}

.audio-player-main {
    display: flex;
    align-items: center;
    gap: 20px;
    background: linear-gradient(135deg, #f8f9fa, #ffffff);
    padding: 20px;
    border-radius: 12px;
}

.main-audio-btn {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--primary-color, #1a5f4a), #2d7a5e);
    color: white;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s ease;
    flex-shrink: 0;
}

.main-audio-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(26, 95, 74, 0.3);
}

.main-audio-btn.playing {
    background: linear-gradient(135deg, var(--secondary-color, #c9a227), #d4b632);
    animation: pulse-play 1.5s ease-in-out infinite;
}

@keyframes pulse-play {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}

.main-audio-btn .play-icon {
    font-size: 1.5rem;
}

.audio-info {
    flex: 1;
}

.audio-title {
    font-weight: bold;
    color: var(--primary-dark, #0d4030);
    margin-bottom: 10px;
    font-size: 1.1rem;
}

.audio-progress {
    display: flex;
    align-items: center;
    gap: 12px;
}

.progress-bar {
    flex: 1;
    height: 8px;
    background: #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary-color, #1a5f4a), var(--secondary-color, #c9a227));
    border-radius: 4px;
    width: 0;
    transition: width 0.1s linear;
}

.audio-time {
    font-size: 0.9rem;
    color: var(--text-light, #666);
    min-width: 80px;
    text-align: left;
}

.audio-actions {
    display: flex;
    gap: 8px;
}

.audio-action-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(26, 95, 74, 0.1);
    border: none;
    color: var(--primary-color, #1a5f4a);
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 0.9rem;
}

.audio-action-btn:hover {
    background: var(--primary-color, #1a5f4a);
    color: white;
}

/* Toast notifications */
.audio-toast {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #333;
    color: white;
    padding: 12px 24px;
    border-radius: 8px;
    z-index: 10000;
    opacity: 0;
    transition: all 0.3s ease;
}

.audio-toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}

.audio-toast.error {
    background: #c0392b;
}

/* Riwaya Audio Grid */
.riwaya-audio-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-top: 20px;
}

@media (max-width: 1024px) {
    .riwaya-audio-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 600px) {
    .riwaya-audio-grid {
        grid-template-columns: 1fr;
    }
}

.riwaya-audio-card {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;
    border: 2px solid transparent;
}

.riwaya-audio-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
    border-color: var(--primary-color, #1a5f4a);
}

.riwaya-audio-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: linear-gradient(135deg, #f8f9fa, #ffffff);
    border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.riwaya-audio-number {
    width: 36px;
    height: 36px;
    background: var(--primary-color, #1a5f4a);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    flex-shrink: 0;
}

.riwaya-audio-info h4 {
    margin: 0 0 2px 0;
    color: var(--primary-dark, #0d4030);
    font-size: 1rem;
}

.riwaya-audio-info span {
    color: var(--text-light, #666);
    font-size: 0.85rem;
}

.riwaya-audio-body {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.riwaya-audio-select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
}

.riwaya-play-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px;
    background: linear-gradient(135deg, var(--primary-color, #1a5f4a), #2d7a5e);
    color: white;
    border: none;
    border-radius: 8px;
    font-family: inherit;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.riwaya-play-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(26, 95, 74, 0.3);
}

.riwaya-play-btn.playing {
    background: linear-gradient(135deg, var(--secondary-color, #c9a227), #d4b632);
}

/* Audio Comparison Section */
.audio-comparison-section {
    background: white;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.audio-comparison-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
}

.audio-comparison-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--primary-color, #1a5f4a);
    margin: 0;
}

.compare-controls {
    display: flex;
    gap: 10px;
}

.compare-btn {
    padding: 10px 20px;
    border: 2px solid var(--primary-color, #1a5f4a);
    background: white;
    color: var(--primary-color, #1a5f4a);
    border-radius: 8px;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.2s ease;
}

.compare-btn:hover, .compare-btn.active {
    background: var(--primary-color, #1a5f4a);
    color: white;
}

.audio-comparison-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}

@media (max-width: 768px) {
    .audio-comparison-grid {
        grid-template-columns: 1fr;
    }
}

.comparison-player {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 12px;
}

.comparison-player-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}

.comparison-player-label {
    background: var(--primary-color, #1a5f4a);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: bold;
}

.comparison-player-name {
    font-weight: bold;
    color: var(--primary-dark, #0d4030);
}

/* Verse playing indicator */
.verse-item.playing,
.verse-row.playing {
    background: rgba(201, 162, 39, 0.1) !important;
    border-right: 4px solid var(--secondary-color, #c9a227);
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .audio-player-controls {
        flex-direction: column;
    }

    .audio-player-main {
        flex-direction: column;
        text-align: center;
    }

    .audio-actions {
        width: 100%;
        justify-content: center;
        margin-top: 12px;
    }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', audioPlayerStyles);

// Create global instance
const qiraatAudioPlayer = new QiraatAudioPlayer();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    qiraatAudioPlayer.init();
});
