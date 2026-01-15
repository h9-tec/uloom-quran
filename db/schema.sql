-- =============================================================================
-- علوم القرآن Database Schema
-- Comprehensive schema for: أسباب النزول، القراءات العشر، التفاسير المقارنة
-- =============================================================================

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- =============================================================================
-- CORE TABLES: Base Quran Data
-- =============================================================================

-- Surahs (Chapters)
CREATE TABLE IF NOT EXISTS surahs (
    id INTEGER PRIMARY KEY,
    name_arabic TEXT NOT NULL,
    name_english TEXT,
    name_transliteration TEXT,
    revelation_type TEXT CHECK(revelation_type IN ('مكي', 'مدني', 'مكية', 'مدنية')),
    revelation_order INTEGER,
    ayah_count INTEGER NOT NULL,
    word_count INTEGER,
    letter_count INTEGER,
    juz_start INTEGER,
    page_start INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Verses (Ayahs)
CREATE TABLE IF NOT EXISTS verses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surah_id INTEGER NOT NULL,
    ayah_number INTEGER NOT NULL,
    verse_key TEXT UNIQUE NOT NULL,  -- e.g., "2:255"
    text_uthmani TEXT NOT NULL,
    text_uthmani_simple TEXT,
    text_imlaei TEXT,  -- Simplified spelling
    page_number INTEGER,
    juz_number INTEGER,
    hizb_number INTEGER,
    rub_number INTEGER,
    manzil_number INTEGER,
    sajda_type TEXT CHECK(sajda_type IN ('واجبة', 'مستحبة', NULL)),
    word_count INTEGER,
    letter_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (surah_id) REFERENCES surahs(id),
    UNIQUE(surah_id, ayah_number)
);

-- Words in verses (for morphology and qiraat word-level tracking)
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    word_position INTEGER NOT NULL,
    text_uthmani TEXT NOT NULL,
    text_simple TEXT,
    transliteration TEXT,
    translation_en TEXT,
    root TEXT,  -- الجذر
    lemma TEXT,  -- الصيغة الأساسية
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    UNIQUE(verse_id, word_position)
);

-- Morphology (Grammar analysis per word)
CREATE TABLE IF NOT EXISTS morphology (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    part_of_speech TEXT,  -- اسم، فعل، حرف
    part_of_speech_detail TEXT,  -- فعل ماضي، اسم فاعل، etc.
    gender TEXT CHECK(gender IN ('مذكر', 'مؤنث', NULL)),
    number TEXT CHECK(number IN ('مفرد', 'مثنى', 'جمع', NULL)),
    person TEXT CHECK(person IN ('متكلم', 'مخاطب', 'غائب', NULL)),
    case_ending TEXT,  -- الإعراب: مرفوع، منصوب، مجرور
    state TEXT,  -- الحالة: معرفة، نكرة
    voice TEXT CHECK(voice IN ('معلوم', 'مجهول', NULL)),
    mood TEXT,  -- المزاج: مرفوع، منصوب، مجزوم
    aspect TEXT,  -- الزمن: ماضي، مضارع، أمر
    derivation TEXT,  -- الاشتقاق
    features TEXT,  -- JSON for additional features
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (word_id) REFERENCES words(id)
);

-- =============================================================================
-- أسباب النزول (Reasons for Revelation)
-- =============================================================================

-- Sources/Books for Asbab al-Nuzul
CREATE TABLE IF NOT EXISTS asbab_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_arabic TEXT NOT NULL,
    name_english TEXT,
    author_arabic TEXT NOT NULL,
    author_english TEXT,
    death_year_hijri INTEGER,
    death_year_gregorian INTEGER,
    description TEXT,
    reliability_rank INTEGER,  -- 1 = highest
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main Asbab al-Nuzul entries
CREATE TABLE IF NOT EXISTS asbab_nuzul (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    verse_end_id INTEGER,  -- If range of verses
    source_id INTEGER NOT NULL,
    sabab_text TEXT NOT NULL,  -- النص
    isnad TEXT,  -- السند
    narrator TEXT,  -- الراوي الأصلي (صحابي)
    hadith_reference TEXT,  -- مرجع الحديث
    authenticity_grade TEXT CHECK(authenticity_grade IN (
        'صحيح', 'حسن', 'ضعيف', 'موضوع', 'مرسل', 'منقطع', NULL
    )),
    grading_scholar TEXT,  -- من حكم عليه
    historical_context TEXT,
    revelation_period TEXT,  -- السنة أو الفترة
    location TEXT,  -- مكان النزول
    related_persons TEXT,  -- الأشخاص المتعلقون (JSON array)
    notes TEXT,
    page_reference TEXT,  -- Reference in original book
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (verse_end_id) REFERENCES verses(id),
    FOREIGN KEY (source_id) REFERENCES asbab_sources(id)
);

