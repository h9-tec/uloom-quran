/**
 * Qiraat Comparison Component - مكوّن مقارنة القراءات
 * A reusable JavaScript widget for displaying and comparing Quranic readings (Qiraat)
 *
 * Usage:
 *   const widget = new QiraatCompare({
 *     container: document.getElementById('qiraat-container'),
 *     verseKey: '1:4',
 *     displayMode: 'stacked', // 'stacked' | 'side-by-side' | 'table'
 *     highlightDifferences: true,
 *     showReaderInfo: true
 *   });
 *   widget.render();
 */

class QiraatCompare {
    /**
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.container - Container element to render into
     * @param {string} options.verseKey - Verse key in format "surah:ayah" (e.g., "1:4")
     * @param {string} options.displayMode - Display mode: 'stacked', 'side-by-side', or 'table'
     * @param {boolean} options.highlightDifferences - Whether to highlight differences between readings
     * @param {boolean} options.showReaderInfo - Whether to show detailed reader information
     * @param {boolean} options.showModeToggle - Whether to show display mode toggle buttons
     * @param {string} options.apiBase - Base URL for API (default: '/api')
     * @param {Function} options.onLoad - Callback when data is loaded
     * @param {Function} options.onError - Callback when error occurs
     */
    constructor(options = {}) {
        this.container = options.container;
        this.verseKey = options.verseKey || null;
        this.displayMode = options.displayMode || 'stacked';
        this.highlightDifferences = options.highlightDifferences !== false;
        this.showReaderInfo = options.showReaderInfo !== false;
        this.showModeToggle = options.showModeToggle !== false;
        this.apiBase = options.apiBase || '/api';
        this.onLoad = options.onLoad || null;
        this.onError = options.onError || null;

        this.data = null;
        this.isLoading = false;
        this.error = null;

        // CSS class prefix to avoid conflicts
        this.cssPrefix = 'qc';

        // Ensure CSS is loaded
        this._ensureStyles();
    }

    /**
     * Set the verse key and optionally re-render
     * @param {string} verseKey - Verse key in format "surah:ayah"
     * @param {boolean} autoRender - Whether to automatically render after setting
     */
    setVerseKey(verseKey, autoRender = true) {
        this.verseKey = verseKey;
        this.data = null;
        this.error = null;
        if (autoRender && this.container) {
            this.render();
        }
    }

    /**
     * Set the display mode
     * @param {string} mode - 'stacked', 'side-by-side', or 'table'
     */
    setDisplayMode(mode) {
        if (['stacked', 'side-by-side', 'table'].includes(mode)) {
            this.displayMode = mode;
            if (this.data && this.container) {
                this._renderContent();
            }
        }
    }

