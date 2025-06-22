#!/usr/bin/env python3
"""
MODUŁ DEDUPLIKACJI OGŁOSZEŃ
Zawiera funkcje do wykrywania i usuwania duplikatów ogłoszeń nieruchomości.
"""
import re
from typing import List, Dict, Tuple, Optional
from functools import lru_cache

# Import na początku modułu dla wydajności
try:
    from fuzzywuzzy import fuzz
except ImportError:
    print("⚠️ Brak biblioteki fuzzywuzzy. Instaluj: pip install fuzzywuzzy python-levenshtein")
    fuzz = None

# =================================================================
# FUNKCJE WYKRYWANIA DUPLIKATÓW OGŁOSZEŃ
# =================================================================

@lru_cache(maxsize=1000)
def normalize_text(text: str) -> str:
    """
    Normalizuje tekst do porównywania duplikatów (z cache dla wydajności)
    
    Args:
        text: Tekst do normalizacji
    
    Returns:
        str: Znormalizowany tekst
    """
    if not text or text is None:
        return ""
    
    # Konwertuj na string jeśli nie jest
    text = str(text)
    
    # Konwertuj na małe litery
    text = text.lower()
    
    # Usuń interpunkcję i nadmiarowe spacje
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Usuń typowe słowa nieistotne
    stop_words = {
        'mieszkanie', 'pokojowe', 'pokój', 'pokoje', 'm2', 'sprzedam', 
        'na', 'sprzedaż', 'do', 'w', 'z', 'i', 'a', 'o', 'u', 'po'
    }
    
    words = text.split()
    words = [word for word in words if word not in stop_words and len(word) > 2]
    
    return ' '.join(words).strip()

@lru_cache(maxsize=500)
def extract_area_number(area_text: str) -> Optional[float]:
    """
    Ekstraktuje liczbę metrów kwadratowych z tekstu (z cache dla wydajności)
    
    Args:
        area_text: Tekst z powierzchnią
    
    Returns:
        float: Powierzchnia w m2 lub None
    """
    if not area_text or area_text is None:
        return None
    
    # Konwertuj na string jeśli nie jest
    area_text = str(area_text)
    
    # Szukaj wzorców typu "65 m2", "65m²", "65.5 m2"
    pattern = r'(\d+(?:[.,]\d+)?)\s*m[2²]?'
    match = re.search(pattern, area_text.lower())
    
    if match:
        try:
            return float(match.group(1).replace(',', '.'))
        except ValueError:
            pass
    
    return None

@lru_cache(maxsize=100)
def extract_rooms_number(rooms_text: str) -> Optional[int]:
    """
    Ekstraktuje liczbę pokoi z tekstu (z cache dla wydajności)
    
    Args:
        rooms_text: Tekst z liczbą pokoi
    
    Returns:
        int: Liczba pokoi lub None
    """
    if not rooms_text or rooms_text is None:
        return None
    
    # Konwertuj na string jeśli nie jest
    rooms_text = str(rooms_text)
    
    # Szukaj wzorców typu "3 pokoje", "3-pokojowe", "3pok"
    pattern = r'(\d+)[\s\-]?pok'
    match = re.search(pattern, rooms_text.lower())
    
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    
    # Może być sama liczba
    if rooms_text.strip().isdigit():
        return int(rooms_text.strip())
    
    return None