-- Multiple Asbab for same verse (different opinions)
CREATE TABLE IF NOT EXISTS asbab_opinions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    opinion_type TEXT CHECK(opinion_type IN ('راجح', 'مرجوح', 'محتمل')),
    summary TEXT,
    scholars_supporting TEXT,  -- JSON array of scholar names
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id)
);

-- =============================================================================
-- القراءات العشر (Ten Readings)
-- =============================================================================

-- The Ten Readers (القراء العشرة)
CREATE TABLE IF NOT EXISTS qurra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_arabic TEXT NOT NULL,
    name_english TEXT,
    death_year_hijri INTEGER,
    death_year_gregorian INTEGER,
    city TEXT,  -- المدينة
    region TEXT,  -- المنطقة (كوفي، بصري، مدني، etc.)
    teacher TEXT,  -- أستاذه
    is_main_ten INTEGER DEFAULT 1,  -- من العشرة الكبار
    biography TEXT,
    rank_order INTEGER,  -- الترتيب (1-10)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transmitters (الرواة) - Two per reader
CREATE TABLE IF NOT EXISTS ruwat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    name_arabic TEXT NOT NULL,
    name_english TEXT,
    death_year_hijri INTEGER,
    is_primary INTEGER DEFAULT 1,  -- الراوي الأول أم الثاني
    biography TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id)
);

-- Qiraat Differences (الفروق بين القراءات)
CREATE TABLE IF NOT EXISTS qiraat_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    word_id INTEGER,  -- NULL if applies to verse level
    word_text TEXT,  -- الكلمة الأصلية
    word_position INTEGER,
    variant_type TEXT CHECK(variant_type IN ('أصول', 'فرش')),
    category TEXT,  -- تصنيف الفرق
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

-- Individual readings per variant
CREATE TABLE IF NOT EXISTS qiraat_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,  -- Optional: specific transmitter
    reading_text TEXT NOT NULL,
    is_default INTEGER DEFAULT 0,  -- هل هي قراءة حفص
    phonetic_description TEXT,  -- وصف النطق
    tajweed_rule TEXT,  -- القاعدة التجويدية المتعلقة
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (variant_id) REFERENCES qiraat_variants(id),
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- Semantic impact of qiraat differences
CREATE TABLE IF NOT EXISTS qiraat_semantic_impact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL,
    has_meaning_difference INTEGER DEFAULT 0,
    meaning_explanation TEXT,
    fiqhi_implication TEXT,  -- الأثر الفقهي
    tafsir_notes TEXT,
    source_reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (variant_id) REFERENCES qiraat_variants(id)
);

-- Usul (General rules) that apply across Quran
CREATE TABLE IF NOT EXISTS qiraat_usul (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rule_name TEXT NOT NULL,
    rule_description TEXT NOT NULL,
    examples TEXT,  -- JSON array of example verses
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id)
);

-- Audio recordings for different readings
CREATE TABLE IF NOT EXISTS qiraat_audio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    reciter_name TEXT,  -- المقرئ المعاصر
    audio_url TEXT NOT NULL,
    duration_seconds INTEGER,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- التفاسير (Tafsir/Commentary)
-- =============================================================================

