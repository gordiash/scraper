-- =====================================================
-- BAZA DANYCH NIERUCHOMOSCI - HOSTING ZEWNĘTRZNY (UPROSZCZONA)
-- Bez constraintów CHECK dla maksymalnej kompatybilności
-- Hosting: s108.cyber-folks.pl
-- Baza: hyxoyexiuq_scraper
-- =====================================================

-- Użyj istniejącej bazy danych
USE hyxoyexiuq_scraper;

-- Usuń tabelę jeśli istnieje
DROP TABLE IF EXISTS nieruchomosci;

-- =====================================================
-- GŁÓWNA TABELA NIERUCHOMOSCI (WERSJA UPROSZCZONA)
-- =====================================================

CREATE TABLE nieruchomosci (
    -- Klucz główny
    ad_id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- ID ogłoszenia z portalu
    listing_id VARCHAR(50),
    
    -- Podstawowe informacje
    url VARCHAR(512) NOT NULL UNIQUE,
    title_raw VARCHAR(500),
    address_raw VARCHAR(512),
    
    -- Cena i podstawowe parametry
    price DECIMAL(12,2),
    area DECIMAL(7,2),
    rooms TINYINT UNSIGNED,
    market ENUM('pierwotny', 'wtórny'),
    listing_date DATE,
    
    -- Lokalizacja (sparsowane komponenty)
    street VARCHAR(200),
    district VARCHAR(150),
    city VARCHAR(100),
    province VARCHAR(100),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    
    -- Cechy nieruchomości (boolean)
    has_balcony TINYINT(1) DEFAULT 0,
    has_garage TINYINT(1) DEFAULT 0,
    has_garden TINYINT(1) DEFAULT 0,
    has_elevator TINYINT(1) DEFAULT 0,
    has_basement TINYINT(1) DEFAULT 0,
    has_separate_kitchen TINYINT(1) DEFAULT 0,
    
    -- Wyposażenie AGD (boolean)
    has_dishwasher TINYINT(1) DEFAULT 0,
    has_fridge TINYINT(1) DEFAULT 0,
    has_oven TINYINT(1) DEFAULT 0,
    
    -- Informacje o budynku
    year_of_construction SMALLINT,
    building_type ENUM('blok', 'kamienica', 'apartamentowiec', 'dom wielorodzinny', 'wielka płyta', 'dom', 'inny'),
    floor TINYINT UNSIGNED,
    total_floors TINYINT UNSIGNED,
    standard_of_finish TINYINT UNSIGNED,
    
    -- Ogrzewanie i media
    heating_type VARCHAR(100),
    rent_amount DECIMAL(8,2),
    
    -- Zabezpieczenia (JSON)
    security_features JSON,
    
    -- Media (JSON)
    media_features JSON,
    
    -- Odległości (w metrach)
    distance_to_city_center INT UNSIGNED,
    distance_to_nearest_school INT UNSIGNED,
    distance_to_nearest_kindergarten INT UNSIGNED,
    distance_to_nearest_public_transport INT UNSIGNED,
    distance_to_nearest_supermarket INT UNSIGNED,
    distance_to_nearest_lake INT UNSIGNED,
    distance_to_university INT UNSIGNED,
    
    -- Metadane
    source VARCHAR(50) DEFAULT 'otodom.pl',
    source_page INT,
    source_position INT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Tylko podstawowe indeksy
    INDEX idx_listing_id (listing_id),
    INDEX idx_price (price),
    INDEX idx_city (city),
    INDEX idx_source (source),
    INDEX idx_url (url)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- WIDOK Z PEŁNYMI ADRESAMI
-- =====================================================

CREATE VIEW vw_nieruchomosci_full_address AS
SELECT 
    ad_id,
    listing_id,
    title_raw,
    price,
    area,
    rooms,
    CONCAT_WS(', ', 
        NULLIF(street, ''),
        NULLIF(district, ''),
        NULLIF(city, ''),
        NULLIF(province, '')
    ) as full_address,
    street,
    district,
    city,
    province,
    market,
    has_balcony,
    has_garage,
    has_garden,
    has_elevator,
    year_of_construction,
    building_type,
    source,
    created_at
FROM nieruchomosci;

-- =====================================================
-- TEST TABELI
-- =====================================================

-- Wstaw dane testowe
INSERT INTO nieruchomosci (
    listing_id, url, title_raw, address_raw, price, area, rooms, market,
    street, district, city, province, has_balcony, has_garage, source
) VALUES 
(
    'TEST123',
    'https://www.otodom.pl/test/simple/1',
    'Test mieszkania - hosting',
    'ul. Testowa 1, Centrum, Warszawa, mazowieckie',
    850000.00,
    65.5,
    3,
    'wtórny',
    'ul. Testowa 1',
    'Centrum',
    'Warszawa', 
    'mazowieckie',
    1, 0,
    'otodom.pl'
);

-- Sprawdź czy tabela działa
SELECT COUNT(*) as test_count FROM nieruchomosci WHERE listing_id = 'TEST123';

-- Sprawdź widok
SELECT full_address FROM vw_nieruchomosci_full_address WHERE listing_id = 'TEST123';

-- Usuń dane testowe
DELETE FROM nieruchomosci WHERE listing_id = 'TEST123';

-- =====================================================
-- KOMUNIKATY KOŃCOWE
-- =====================================================

SELECT '✅ UPROSZCZONA TABELA UTWORZONA!' AS status;
SELECT '📋 Tabela: nieruchomosci (bez constraintów CHECK)' AS info;
SELECT '🚀 Gotowa do użycia przez scraper!' AS info; 