def calculate_listings_similarity(listing1: Dict, listing2: Dict) -> float:
    """
    Oblicza podobieństwo między dwoma ogłoszeniami na podstawie ich kluczowych cech.
    
    Wagi:
    - Tytuł: 40%
    - Cena: 25%
    - Powierzchnia: 15%
    - Pokoje: 10%
    - Miasto/Dzielnica: 10%
    
    Args:
        listing1: Pierwsze ogłoszenie (słownik z danymi).
        listing2: Drugie ogłoszenie (słownik z danymi).
        
    Returns:
        float: Procent podobieństwa (0-100).
    """
    # Sprawdź czy fuzzywuzzy jest dostępne
    if fuzz is None:
        raise ImportError("Biblioteka fuzzywuzzy nie jest zainstalowana. Instaluj: pip install fuzzywuzzy python-levenshtein")
    
    # Waliduj dane wejściowe
    listing1 = validate_listing_data(listing1)
    listing2 = validate_listing_data(listing2)
    
    total_weight = 0
    similarity_score = 0

    # 1. Tytuł (waga 40%)
    title1 = normalize_text(listing1.get('title_raw', ''))
    title2 = normalize_text(listing2.get('title_raw', ''))
    if title1 and title2:
        title_sim = fuzz.ratio(title1, title2)
        similarity_score += title_sim * 0.40
        total_weight += 0.40

    # 2. Cena (waga 25%)
    price1 = listing1.get('price')
    price2 = listing2.get('price')
    
    # Bezpieczna konwersja cen
    try:
        if price1 is not None and price2 is not None:
            price1 = float(price1)
            price2 = float(price2)
            if price1 > 0 and price2 > 0:
                price_diff = abs(price1 - price2) / max(price1, price2)
                if price_diff <= 0.05:  # 5% tolerancji
                    similarity_score += 100 * 0.25
                else:
                    similarity_score += (1 - min(price_diff, 0.5)) * 100 * 0.25 # Zmniejszaj do 50% różnicy
                total_weight += 0.25
    except (ValueError, TypeError):
        # Jeśli konwersja się nie powiedzie, pomiń ceny
        pass

    # 3. Powierzchnia (waga 15%)
    area1 = extract_area_number(str(listing1.get('area', '')))
    area2 = extract_area_number(str(listing2.get('area', '')))
    if area1 is not None and area2 is not None and area1 > 0 and area2 > 0:
        area_diff = abs(area1 - area2) / max(area1, area2)
        if area_diff <= 0.10:  # 10% tolerancji
            similarity_score += 100 * 0.15
        else:
            similarity_score += (1 - min(area_diff, 0.5)) * 100 * 0.15 # Zmniejszaj do 50% różnicy
        total_weight += 0.15

    # 4. Pokoje (waga 10%)
    rooms1 = extract_rooms_number(str(listing1.get('rooms', '')))
    rooms2 = extract_rooms_number(str(listing2.get('rooms', '')))
    if rooms1 is not None and rooms2 is not None:
        if rooms1 == rooms2:
            similarity_score += 100 * 0.10
        total_weight += 0.10

    # 5. Miasto i Dzielnica (waga 10%)
    city1 = normalize_text(listing1.get('city', ''))
    district1 = normalize_text(listing1.get('district', ''))
    city2 = normalize_text(listing2.get('city', ''))
    district2 = normalize_text(listing2.get('district', ''))
    
    if city1 and city2 and fuzz.ratio(city1, city2) > 80:
        similarity_score += 50 * 0.10 # 50% wagi za miasto
        if district1 and district2 and fuzz.ratio(district1, district2) > 70:
            similarity_score += 50 * 0.10 # Dodatkowe 50% za dzielnicę
        total_weight += 0.10

    if total_weight == 0:
        return 0.0
    
    return (similarity_score / total_weight) if total_weight > 0 else 0.0

def simple_similarity(listing1: Dict, listing2: Dict) -> float:
    """
    Prosta funkcja podobieństwa - dla szybkich testów
    """
    # Sprawdź czy fuzzywuzzy jest dostępne
    if fuzz is None:
        return 0.0
        
    # Porównaj URL, jeśli są identyczne
    if listing1.get('url') and listing2.get('url') and listing1['url'] == listing2['url']:
        return 100.0
    
    # Porównaj tytuły i ceny
    title_sim = 0
    if listing1.get('title_raw') and listing2.get('title_raw'):
        title_sim = fuzz.ratio(normalize_text(listing1['title_raw']), normalize_text(listing2['title_raw']))
        
    price_match = False
    try:
        if listing1.get('price') is not None and listing2.get('price') is not None:
            price1 = float(listing1['price'])
            price2 = float(listing2['price'])
            if price1 > 0 and price2 > 0:
                price_diff = abs(price1 - price2) / max(price1, price2)
                if price_diff <= 0.05: # 5% tolerancji
                    price_match = True
    except (ValueError, TypeError):
        # Jeśli konwersja się nie powiedzie, pomiń porównanie cen
        pass
                
    if title_sim > 80 and price_match:
        return 95.0 # Wysokie podobieństwo
        
    return 0.0

def find_duplicates(listings: List[Dict], similarity_threshold: float = 75.0) -> Tuple[List[Dict], List[Dict]]:
    """
    Znajduje duplikaty ogłoszeń w liście.
    
    Args:
        listings: Lista ogłoszeń (słowników).
        similarity_threshold: Próg podobieństwa (0-100), powyżej którego ogłoszenia są uznawane za duplikaty.
    
    Returns:
        Tuple[List[Dict], List[Dict]]: Krotka zawierająca listę unikalnych ogłoszeń i listę duplikatów.
    """
    unique_listings = []
    duplicates = []
    
    for i, current_listing in enumerate(listings):
        is_duplicate = False
        for j, unique_listing in enumerate(unique_listings):
            similarity = calculate_listings_similarity(current_listing, unique_listing)
            if similarity >= similarity_threshold:
                duplicates.append(current_listing)
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_listings.append(current_listing)
            
    return unique_listings, duplicates