-- Tafsir books metadata
CREATE TABLE IF NOT EXISTS tafsir_books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_arabic TEXT NOT NULL,
    name_english TEXT,
    short_name TEXT UNIQUE,  -- For API reference
    author_arabic TEXT NOT NULL,
    author_english TEXT,
    death_year_hijri INTEGER,
    death_year_gregorian INTEGER,
    methodology TEXT CHECK(methodology IN (
        'بالمأثور', 'بالرأي', 'فقهي', 'لغوي', 'بلاغي', 'صوفي', 'علمي', 'معاصر', 'مختلط'
    )),
    madhab TEXT CHECK(madhab IN (
        'حنفي', 'مالكي', 'شافعي', 'حنبلي', 'ظاهري', 'غير محدد', NULL
    )),
    aqeedah TEXT CHECK(aqeedah IN (
        'سني', 'أشعري', 'ماتريدي', 'سلفي', 'معتزلي', NULL
    )),
    volume_count INTEGER,
    is_complete INTEGER DEFAULT 1,
    language TEXT DEFAULT 'ar',
    description TEXT,
    specialties TEXT,  -- JSON array: ["الأحكام", "البلاغة", etc.]
    source_url TEXT,
    priority_rank INTEGER,  -- For display ordering
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tafsir entries per verse
CREATE TABLE IF NOT EXISTS tafsir_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tafsir_id INTEGER NOT NULL,
    verse_id INTEGER NOT NULL,
    verse_end_id INTEGER,  -- If tafsir covers range
    text_arabic TEXT NOT NULL,
    text_english TEXT,
    summary TEXT,  -- AI-generated or manual summary
    word_count INTEGER,
    has_hadith INTEGER DEFAULT 0,
    has_poetry INTEGER DEFAULT 0,
    has_grammar INTEGER DEFAULT 0,
    has_fiqh INTEGER DEFAULT 0,
    topics TEXT,  -- JSON array of topics covered
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tafsir_id) REFERENCES tafsir_books(id),
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (verse_end_id) REFERENCES verses(id),
    UNIQUE(tafsir_id, verse_id)
);

-- Comparison points between tafsirs
CREATE TABLE IF NOT EXISTS tafsir_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    topic TEXT,
    comparison_type TEXT CHECK(comparison_type IN (
        'اتفاق', 'اختلاف', 'إضافة', 'تفرد'
    )),
    summary TEXT,
    tafsir_ids TEXT,  -- JSON array of tafsir IDs involved
    details TEXT,  -- JSON object with detailed comparison
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id)
);

-- Key terms/concepts mentioned in tafsirs
CREATE TABLE IF NOT EXISTS tafsir_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_arabic TEXT NOT NULL,
    term_english TEXT,
    definition TEXT,
    category TEXT,  -- فقه، عقيدة، نحو، بلاغة، etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link terms to tafsir entries
CREATE TABLE IF NOT EXISTS tafsir_entry_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    term_id INTEGER NOT NULL,
    context TEXT,
    FOREIGN KEY (entry_id) REFERENCES tafsir_entries(id),
    FOREIGN KEY (term_id) REFERENCES tafsir_terms(id)
);

-- =============================================================================
-- CROSS-REFERENCES AND RELATIONSHIPS
-- =============================================================================

-- Related verses (cross-references within Quran)
CREATE TABLE IF NOT EXISTS verse_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    related_verse_id INTEGER NOT NULL,
    relation_type TEXT CHECK(relation_type IN (
        'تفسير', 'تأكيد', 'تخصيص', 'نسخ', 'تقييد', 'إجمال', 'تفصيل', 'موضوع'
    )),
    description TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (related_verse_id) REFERENCES verses(id)
);

-- Hadith references (for asbab and tafsir)
CREATE TABLE IF NOT EXISTS hadith_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER,
    hadith_text TEXT NOT NULL,
    hadith_arabic TEXT,
    source_book TEXT,  -- البخاري، مسلم، etc.
    hadith_number TEXT,
    chapter TEXT,
    narrator TEXT,
    grade TEXT,
    relation_type TEXT CHECK(relation_type IN (
        'سبب_نزول', 'تفسير', 'استشهاد', 'حكم'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id)
);

-- Themes/Topics index
CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_arabic TEXT NOT NULL,
    name_english TEXT,
    parent_id INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES themes(id)
);

-- Link verses to themes
CREATE TABLE IF NOT EXISTS verse_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    relevance_score REAL,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (theme_id) REFERENCES themes(id)
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_verses_surah ON verses(surah_id);
CREATE INDEX IF NOT EXISTS idx_verses_key ON verses(verse_key);
CREATE INDEX IF NOT EXISTS idx_verses_page ON verses(page_number);
CREATE INDEX IF NOT EXISTS idx_verses_juz ON verses(juz_number);

CREATE INDEX IF NOT EXISTS idx_words_verse ON words(verse_id);
CREATE INDEX IF NOT EXISTS idx_words_root ON words(root);

CREATE INDEX IF NOT EXISTS idx_asbab_verse ON asbab_nuzul(verse_id);
CREATE INDEX IF NOT EXISTS idx_asbab_grade ON asbab_nuzul(authenticity_grade);

CREATE INDEX IF NOT EXISTS idx_qiraat_verse ON qiraat_variants(verse_id);
CREATE INDEX IF NOT EXISTS idx_qiraat_type ON qiraat_variants(variant_type);
CREATE INDEX IF NOT EXISTS idx_readings_qari ON qiraat_readings(qari_id);

