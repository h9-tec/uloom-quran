-- =============================================================================
-- أصول القراءات العشر - Database Schema
-- Foundational Rules of the Ten Qira'at
-- =============================================================================

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- =============================================================================
-- USUL CATEGORIES (Rule Categories)
-- =============================================================================

-- Main categories of Usul rules
CREATE TABLE IF NOT EXISTS usul_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_arabic TEXT NOT NULL UNIQUE,
    name_english TEXT,
    description_arabic TEXT,
    description_english TEXT,
    display_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert the 11 main usul categories
INSERT OR IGNORE INTO usul_categories (id, name_arabic, name_english, description_arabic, display_order) VALUES
(1, 'الاستعاذة', 'Al-Isti''adha', 'التعوذ بالله من الشيطان الرجيم قبل القراءة', 1),
(2, 'البسملة', 'Al-Basmala', 'الإتيان ببسم الله الرحمن الرحيم بين السورتين', 2),
(3, 'الإدغام', 'Al-Idgham', 'إدخال حرف في حرف بحيث يصيران حرفاً واحداً مشدداً', 3),
(4, 'المد', 'Al-Madd', 'طول زمان صوت حرف المد واللين', 4),
(5, 'الهمزات', 'Al-Hamzat', 'أحكام الهمزة المفردة والهمزتين المجتمعتين', 5),
(6, 'هاء الكناية', 'Ha al-Kinaya', 'الهاء الزائدة الدالة على الواحد المذكر الغائب', 6),
(7, 'ياءات الإضافة', 'Ya''at al-Idafa', 'ياء المتكلم المتصلة بالاسم والفعل والحرف', 7),
(8, 'ياءات الزوائد', 'Ya''at al-Zawa''id', 'الياءات المتطرفة الزائدة في التلاوة على رسم المصاحف', 8),
(9, 'صلة ميم الجمع', 'Silat Mim al-Jam', 'ضم ميم الجمع ووصلها بواو لفظية', 9),
(10, 'الراءات', 'Al-Ra''at', 'أحكام الراء من حيث التفخيم والترقيق', 10),
(11, 'اللامات', 'Al-Lamat', 'أحكام اللام من حيث التفخيم والترقيق', 11),
(12, 'الإمالة', 'Al-Imala', 'النطق بالفتحة نحو الكسرة وبالألف نحو الياء', 12);

-- =============================================================================
-- USUL RULES (Main Rules Table)
-- =============================================================================

-- Main usul rules for each qari
CREATE TABLE IF NOT EXISTS usul_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,  -- Optional: specific to a rawi
    rule_name_arabic TEXT NOT NULL,
    rule_name_english TEXT,
    rule_description_arabic TEXT NOT NULL,
    rule_description_english TEXT,
    rule_value TEXT,  -- e.g., "6 حركات", "صلة", "إسكان"
    is_default INTEGER DEFAULT 0,  -- Is this the default/most common option?
    has_variations INTEGER DEFAULT 0,  -- Does this rule have multiple options?
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES usul_categories(id),
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- USUL RULE OPTIONS (For rules with multiple valid options)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_rule_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    option_name_arabic TEXT NOT NULL,
    option_name_english TEXT,
    option_description TEXT,
    is_preferred INTEGER DEFAULT 0,  -- Is this the preferred/primary option?
    display_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES usul_rules(id)
);