def deduplicate_listings(listings: List[Dict], similarity_threshold: float = 75.0, 
                        keep_best_source: bool = True) -> List[Dict]:
    """
    Usuwa duplikaty z listy ogłoszeń, opcjonalnie zachowując ogłoszenie z "najlepszego" źródła.
    
    Args:
        listings: Lista ogłoszeń (słowników).
        similarity_threshold: Próg podobieństwa (0-100) dla wykrywania duplikatów.
        keep_best_source: Jeśli True, w przypadku duplikatu, zachowuje ogłoszenie z wyższym priorytetem źródła.
                          Priorytety: otodom.pl > olx.pl > domiporta.pl > gratka.pl > metrohouse.pl > freedom.pl
                          
    Returns:
        List[Dict]: Lista zdeduplikowanych, unikalnych ogłoszeń.
    """
    if not listings:
        return []

    # Ranking źródeł (niższy indeks = wyższy priorytet)
    source_priority = ["otodom.pl", "olx.pl", "domiporta.pl", "gratka.pl", "metrohouse.pl", "freedom.pl"]
    
    # Sortuj ogłoszenia wg priorytetu źródła (najlepsze na początku)
    if keep_best_source:
        listings.sort(key=lambda x: source_priority.index(x.get('source', 'unknown')) if x.get('source') in source_priority else len(source_priority))

    unique_listings = []
    
    for current_listing in listings:
        is_duplicate = False
        for i, existing_unique in enumerate(unique_listings):
            similarity = calculate_listings_similarity(current_listing, existing_unique)
            if similarity >= similarity_threshold:
                # Znaleziono duplikat
                is_duplicate = True
                
                if keep_best_source:
                    # Jeśli obecne ogłoszenie jest z lepszego źródła, zamień je
                    current_source_priority = source_priority.index(current_listing.get('source', 'unknown')) if current_listing.get('source') in source_priority else len(source_priority)
                    existing_source_priority = source_priority.index(existing_unique.get('source', 'unknown')) if existing_unique.get('source') in source_priority else len(source_priority)
                    
                    if current_source_priority < existing_source_priority: # Jeśli obecne jest lepsze
                        unique_listings[i] = current_listing # Zastąp istniejący unikalny ogłoszeniem z lepszego źródła
                break
        
        if not is_duplicate:
            unique_listings.append(current_listing)
            
    return unique_listings

def generate_duplicate_report(duplicates: List[Dict]) -> str:
    """
    Generuje raport o znalezionych duplikatach.
    
    Args:
        duplicates: Lista ogłoszeń zidentyfikowanych jako duplikaty.
        
    Returns:
        str: Sformatowany raport.
    """
    if not duplicates:
        return "Brak znalezionych duplikatów."
        
    report = "\n📊 Raport duplikatów:\n"
    report += "-" * 20 + "\n"
    
    # Pogrupuj duplikaty wg źródła
    duplicates_by_source = {}
    for dup in duplicates:
        source = dup.get('source', 'Nieznane')
        duplicates_by_source.setdefault(source, []).append(dup)
        
    for source, dup_list in duplicates_by_source.items():
        report += f"• {source}: {len(dup_list)} duplikatów\n"
        for i, item in enumerate(dup_list[:3]): # Pokaż max 3 przykłady na źródło
            report += f"  - {item.get('title_raw', 'Brak tytułu')[:50]}... (URL: {item.get('url', 'Brak URL')})\n"
        if len(dup_list) > 3:
            report += f"  ...i {len(dup_list) - 3} więcej z {source}\n"
            
    return report 

def validate_listing_data(listing: Dict) -> Dict:
    """
    Waliduje i czyści dane ogłoszenia przed porównaniem
    
    Args:
        listing: Słownik z danymi ogłoszenia
        
    Returns:
        Dict: Zwalidowane dane ogłoszenia
    """
    validated = {}
    
    # Walidacja tytułu
    title = listing.get('title_raw')
    validated['title_raw'] = str(title) if title is not None else ""
    
    # Walidacja ceny
    price = listing.get('price')
    try:
        validated['price'] = float(price) if price is not None else None
    except (ValueError, TypeError):
        validated['price'] = None
    
    # Walidacja powierzchni
    area = listing.get('area')
    validated['area'] = str(area) if area is not None else ""
    
    # Walidacja pokoi
    rooms = listing.get('rooms')
    validated['rooms'] = str(rooms) if rooms is not None else ""
    
    # Walidacja lokalizacji
    city = listing.get('city')
    validated['city'] = str(city) if city is not None else ""
    
    district = listing.get('district')
    validated['district'] = str(district) if district is not None else ""
    
    # Walidacja URL
    url = listing.get('url')
    validated['url'] = str(url) if url is not None else ""
    
    # Walidacja źródła
    source = listing.get('source')
    validated['source'] = str(source) if source is not None else ""
    
    return validated 