CREATE INDEX IF NOT EXISTS idx_tafsir_entries_verse ON tafsir_entries(verse_id);
CREATE INDEX IF NOT EXISTS idx_tafsir_entries_book ON tafsir_entries(tafsir_id);

CREATE INDEX IF NOT EXISTS idx_hadith_verse ON hadith_references(verse_id);
CREATE INDEX IF NOT EXISTS idx_verse_themes ON verse_themes(verse_id);
CREATE INDEX IF NOT EXISTS idx_theme_verses ON verse_themes(theme_id);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Full verse view with surah info
CREATE VIEW IF NOT EXISTS v_verses_full AS
SELECT
    v.id,
    v.verse_key,
    v.surah_id,
    s.name_arabic as surah_name,
    v.ayah_number,
    v.text_uthmani,
    v.page_number,
    v.juz_number,
    s.revelation_type
FROM verses v
JOIN surahs s ON v.surah_id = s.id;

-- Asbab with source info
CREATE VIEW IF NOT EXISTS v_asbab_full AS
SELECT
    a.id,
    a.verse_id,
    v.verse_key,
    a.sabab_text,
    a.isnad,
    a.authenticity_grade,
    a.narrator,
    s.name_arabic as source_name,
    s.author_arabic as source_author
FROM asbab_nuzul a
JOIN verses v ON a.verse_id = v.id
JOIN asbab_sources s ON a.source_id = s.id;

-- Qiraat variants with reader info
CREATE VIEW IF NOT EXISTS v_qiraat_full AS
SELECT
    qv.id as variant_id,
    v.verse_key,
    qv.word_text,
    qv.variant_type,
    q.name_arabic as qari_name,
    r.name_arabic as rawi_name,
    qr.reading_text,
    qr.is_default
FROM qiraat_variants qv
JOIN verses v ON qv.verse_id = v.id
JOIN qiraat_readings qr ON qr.variant_id = qv.id
JOIN qurra q ON qr.qari_id = q.id
LEFT JOIN ruwat r ON qr.rawi_id = r.id;

-- Tafsir comparison view
CREATE VIEW IF NOT EXISTS v_tafsir_comparison AS
SELECT
    v.verse_key,
    tb.short_name as tafsir,
    tb.methodology,
    te.text_arabic,
    te.summary,
    te.word_count
FROM tafsir_entries te
JOIN verses v ON te.verse_id = v.id
JOIN tafsir_books tb ON te.tafsir_id = tb.id;

-- =============================================================================
-- INITIAL DATA: القراء العشرة والرواة
-- =============================================================================

-- Insert the Ten Readers
INSERT OR IGNORE INTO qurra (id, name_arabic, name_english, death_year_hijri, city, region, rank_order) VALUES
(1, 'نافع بن عبد الرحمن', 'Nafi ibn Abd al-Rahman', 169, 'المدينة', 'مدني', 1),
(2, 'عبد الله بن كثير', 'Abdullah ibn Kathir', 120, 'مكة', 'مكي', 2),
(3, 'أبو عمرو بن العلاء', 'Abu Amr ibn al-Ala', 154, 'البصرة', 'بصري', 3),
(4, 'عبد الله بن عامر', 'Abdullah ibn Amir', 118, 'دمشق', 'شامي', 4),
(5, 'عاصم بن أبي النجود', 'Asim ibn Abi al-Najud', 127, 'الكوفة', 'كوفي', 5),
(6, 'حمزة بن حبيب الزيات', 'Hamza al-Zayyat', 156, 'الكوفة', 'كوفي', 6),
(7, 'علي بن حمزة الكسائي', 'Al-Kisai', 189, 'الكوفة', 'كوفي', 7),
(8, 'أبو جعفر يزيد بن القعقاع', 'Abu Jafar', 130, 'المدينة', 'مدني', 8),
(9, 'يعقوب بن إسحاق الحضرمي', 'Yaqub al-Hadrami', 205, 'البصرة', 'بصري', 9),
(10, 'خلف بن هشام البزار', 'Khalaf al-Bazzar', 229, 'بغداد', 'بغدادي', 10);