-- =============================================================================
-- MADD RULES (Specific table for elongation rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_madd_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    madd_type TEXT NOT NULL CHECK(madd_type IN (
        'متصل', 'منفصل', 'بدل', 'لين', 'عارض', 'لازم'
    )),
    madd_type_english TEXT,
    harakat_min INTEGER NOT NULL,  -- Minimum harakat
    harakat_max INTEGER NOT NULL,  -- Maximum harakat
    harakat_default INTEGER,       -- Default/common value
    description TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- BASMALA RULES (Specific table for basmala between surahs)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_basmala_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    rule_type TEXT NOT NULL CHECK(rule_type IN (
        'وجوب', 'ترك', 'ثلاثة_أوجه'
    )),
    allows_basmala INTEGER DEFAULT 1,
    allows_sakt INTEGER DEFAULT 0,
    allows_wasl INTEGER DEFAULT 0,
    preferred_option TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- HAMZA RULES (Specific table for hamza rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_hamza_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    hamza_type TEXT NOT NULL CHECK(hamza_type IN (
        'مفردة', 'من_كلمة_مفتوحتان', 'من_كلمة_مفتوحة_مكسورة', 'من_كلمة_مفتوحة_مضمومة',
        'من_كلمتين_متفقتان', 'من_كلمتين_مختلفتان', 'وقف_على_الهمز'
    )),
    rule_type TEXT CHECK(rule_type IN (
        'تحقيق', 'تسهيل', 'إبدال', 'حذف', 'نقل', 'إدخال'
    )),
    applies_to_first INTEGER DEFAULT 0,  -- Applies to first hamza
    applies_to_second INTEGER DEFAULT 0, -- Applies to second hamza
    with_insertion INTEGER DEFAULT 0,    -- With alif insertion
    description TEXT,
    examples TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- HA KINAYA RULES (Pronoun ha rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_ha_kinaya_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    rule_type TEXT NOT NULL CHECK(rule_type IN (
        'صلة_دائمة', 'صلة_بين_متحركين', 'قصر', 'خلاف'
    )),
    connects_after_sukun INTEGER DEFAULT 0,
    description TEXT,
    exceptions TEXT,  -- JSON array of exception cases
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- MIM JAM RULES (Plural meem connection rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_mim_jam_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    rule_type TEXT NOT NULL CHECK(rule_type IN (
        'صلة', 'إسكان', 'وجهان'
    )),
    preferred_option TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- IDGHAM RULES (Assimilation rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_idgham_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    idgham_type TEXT NOT NULL CHECK(idgham_type IN (
        'كبير', 'صغير'
    )),
    applies_to_mithlayn INTEGER DEFAULT 0,   -- Same letters
    applies_to_mutaqaribayn INTEGER DEFAULT 0, -- Close letters
    applies_to_mutajanisayn INTEGER DEFAULT 0, -- Same makhraj
    is_active INTEGER DEFAULT 1,  -- Does this qari use this type?
    description TEXT,
    letters TEXT,  -- JSON array of letter combinations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- IMALA RULES (Inclination rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_imala_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    imala_type TEXT NOT NULL CHECK(imala_type IN (
        'كبرى', 'صغرى_تقليل', 'فتح', 'وجهان'
    )),
    scope TEXT,  -- Description of where it applies
    eleven_surahs INTEGER DEFAULT 0,  -- Applies to the 11 surahs?
    ra_words INTEGER DEFAULT 0,  -- Applies to words with ra?
    specific_words TEXT,  -- JSON array of specific words
    exceptions TEXT,  -- JSON array of exceptions
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- RA/LAM RULES (Tafkhim and Tarqiq)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_ra_lam_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    letter TEXT NOT NULL CHECK(letter IN ('ر', 'ل')),
    context TEXT,  -- Context description
    rule_type TEXT NOT NULL CHECK(rule_type IN (
        'تفخيم', 'ترقيق', 'وجهان'
    )),
    condition TEXT,  -- When this rule applies
    description TEXT,
    exceptions TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- YA IDAFA RULES (Possessive ya)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_ya_idafa_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    tendency TEXT CHECK(tendency IN (
        'يميل_للفتح', 'يميل_للإسكان', 'متوسط'
    )),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- YA ZAWAID RULES (Extra ya)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_ya_zawaid_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    tendency TEXT CHECK(tendency IN (
        'يثبت_الأكثر', 'يحذف_الأكثر', 'متوسط'
    )),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- SPECIFIC YA OCCURRENCES (For tracking individual ya rules)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_ya_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verse_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    ya_type TEXT NOT NULL CHECK(ya_type IN ('إضافة', 'زوائد')),
    without_ya TEXT,  -- Word without the ya
    with_ya TEXT,     -- Word with the ya
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id)
);

-- Ya occurrence readings by qari
CREATE TABLE IF NOT EXISTS usul_ya_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurrence_id INTEGER NOT NULL,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    reading_type TEXT CHECK(reading_type IN (
        'فتح', 'إسكان', 'إثبات', 'حذف'
    )),
    in_wasl INTEGER DEFAULT 1,  -- In connected reading
    in_waqf INTEGER DEFAULT 1,  -- At stopping
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (occurrence_id) REFERENCES usul_ya_occurrences(id),
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- SPECIAL WORDS (Words with special rulings)
-- =============================================================================

CREATE TABLE IF NOT EXISTS usul_special_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    verse_id INTEGER,
    verse_reference TEXT,  -- e.g., "الأعراف:111"
    category_id INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verse_id) REFERENCES verses(id),
    FOREIGN KEY (category_id) REFERENCES usul_categories(id)
);

-- Special word readings
CREATE TABLE IF NOT EXISTS usul_special_word_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    special_word_id INTEGER NOT NULL,
    qari_id INTEGER NOT NULL,
    rawi_id INTEGER,
    reading_text TEXT NOT NULL,
    reading_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (special_word_id) REFERENCES usul_special_words(id),
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_usul_rules_category ON usul_rules(category_id);
CREATE INDEX IF NOT EXISTS idx_usul_rules_qari ON usul_rules(qari_id);
CREATE INDEX IF NOT EXISTS idx_usul_rules_rawi ON usul_rules(rawi_id);
CREATE INDEX IF NOT EXISTS idx_usul_madd_qari ON usul_madd_rules(qari_id);
CREATE INDEX IF NOT EXISTS idx_usul_madd_type ON usul_madd_rules(madd_type);
CREATE INDEX IF NOT EXISTS idx_usul_basmala_qari ON usul_basmala_rules(qari_id);
CREATE INDEX IF NOT EXISTS idx_usul_hamza_qari ON usul_hamza_rules(qari_id);
CREATE INDEX IF NOT EXISTS idx_usul_hamza_type ON usul_hamza_rules(hamza_type);
CREATE INDEX IF NOT EXISTS idx_usul_imala_qari ON usul_imala_rules(qari_id);
CREATE INDEX IF NOT EXISTS idx_usul_special_word ON usul_special_words(word);
CREATE INDEX IF NOT EXISTS idx_usul_ya_verse ON usul_ya_occurrences(verse_id);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- View: Summary of usul rules by qari
CREATE VIEW IF NOT EXISTS v_usul_summary AS
SELECT
    q.name_arabic as qari_name,
    r.name_arabic as rawi_name,
    c.name_arabic as category_name,
    ur.rule_name_arabic,
    ur.rule_value,
    ur.rule_description_arabic
FROM usul_rules ur
JOIN qurra q ON ur.qari_id = q.id
LEFT JOIN ruwat r ON ur.rawi_id = r.id
JOIN usul_categories c ON ur.category_id = c.id
ORDER BY q.rank_order, c.display_order;

-- View: Madd rules summary
CREATE VIEW IF NOT EXISTS v_madd_summary AS
SELECT
    q.name_arabic as qari_name,
    r.name_arabic as rawi_name,
    um.madd_type,
    um.harakat_min,
    um.harakat_max,
    um.harakat_default,
    um.description
FROM usul_madd_rules um
JOIN qurra q ON um.qari_id = q.id
LEFT JOIN ruwat r ON um.rawi_id = r.id
ORDER BY q.rank_order, um.madd_type;

-- View: Basmala rules summary
CREATE VIEW IF NOT EXISTS v_basmala_summary AS
SELECT
    q.name_arabic as qari_name,
    r.name_arabic as rawi_name,
    ub.rule_type,
    ub.allows_basmala,
    ub.allows_sakt,
    ub.allows_wasl,
    ub.preferred_option
FROM usul_basmala_rules ub
JOIN qurra q ON ub.qari_id = q.id
LEFT JOIN ruwat r ON ub.rawi_id = r.id
ORDER BY q.rank_order;

-- =============================================================================
-- INITIAL DATA: Madd Rules
-- =============================================================================

-- Madd Muttasil (Connected)
INSERT OR IGNORE INTO usul_madd_rules (qari_id, rawi_id, madd_type, harakat_min, harakat_max, harakat_default, description) VALUES
(1, 1, 'متصل', 4, 4, 4, 'قالون: أربع حركات'),
(1, 2, 'متصل', 6, 6, 6, 'ورش: ست حركات (الإشباع)'),
(2, NULL, 'متصل', 4, 4, 4, 'ابن كثير: أربع حركات'),
(3, NULL, 'متصل', 4, 4, 4, 'أبو عمرو: أربع حركات'),
(4, NULL, 'متصل', 4, 4, 4, 'ابن عامر: أربع حركات'),
(5, 1, 'متصل', 4, 4, 4, 'شعبة: أربع حركات'),
(5, 2, 'متصل', 4, 5, 5, 'حفص: أربع إلى خمس حركات'),
(6, NULL, 'متصل', 6, 6, 6, 'حمزة: ست حركات (الإشباع)'),
(7, NULL, 'متصل', 4, 4, 4, 'الكسائي: أربع حركات'),
(8, NULL, 'متصل', 4, 4, 4, 'أبو جعفر: أربع حركات'),
(9, NULL, 'متصل', 4, 4, 4, 'يعقوب: أربع حركات'),
(10, NULL, 'متصل', 4, 4, 4, 'خلف العاشر: أربع حركات');

-- Madd Munfasil (Separated)
INSERT OR IGNORE INTO usul_madd_rules (qari_id, rawi_id, madd_type, harakat_min, harakat_max, harakat_default, description) VALUES
(1, 1, 'منفصل', 2, 4, 4, 'قالون: القصر والتوسط'),
(1, 2, 'منفصل', 6, 6, 6, 'ورش: ست حركات (الإشباع)'),
(2, NULL, 'منفصل', 2, 2, 2, 'ابن كثير: القصر'),
(3, NULL, 'منفصل', 2, 2, 2, 'أبو عمرو: القصر'),
(4, NULL, 'منفصل', 4, 4, 4, 'ابن عامر: التوسط'),
(5, 1, 'منفصل', 4, 5, 4, 'شعبة: التوسط'),
(5, 2, 'منفصل', 4, 5, 4, 'حفص: التوسط'),
(6, NULL, 'منفصل', 6, 6, 6, 'حمزة: ست حركات (الإشباع)'),
(7, NULL, 'منفصل', 4, 4, 4, 'الكسائي: التوسط'),
(8, NULL, 'منفصل', 2, 2, 2, 'أبو جعفر: القصر'),
(9, NULL, 'منفصل', 2, 2, 2, 'يعقوب: القصر'),
(10, NULL, 'منفصل', 4, 4, 4, 'خلف العاشر: التوسط');

-- =============================================================================
-- INITIAL DATA: Basmala Rules
-- =============================================================================

INSERT OR IGNORE INTO usul_basmala_rules (qari_id, rawi_id, rule_type, allows_basmala, allows_sakt, allows_wasl, preferred_option) VALUES
(1, 1, 'وجوب', 1, 0, 0, 'البسملة'),
(1, 2, 'ثلاثة_أوجه', 1, 1, 1, 'البسملة'),
(2, NULL, 'وجوب', 1, 0, 0, 'البسملة'),
(3, NULL, 'ثلاثة_أوجه', 1, 1, 1, 'السكت'),
(4, NULL, 'ثلاثة_أوجه', 1, 1, 1, 'البسملة'),
(5, NULL, 'وجوب', 1, 0, 0, 'البسملة'),
(6, NULL, 'ترك', 0, 1, 1, 'الوصل'),
(7, NULL, 'وجوب', 1, 0, 0, 'البسملة'),
(8, NULL, 'وجوب', 1, 0, 0, 'البسملة'),
(9, NULL, 'ثلاثة_أوجه', 1, 1, 1, 'البسملة'),
(10, NULL, 'ترك', 0, 1, 1, 'السكت');

-- =============================================================================
-- INITIAL DATA: Mim Jam Rules
-- =============================================================================

INSERT OR IGNORE INTO usul_mim_jam_rules (qari_id, rawi_id, rule_type, preferred_option, description) VALUES
(1, 1, 'وجهان', 'صلة', 'قالون: له الصلة والإسكان، والصلة مقدمة'),
(1, 2, 'إسكان', NULL, 'ورش: الإسكان'),
(2, NULL, 'صلة', NULL, 'ابن كثير: صلة ميم الجمع بواو'),
(3, NULL, 'إسكان', NULL, 'أبو عمرو: الإسكان'),
(4, NULL, 'إسكان', NULL, 'ابن عامر: الإسكان'),
(5, NULL, 'إسكان', NULL, 'عاصم: الإسكان'),
(6, NULL, 'إسكان', NULL, 'حمزة: الإسكان'),
(7, NULL, 'إسكان', NULL, 'الكسائي: الإسكان'),
(8, NULL, 'صلة', NULL, 'أبو جعفر: صلة ميم الجمع بواو'),
(9, NULL, 'إسكان', NULL, 'يعقوب: الإسكان'),
(10, NULL, 'إسكان', NULL, 'خلف العاشر: الإسكان');

-- =============================================================================
-- INITIAL DATA: Ha Kinaya Rules
-- =============================================================================

INSERT OR IGNORE INTO usul_ha_kinaya_rules (qari_id, rawi_id, rule_type, connects_after_sukun, description) VALUES
(1, NULL, 'صلة_بين_متحركين', 0, 'نافع: صلة هاء الضمير بين متحركين'),
(2, NULL, 'صلة_دائمة', 1, 'ابن كثير: صلة هاء الضمير دائماً حتى بعد ساكن'),
(3, NULL, 'صلة_بين_متحركين', 0, 'أبو عمرو: صلة بين متحركين'),
(4, NULL, 'صلة_بين_متحركين', 0, 'ابن عامر: صلة بين متحركين'),
(5, 1, 'صلة_بين_متحركين', 0, 'شعبة: صلة بين متحركين'),
(5, 2, 'قصر', 0, 'حفص: قصر هاء الضمير غالباً مع استثناءات'),
(6, NULL, 'صلة_بين_متحركين', 0, 'حمزة: صلة بين متحركين'),
(7, NULL, 'صلة_بين_متحركين', 0, 'الكسائي: صلة بين متحركين'),
(8, NULL, 'صلة_بين_متحركين', 0, 'أبو جعفر: صلة بين متحركين'),
(9, NULL, 'صلة_بين_متحركين', 0, 'يعقوب: صلة بين متحركين'),
(10, NULL, 'صلة_بين_متحركين', 0, 'خلف العاشر: صلة بين متحركين');

-- =============================================================================
-- INITIAL DATA: Idgham Rules
-- =============================================================================

INSERT OR IGNORE INTO usul_idgham_rules (qari_id, rawi_id, idgham_type, applies_to_mithlayn, applies_to_mutaqaribayn, applies_to_mutajanisayn, is_active, description) VALUES
(3, 2, 'كبير', 1, 1, 1, 1, 'السوسي عن أبي عمرو: الإدغام الكبير'),
(3, 1, 'كبير', 0, 0, 0, 0, 'الدوري عن أبي عمرو: الإظهار');

-- =============================================================================
-- INITIAL DATA: Imala Rules
-- =============================================================================

INSERT OR IGNORE INTO usul_imala_rules (qari_id, rawi_id, imala_type, eleven_surahs, ra_words, scope, description) VALUES
(1, 2, 'صغرى_تقليل', 1, 1, 'رؤوس آي السور الإحدى عشرة وذوات الراء', 'ورش: التقليل'),
(6, NULL, 'كبرى', 1, 1, 'رؤوس آي السور الإحدى عشرة والألفات اليائية', 'حمزة: الإمالة الكبرى'),
(7, NULL, 'كبرى', 1, 1, 'رؤوس آي السور الإحدى عشرة والألفات اليائية', 'الكسائي: الإمالة الكبرى'),
(10, NULL, 'كبرى', 1, 1, 'رؤوس آي السور الإحدى عشرة والألفات اليائية', 'خلف العاشر: الإمالة الكبرى'),
(3, 1, 'وجهان', 0, 0, 'كلمة النار وبعض الكلمات', 'الدوري عن أبي عمرو: إمالة في النار');

-- =============================================================================
-- INITIAL DATA: Ya Rules Tendencies
-- =============================================================================

INSERT OR IGNORE INTO usul_ya_idafa_rules (qari_id, tendency, description) VALUES
(1, 'يميل_للفتح', 'نافع: يميل لفتح ياء الإضافة'),
(2, 'يميل_للفتح', 'ابن كثير: يميل لفتح ياء الإضافة'),
(3, 'متوسط', 'أبو عمرو: متوسط في ياء الإضافة'),
(4, 'متوسط', 'ابن عامر: متوسط في ياء الإضافة'),
(5, 'متوسط', 'عاصم: متوسط في ياء الإضافة'),
(6, 'يميل_للإسكان', 'حمزة: يميل لإسكان ياء الإضافة'),
(7, 'يميل_للإسكان', 'الكسائي: يميل لإسكان ياء الإضافة'),
(8, 'يميل_للفتح', 'أبو جعفر: يميل لفتح ياء الإضافة'),
(9, 'متوسط', 'يعقوب: متوسط في ياء الإضافة'),
(10, 'يميل_للإسكان', 'خلف العاشر: يميل لإسكان ياء الإضافة');

INSERT OR IGNORE INTO usul_ya_zawaid_rules (qari_id, tendency, description) VALUES
(1, 'متوسط', 'نافع: متوسط في ياءات الزوائد'),
(2, 'يثبت_الأكثر', 'ابن كثير: يثبت معظم ياءات الزوائد'),
(3, 'يثبت_الأكثر', 'أبو عمرو: يثبت معظم ياءات الزوائد'),
(4, 'متوسط', 'ابن عامر: متوسط في ياءات الزوائد'),
(5, 'متوسط', 'عاصم: متوسط في ياءات الزوائد'),
(6, 'يحذف_الأكثر', 'حمزة: يحذف معظم ياءات الزوائد'),
(7, 'يحذف_الأكثر', 'الكسائي: يحذف معظم ياءات الزوائد'),
(8, 'يثبت_الأكثر', 'أبو جعفر: يثبت معظم ياءات الزوائد'),
(9, 'يثبت_الأكثر', 'يعقوب: يثبت معظم ياءات الزوائد'),
(10, 'يحذف_الأكثر', 'خلف العاشر: يحذف معظم ياءات الزوائد');

-- End of schema