    /**
     * Fetch qiraat data from API
     * @returns {Promise<Object>} Qiraat data
     */
    async fetchData() {
        if (!this.verseKey) {
            throw new Error('Verse key is required');
        }

        const response = await fetch(`${this.apiBase}/qiraat/verse/${this.verseKey}`);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error: ${response.status} - ${errorText}`);
        }

        return await response.json();
    }

    /**
     * Main render method
     */
    async render() {
        if (!this.container) {
            console.error('QiraatCompare: No container specified');
            return;
        }

        if (!this.verseKey) {
            this.container.innerHTML = this._renderEmptyState();
            return;
        }

        // Show loading state
        this.isLoading = true;
        this.container.innerHTML = this._renderLoading();

        try {
            this.data = await this.fetchData();
            this.error = null;
            this._renderContent();

            if (this.onLoad) {
                this.onLoad(this.data);
            }
        } catch (err) {
            this.error = err.message;
            this.container.innerHTML = this._renderError();

            if (this.onError) {
                this.onError(err);
            }
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Render the main content
     * @private
     */
    _renderContent() {
        const { verse, variants, has_differences } = this.data;

        let html = `<div class="${this.cssPrefix}-widget" dir="rtl">`;

        // Verse header
        html += this._renderVerseHeader(verse);

        // Mode toggle (if enabled)
        if (this.showModeToggle) {
            html += this._renderModeToggle();
        }

        // Content based on whether there are differences
        if (!has_differences || !variants || variants.length === 0) {
            html += this._renderNoDifferences();
        } else {
            html += this._renderVariants(variants);
        }

        html += '</div>';

        this.container.innerHTML = html;

        // Attach event listeners
        this._attachEventListeners();
    }

    /**
     * Render the verse header section
     * @private
     */
    _renderVerseHeader(verse) {
        return `
            <div class="${this.cssPrefix}-header">
                <div class="${this.cssPrefix}-verse-display">
                    <span class="${this.cssPrefix}-verse-text">${this._escapeHtml(verse.text_uthmani)}</span>
                </div>
                <div class="${this.cssPrefix}-verse-meta">
                    <span class="${this.cssPrefix}-surah-name">${this._escapeHtml(verse.surah_name)}</span>
                    <span class="${this.cssPrefix}-verse-key">${this._formatVerseKey(verse.verse_key)}</span>
                </div>
            </div>
        `;
    }

    /**
     * Render the display mode toggle buttons
     * @private
     */
    _renderModeToggle() {
        const modes = [
            { id: 'stacked', label: 'مكدس', icon: '&#9776;' },
            { id: 'side-by-side', label: 'جنبًا لجنب', icon: '&#9783;' },
            { id: 'table', label: 'جدول', icon: '&#9638;' }
        ];

        return `
            <div class="${this.cssPrefix}-controls">
                <div class="${this.cssPrefix}-mode-toggle">
                    ${modes.map(mode => `
                        <button
                            class="${this.cssPrefix}-mode-btn ${this.displayMode === mode.id ? `${this.cssPrefix}-mode-btn--active` : ''}"
                            data-mode="${mode.id}"
                            title="${mode.label}"
                        >
                            <span class="${this.cssPrefix}-mode-icon">${mode.icon}</span>
                            <span class="${this.cssPrefix}-mode-label">${mode.label}</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render the variants based on current display mode
     * @private
     */
    _renderVariants(variants) {
        let html = `<div class="${this.cssPrefix}-content ${this.cssPrefix}-mode-${this.displayMode}">`;

        switch (this.displayMode) {
            case 'side-by-side':
                html += this._renderSideBySide(variants);
                break;
            case 'table':
                html += this._renderTable(variants);
                break;
            case 'stacked':
            default:
                html += this._renderStacked(variants);
                break;
        }

        html += '</div>';
        return html;
    }

    /**
     * Render stacked view (default)
     * @private
     */
    _renderStacked(variants) {
        return variants.map((variant, index) => `
            <div class="${this.cssPrefix}-variant ${this.cssPrefix}-variant--stacked">
                <div class="${this.cssPrefix}-variant-header">
                    <span class="${this.cssPrefix}-variant-number">${index + 1}</span>
                    <span class="${this.cssPrefix}-variant-word">${this._escapeHtml(variant.word_text)}</span>
                    ${variant.variant_type ? `<span class="${this.cssPrefix}-variant-type">${this._escapeHtml(variant.variant_type)}</span>` : ''}
                </div>
                <div class="${this.cssPrefix}-readings-stacked">
                    ${this._renderReadings(variant.readings)}
                </div>
            </div>
        `).join('');
    }

    /**
     * Render side-by-side view
     * @private
     */
    _renderSideBySide(variants) {
        return variants.map((variant, index) => {
            const readings = variant.readings || [];
            const half = Math.ceil(readings.length / 2);
            const leftReadings = readings.slice(0, half);
            const rightReadings = readings.slice(half);

            return `
                <div class="${this.cssPrefix}-variant ${this.cssPrefix}-variant--side-by-side">
                    <div class="${this.cssPrefix}-variant-header">
                        <span class="${this.cssPrefix}-variant-number">${index + 1}</span>
                        <span class="${this.cssPrefix}-variant-word">${this._escapeHtml(variant.word_text)}</span>
                        ${variant.variant_type ? `<span class="${this.cssPrefix}-variant-type">${this._escapeHtml(variant.variant_type)}</span>` : ''}
                    </div>
                    <div class="${this.cssPrefix}-readings-grid">
                        <div class="${this.cssPrefix}-readings-column">
                            ${this._renderReadings(leftReadings)}
                        </div>
                        <div class="${this.cssPrefix}-readings-column">
                            ${this._renderReadings(rightReadings)}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Render table view
     * @private
     */
    _renderTable(variants) {
        // Collect all unique readers across all variants
        const allReaders = new Map();
        variants.forEach(variant => {
            (variant.readings || []).forEach(reading => {
                if (!allReaders.has(reading.qari_id)) {
                    allReaders.set(reading.qari_id, reading.qari_name);
                }
            });
        });

        const readers = Array.from(allReaders.entries());

        return `
            <div class="${this.cssPrefix}-table-wrapper">
                <table class="${this.cssPrefix}-table">
                    <thead>
                        <tr>
                            <th class="${this.cssPrefix}-table-header ${this.cssPrefix}-table-header--word">الكلمة</th>
                            ${readers.map(([id, name]) => `
                                <th class="${this.cssPrefix}-table-header ${this.cssPrefix}-table-header--reader">${this._escapeHtml(name)}</th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${variants.map(variant => {
                            const readingsByQari = new Map();
                            (variant.readings || []).forEach(reading => {
                                readingsByQari.set(reading.qari_id, reading);
                            });

                            return `
                                <tr class="${this.cssPrefix}-table-row">
                                    <td class="${this.cssPrefix}-table-cell ${this.cssPrefix}-table-cell--word">
                                        ${this._escapeHtml(variant.word_text)}
                                    </td>
                                    ${readers.map(([id, name]) => {
                                        const reading = readingsByQari.get(id);
                                        const text = reading ? reading.reading_text : '-';
                                        const isDifferent = reading && this._isDifferentReading(variant, reading);

                                        return `
                                            <td class="${this.cssPrefix}-table-cell ${isDifferent && this.highlightDifferences ? `${this.cssPrefix}-table-cell--highlight` : ''}">
                                                ${this._escapeHtml(text)}
                                            </td>
                                        `;
                                    }).join('')}
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    /**
     * Render individual readings
     * @private
     */
    _renderReadings(readings) {
        if (!readings || readings.length === 0) {
            return `<div class="${this.cssPrefix}-no-readings">لا توجد قراءات</div>`;
        }

        return readings.map(reading => {
            const isHighlighted = this.highlightDifferences && this._shouldHighlight(reading);

            return `
                <div class="${this.cssPrefix}-reading ${isHighlighted ? `${this.cssPrefix}-reading--highlight` : ''}">
                    <div class="${this.cssPrefix}-reading-header">
                        <span class="${this.cssPrefix}-qari-name">${this._escapeHtml(reading.qari_name)}</span>
                        ${reading.rawi_name ? `<span class="${this.cssPrefix}-rawi-name">رواية ${this._escapeHtml(reading.rawi_name)}</span>` : ''}
                    </div>
                    <div class="${this.cssPrefix}-reading-text">${this._escapeHtml(reading.reading_text)}</div>
                    ${reading.phonetic_description && this.showReaderInfo ? `
                        <div class="${this.cssPrefix}-reading-description">${this._escapeHtml(reading.phonetic_description)}</div>
                    ` : ''}
                </div>
            `;
        }).join('');
    }

    /**
     * Check if a reading should be highlighted
     * @private
     */
    _shouldHighlight(reading) {
        // For now, we don't have baseline to compare against
        // This could be enhanced to compare against Hafs reading
        return false;
    }

    /**
     * Check if a reading is different from the main word
     * @private
     */
    _isDifferentReading(variant, reading) {
        return variant.word_text !== reading.reading_text;
    }

    /**
     * Render loading state
     * @private
     */
    _renderLoading() {
        return `
            <div class="${this.cssPrefix}-widget ${this.cssPrefix}-loading" dir="rtl">
                <div class="${this.cssPrefix}-spinner"></div>
                <span>جارٍ تحميل القراءات...</span>
            </div>
        `;
    }

    /**
     * Render error state
     * @private
     */
    _renderError() {
        return `
            <div class="${this.cssPrefix}-widget ${this.cssPrefix}-error" dir="rtl">
                <div class="${this.cssPrefix}-error-icon">&#9888;</div>
                <div class="${this.cssPrefix}-error-message">حدث خطأ في تحميل القراءات</div>
                <div class="${this.cssPrefix}-error-details">${this._escapeHtml(this.error)}</div>
                <button class="${this.cssPrefix}-retry-btn" onclick="this.closest('.${this.cssPrefix}-widget').dispatchEvent(new CustomEvent('retry'))">
                    إعادة المحاولة
                </button>
            </div>
        `;
    }

    /**
     * Render empty state (no verse selected)
     * @private
     */
    _renderEmptyState() {
        return `
            <div class="${this.cssPrefix}-widget ${this.cssPrefix}-empty" dir="rtl">
                <div class="${this.cssPrefix}-empty-icon">&#128214;</div>
                <div class="${this.cssPrefix}-empty-message">اختر آية لعرض القراءات</div>
            </div>
        `;
    }

    /**
     * Render no differences message
     * @private
     */
    _renderNoDifferences() {
        return `
            <div class="${this.cssPrefix}-no-differences">
                <div class="${this.cssPrefix}-no-diff-icon">&#10004;</div>
                <div class="${this.cssPrefix}-no-diff-message">لا توجد فروق في القراءات لهذه الآية</div>
                <div class="${this.cssPrefix}-no-diff-note">جميع القراءات متفقة على نص هذه الآية</div>
            </div>
        `;
    }

    /**
     * Attach event listeners
     * @private
     */
    _attachEventListeners() {
        // Mode toggle buttons
        const modeButtons = this.container.querySelectorAll(`.${this.cssPrefix}-mode-btn`);
        modeButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.currentTarget.dataset.mode;
                this.setDisplayMode(mode);
            });
        });

        // Retry button
        const widget = this.container.querySelector(`.${this.cssPrefix}-widget`);
        if (widget) {
            widget.addEventListener('retry', () => {
                this.render();
            });
        }
    }

    /**
     * Format verse key for display
     * @private
     */
    _formatVerseKey(verseKey) {
        const [surah, ayah] = verseKey.split(':');
        return `الآية ${this._toArabicNumerals(ayah)}`;
    }

    /**
     * Convert number to Arabic numerals
     * @private
     */
    _toArabicNumerals(num) {
        const arabicNumerals = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
        return String(num).split('').map(digit => arabicNumerals[parseInt(digit)] || digit).join('');
    }

    /**
     * Escape HTML to prevent XSS
     * @private
     */
    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Ensure CSS is loaded
     * @private
     */
    _ensureStyles() {
        const styleId = 'qiraat-compare-styles';
        if (!document.getElementById(styleId)) {
            const link = document.createElement('link');
            link.id = styleId;
            link.rel = 'stylesheet';
            link.href = '/static/css/qiraat-compare.css';
            document.head.appendChild(link);
        }
    }

    /**
     * Destroy the widget and clean up
     */
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.data = null;
        this.error = null;
    }
}

/**
 * Factory function for creating QiraatCompare instances
 * @param {string|HTMLElement} container - Container selector or element
 * @param {Object} options - Configuration options
 * @returns {QiraatCompare}
 */
function createQiraatCompare(container, options = {}) {
    const containerEl = typeof container === 'string'
        ? document.querySelector(container)
        : container;

    if (!containerEl) {
        console.error('QiraatCompare: Container not found');
        return null;
    }

    return new QiraatCompare({
        container: containerEl,
        ...options
    });
}

/**
 * Initialize all qiraat-compare widgets on the page
 * Looks for elements with data-qiraat-compare attribute
 */
function initQiraatCompareWidgets() {
    const widgets = document.querySelectorAll('[data-qiraat-compare]');
    const instances = [];

    widgets.forEach(container => {
        const verseKey = container.dataset.qiraatCompare || container.dataset.verseKey;
        const displayMode = container.dataset.displayMode || 'stacked';
        const highlightDifferences = container.dataset.highlightDifferences !== 'false';
        const showReaderInfo = container.dataset.showReaderInfo !== 'false';
        const showModeToggle = container.dataset.showModeToggle !== 'false';

        const widget = new QiraatCompare({
            container,
            verseKey,
            displayMode,
            highlightDifferences,
            showReaderInfo,
            showModeToggle
        });

        if (verseKey) {
            widget.render();
        }

        instances.push(widget);
    });

    return instances;
}

// Auto-initialize when DOM is ready
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initQiraatCompareWidgets);
    } else {
        // DOM is already ready, but delay slightly to ensure all elements are parsed
        setTimeout(initQiraatCompareWidgets, 0);
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { QiraatCompare, createQiraatCompare, initQiraatCompareWidgets };
}