-- Insert the Transmitters (الرواة)
INSERT OR IGNORE INTO ruwat (qari_id, name_arabic, name_english, death_year_hijri, is_primary) VALUES
-- نافع
(1, 'قالون', 'Qalun', 220, 1),
(1, 'ورش', 'Warsh', 197, 0),
-- ابن كثير
(2, 'البزي', 'Al-Bazzi', 250, 1),
(2, 'قنبل', 'Qunbul', 291, 0),
-- أبو عمرو
(3, 'الدوري', 'Al-Duri', 246, 1),
(3, 'السوسي', 'Al-Susi', 261, 0),
-- ابن عامر
(4, 'هشام', 'Hisham', 245, 1),
(4, 'ابن ذكوان', 'Ibn Dhakwan', 242, 0),
-- عاصم
(5, 'شعبة', 'Shuba', 193, 1),
(5, 'حفص', 'Hafs', 180, 0),
-- حمزة
(6, 'خلف', 'Khalaf', 229, 1),
(6, 'خلاد', 'Khallad', 220, 0),
-- الكسائي
(7, 'أبو الحارث', 'Abu al-Harith', 240, 1),
(7, 'الدوري', 'Al-Duri', 246, 0),
-- أبو جعفر
(8, 'ابن وردان', 'Ibn Wardan', 160, 1),
(8, 'ابن جماز', 'Ibn Jammaz', 170, 0),
-- يعقوب
(9, 'رويس', 'Ruways', 238, 1),
(9, 'روح', 'Rawh', 234, 0),
-- خلف العاشر
(10, 'إسحاق', 'Ishaq', 286, 1),
(10, 'إدريس', 'Idris', 292, 0);

-- =============================================================================
-- INITIAL DATA: مصادر أسباب النزول
-- =============================================================================

INSERT OR IGNORE INTO asbab_sources (id, name_arabic, author_arabic, death_year_hijri, reliability_rank) VALUES
(1, 'أسباب النزول', 'علي بن أحمد الواحدي', 468, 1),
(2, 'لباب النقول في أسباب النزول', 'جلال الدين السيوطي', 911, 2),
(3, 'العجاب في بيان الأسباب', 'ابن حجر العسقلاني', 852, 3),
(4, 'المحرر في أسباب نزول القرآن', 'خالد المزيني', 1400, 4);

-- =============================================================================
-- INITIAL DATA: كتب التفسير
-- =============================================================================

INSERT OR IGNORE INTO tafsir_books (id, name_arabic, short_name, author_arabic, death_year_hijri, methodology, priority_rank) VALUES
-- Classical بالمأثور
(1, 'جامع البيان عن تأويل آي القرآن', 'tabari', 'محمد بن جرير الطبري', 310, 'بالمأثور', 1),
(2, 'تفسير القرآن العظيم', 'ibn_kathir', 'إسماعيل بن عمر بن كثير', 774, 'بالمأثور', 2),
(3, 'معالم التنزيل', 'baghawi', 'الحسين بن مسعود البغوي', 516, 'بالمأثور', 3),

-- Jurisprudential فقهي
(4, 'الجامع لأحكام القرآن', 'qurtubi', 'محمد بن أحمد القرطبي', 671, 'فقهي', 4),
(5, 'أحكام القرآن', 'jassas', 'أحمد بن علي الجصاص', 370, 'فقهي', 10),

-- Linguistic/Rhetorical لغوي/بلاغي
(6, 'الكشاف عن حقائق غوامض التنزيل', 'zamakhshari', 'محمود بن عمر الزمخشري', 538, 'لغوي', 5),
(7, 'مفاتيح الغيب', 'razi', 'فخر الدين الرازي', 606, 'بالرأي', 6),
(8, 'البحر المحيط', 'abu_hayyan', 'أبو حيان الأندلسي', 745, 'لغوي', 11),

-- Brief/Popular
(9, 'تفسير الجلالين', 'jalalayn', 'جلال الدين المحلي والسيوطي', 911, 'مختلط', 7),

-- Modern معاصر
(10, 'تيسير الكريم الرحمن', 'saadi', 'عبد الرحمن بن ناصر السعدي', 1376, 'معاصر', 8),
(11, 'التحرير والتنوير', 'ibn_ashur', 'محمد الطاهر بن عاشور', 1393, 'معاصر', 9),
(12, 'في ظلال القرآن', 'qutb', 'سيد قطب', 1386, 'معاصر', 12),
(13, 'تفسير الشعراوي', 'shaarawi', 'محمد متولي الشعراوي', 1419, 'معاصر', 13),
(14, 'التفسير الميسر', 'muyassar', 'نخبة من العلماء', 1430, 'معاصر', 14),
(15, 'الوسيط في تفسير القرآن', 'waseet', 'محمد سيد طنطاوي', 1431, 'معاصر', 15);

-- End of schema
