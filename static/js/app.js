/**
 * علوم القرآن - Frontend JavaScript
 */

const API_BASE = '/api';

// Utility Functions
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) throw new Error('API Error');
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return null;
    }
}

function showLoading(container) {
    container.innerHTML = '<div class="loading">جارٍ التحميل...</div>';
}

function formatNumber(num) {
    return num.toLocaleString('ar-EG');
}

// ============================================================================
// Quran Functions
// ============================================================================

async function loadSurahVerses(surahId, container) {
    showLoading(container);
    const data = await fetchAPI(`/quran/surahs/${surahId}`);
    if (!data) {
        container.innerHTML = '<p>حدث خطأ في تحميل الآيات</p>';
        return;
    }

    let html = '';
    data.verses.forEach(verse => {
        html += `
            <div class="verse-item" data-verse-key="${verse.verse_key}" onclick="showVerseDetails('${verse.verse_key}')">
                <span class="verse-number">${verse.ayah_number}</span>
                <span class="verse-text">${verse.text_uthmani}</span>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function searchQuran(query) {
    const results = await fetchAPI(`/quran/search?q=${encodeURIComponent(query)}`);
    return results || [];
}

// ============================================================================
// Tafsir Functions
// ============================================================================

async function loadVerseTafsirs(verseKey, tafsirIds = null) {
    let endpoint = `/tafsir/verse/${verseKey}`;
    if (tafsirIds && tafsirIds.length > 0) {
        endpoint += `?tafsir_ids=${tafsirIds.join(',')}`;
    }
    return await fetchAPI(endpoint);
}

async function compareTafsirs(verseKey, tafsirIds) {
    if (!tafsirIds || tafsirIds.length < 2) {
        alert('الرجاء اختيار تفسيرين على الأقل للمقارنة');
        return null;
    }
    return await fetchAPI(`/tafsir/compare/${verseKey}?tafsir_ids=${tafsirIds.join(',')}`);
}

function renderTafsirComparison(data, container) {
    if (!data) {
        container.innerHTML = '<p>حدث خطأ في تحميل التفاسير</p>';
        return;
    }

    let html = `
        <div class="card mb-3">
            <div class="verse-text text-center" style="padding: 1.5rem; background: rgba(26, 95, 74, 0.05); border-radius: 10px;">
                ${data.verse.text_uthmani}
            </div>
            <p class="text-center mt-2" style="color: var(--text-light);">
                ${data.verse.surah_name} - الآية ${data.verse.verse_key.split(':')[1]}
            </p>
        </div>
        <div class="comparison-grid">
    `;

    data.comparisons.forEach(tafsir => {
        html += `
            <div class="tafsir-item">
                <div class="tafsir-header">
                    <span class="tafsir-name">${tafsir.tafsir_name}</span>
                    <span class="tafsir-author">${tafsir.author_arabic}</span>
                </div>
                <div class="tafsir-text">${tafsir.text_arabic}</div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

// ============================================================================
// Qiraat Functions
// ============================================================================

async function loadVerseQiraat(verseKey) {
    return await fetchAPI(`/qiraat/verse/${verseKey}`);
}

async function loadSurahQiraat(surahId) {
    return await fetchAPI(`/qiraat/surah/${surahId}`);
}

function renderQiraatDifferences(data, container) {
    if (!data || !data.variants || data.variants.length === 0) {
        container.innerHTML = '<p class="text-center" style="padding: 2rem; color: var(--text-light);">لا توجد فروق في القراءات لهذه الآية</p>';
        return;
    }

    let html = `
        <div class="card mb-3">
            <div class="verse-text text-center" style="padding: 1.5rem; background: rgba(26, 95, 74, 0.05); border-radius: 10px;">
                ${data.verse.text_uthmani}
            </div>
            <p class="text-center mt-2" style="color: var(--text-light);">
                ${data.verse.surah_name} - الآية ${data.verse.verse_key.split(':')[1]}
            </p>
        </div>
    `;

    data.variants.forEach(variant => {
        html += `
            <div class="qiraat-item">
                <div class="qiraat-word">${variant.word_text}</div>
                <div class="readings-list">
        `;

        variant.readings.forEach(reading => {
            html += `
                <div class="reading-item">
                    <span class="reader-name">${reading.qari_name}</span>
                    <span class="reading-text">${reading.reading_text}</span>
                </div>
            `;
        });

        html += '</div></div>';
    });

    container.innerHTML = html;
}

// ============================================================================
// Asbab Functions
// ============================================================================

async function loadVerseAsbab(verseKey) {
    return await fetchAPI(`/asbab/verse/${verseKey}`);
}

async function loadSurahAsbab(surahId) {
    return await fetchAPI(`/asbab/surah/${surahId}`);
}

function renderAsbab(data, container) {
    if (!data || !data.asbab || data.asbab.length === 0) {
        container.innerHTML = '<p class="text-center" style="padding: 2rem; color: var(--text-light);">لا توجد أسباب نزول مسجلة لهذه الآية</p>';
        return;
    }

    let html = `
        <div class="card mb-3">
            <div class="verse-text text-center" style="padding: 1.5rem; background: rgba(26, 95, 74, 0.05); border-radius: 10px;">
                ${data.verse.text_uthmani}
            </div>
            <p class="text-center mt-2" style="color: var(--text-light);">
                ${data.verse.surah_name} - الآية ${data.verse.verse_key.split(':')[1]}
            </p>
        </div>
    `;

    data.asbab.forEach(sabab => {
        html += `
            <div class="asbab-item">
                <div class="asbab-text">${sabab.text_arabic}</div>
                <div class="asbab-meta">
                    ${sabab.source_name ? `<span>المصدر: ${sabab.source_name}</span>` : ''}
                    ${sabab.grading ? `<span>الدرجة: ${sabab.grading}</span>` : ''}
                    ${sabab.context_period ? `<span>الفترة: ${sabab.context_period}</span>` : ''}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// ============================================================================
// Verse Details Modal/Panel
// ============================================================================

async function showVerseDetails(verseKey) {
    // Get or create modal
    let modal = document.getElementById('verse-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'verse-modal';
        modal.className = 'verse-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>تفاصيل الآية</h3>
                    <button onclick="closeVerseModal()" class="close-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="tabs">
                        <button class="tab active" data-tab="tafsir">التفسير</button>
                        <button class="tab" data-tab="qiraat">القراءات</button>
                        <button class="tab" data-tab="asbab">أسباب النزول</button>
                    </div>
                    <div id="tab-content"></div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Add modal styles
        const style = document.createElement('style');
        style.textContent = `
            .verse-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 2000;
            }
            .modal-content {
                background: white;
                border-radius: 16px;
                width: 90%;
                max-width: 900px;
                max-height: 85vh;
                overflow: hidden;
                display: flex;
                flex-direction: column;
            }
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1.5rem;
                background: var(--primary-color);
                color: white;
            }
            .modal-header h3 {
                margin: 0;
                color: white;
            }
            .close-btn {
                background: none;
                border: none;
                color: white;
                font-size: 2rem;
                cursor: pointer;
                line-height: 1;
            }
            .modal-body {
                padding: 1.5rem;
                overflow-y: auto;
                flex: 1;
            }
        `;
        document.head.appendChild(style);

        // Tab click handlers
        modal.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', async () => {
                modal.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                await loadTabContent(verseKey, tab.dataset.tab);
            });
        });
    }

    modal.style.display = 'flex';
    modal.dataset.verseKey = verseKey;

    // Load tafsir by default
    await loadTabContent(verseKey, 'tafsir');
}

async function loadTabContent(verseKey, tabName) {
    const container = document.getElementById('tab-content');
    showLoading(container);

    switch (tabName) {
        case 'tafsir':
            const tafsirData = await loadVerseTafsirs(verseKey);
            if (tafsirData) {
                let html = `
                    <div class="card mb-3">
                        <div class="verse-text text-center" style="padding: 1rem;">
                            ${tafsirData.verse.text_uthmani}
                        </div>
                    </div>
                `;
                tafsirData.tafsirs.forEach(tafsir => {
                    html += `
                        <div class="tafsir-item">
                            <div class="tafsir-header">
                                <span class="tafsir-name">${tafsir.tafsir_name}</span>
                                <span class="tafsir-author">${tafsir.author_arabic}</span>
                            </div>
                            <div class="tafsir-text">${tafsir.text_arabic}</div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
            break;

        case 'qiraat':
            const qiraatData = await loadVerseQiraat(verseKey);
            renderQiraatDifferences(qiraatData, container);
            break;

        case 'asbab':
            const asbabData = await loadVerseAsbab(verseKey);
            renderAsbab(asbabData, container);
            break;
    }
}

function closeVerseModal() {
    const modal = document.getElementById('verse-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeVerseModal();
});

// ============================================================================
// Initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('علوم القرآن - App Initialized');
});
