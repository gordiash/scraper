#!/usr/bin/env python3
"""
ZOPTYMALIZOWANY GEOCODER - WYDAJNOŚĆ I ASYNC
Ulepszona wersja z async/await, connection pooling i batch processing
"""
import asyncio
import aiohttp
import logging
import time
import sys
import os
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import json

# Dodaj główny katalog do ścieżki
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from supabase_utils import get_supabase_client

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Konfiguracja geocodingu
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
DELAY_BETWEEN_REQUESTS = 0.5  # Zmniejszone opóźnienie dla async
MAX_RETRIES = 2  # Zmniejszone retry dla szybkości
MAX_CONCURRENT_REQUESTS = 5  # Maksymalna liczba równoczesnych requestów
BATCH_SIZE = 100  # Większy batch size
CONNECTION_TIMEOUT = 10
READ_TIMEOUT = 15

class OptimizedGeocoder:
    """Zoptymalizowany geocoder z async/await"""
    
    def __init__(self):
        self.session = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.headers = {
            'User-Agent': 'Polish Real Estate Scraper/2.0 (optimized version)'
        }
        
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=20,  # Connection pool size
            limit_per_host=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(
            total=CONNECTION_TIMEOUT + READ_TIMEOUT,
            connect=CONNECTION_TIMEOUT,
            sock_read=READ_TIMEOUT
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def build_optimized_query(self, address_data: Dict) -> str:
        """Buduje zoptymalizowane zapytanie - tylko najważniejsze elementy"""
        components = []
        
        # 1. Ulica (bez prefiksów)
        if address_data.get('street_name'):
            street = address_data['street_name']
            # Usuń prefiksy
            for prefix in ['Ul. ', 'Al. ', 'Pl. ', 'Os. ', 'ul. ', 'al. ', 'pl. ', 'os. ']:
                street = street.replace(prefix, '')
            if street.strip():
                components.append(street.strip())
        
        # 2. Miasto (obowiązkowe)
        if address_data.get('city'):
            city = address_data['city']
            # Poprawki nazw miast
            city_fixes = {
                'Gdański': 'Pruszcz Gdański',
                'Łomianki': 'Łomianki',
                'Oleśnica': 'Oleśnica',
            }
            city = city_fixes.get(city, city)
            components.append(city)
        
        # 3. Zawsze dodaj "Polska"
        components.append("Polska")
        
        query = ", ".join(components)
        logger.debug(f"Zoptymalizowane zapytanie: {query}")
        return query
    
    def build_fallback_query(self, address_data: Dict) -> str:
        """Buduje zapytanie fallback - tylko miasto + Polska"""
        if address_data.get('city'):
            city = address_data['city']
            city_fixes = {'Gdański': 'Pruszcz Gdański'}
            city = city_fixes.get(city, city)
            return f"{city}, Polska"
        return "Polska"
    
    async def geocode_single_async(self, query: str, fallback_query: str = None) -> Optional[Tuple[float, float]]:
        """Async geocoding pojedynczego adresu"""
        async with self.semaphore:  # Limit concurrent requests
            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'pl',
                'addressdetails': 0,  # Wyłącz szczegóły dla szybkości
                'extratags': 0       # Wyłącz dodatkowe tagi
            }
            
            # Próba 1: Główne zapytanie
            for attempt in range(MAX_RETRIES):
                try:
                    async with self.session.get(NOMINATIM_BASE_URL, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data and len(data) > 0:
                                result = data[0]
                                lat = float(result['lat'])
                                lon = float(result['lon'])
                                
                                # Walidacja granic Polski
                                if 49.0 <= lat <= 54.9 and 14.1 <= lon <= 24.2:
                                    logger.debug(f"Znaleziono współrzędne: {lat:.6f}, {lon:.6f}")
                                    return (lat, lon)
                                else:
                                    logger.warning(f"Współrzędne poza Polską: {lat}, {lon}")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout dla zapytania: {query} (próba {attempt + 1})")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Błąd geocodingu (próba {attempt + 1}): {e}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
            
            # Próba 2: Fallback query
            if fallback_query and fallback_query != query:
                logger.debug(f"Próba fallback: {fallback_query}")
                params['q'] = fallback_query
                
                try:
                    async with self.session.get(NOMINATIM_BASE_URL, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data and len(data) > 0:
                                result = data[0]
                                lat = float(result['lat'])
                                lon = float(result['lon'])
                                
                                if 49.0 <= lat <= 54.9 and 14.1 <= lon <= 24.2:
                                    logger.debug(f"Znaleziono współrzędne (fallback): {lat:.6f}, {lon:.6f}")
                                    return (lat, lon)
                                    
                except Exception as e:
                    logger.error(f"Błąd fallback geocodingu: {e}")
            
            # Opóźnienie między requestami
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
            
            logger.warning(f"Brak wyników geocodingu dla: {query}")
            return None
    
    async def geocode_batch_async(self, addresses: List[Dict]) -> List[Tuple[int, Optional[Tuple[float, float]]]]:
        """Async geocoding całego batcha"""
        tasks = []
        
        for address in addresses:
            address_id = address['id']
            
            # Sprawdź czy już ma współrzędne
            if address.get('latitude') and address.get('longitude'):
                tasks.append(asyncio.create_task(self._return_existing(address_id, address)))
                continue
            
            # Buduj zapytania
            main_query = self.build_optimized_query(address)
            fallback_query = self.build_fallback_query(address)
            
            if not main_query or main_query == "Polska":
                tasks.append(asyncio.create_task(self._return_none(address_id)))
                continue
            
            # Dodaj task geocodingu
            task = asyncio.create_task(self._geocode_with_id(address_id, main_query, fallback_query))
            tasks.append(task)
        
        # Wykonaj wszystkie taski równocześnie
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtruj wyjątki
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Błąd w batch geocoding: {result}")
                valid_results.append((None, None))
            else:
                valid_results.append(result)
        
        return valid_results
    
    async def _return_existing(self, address_id: int, address: Dict) -> Tuple[int, Optional[Tuple[float, float]]]:
        """Zwraca istniejące współrzędne"""
        lat = address.get('latitude')
        lon = address.get('longitude')
        return (address_id, (lat, lon) if lat and lon else None)
    
    async def _return_none(self, address_id: int) -> Tuple[int, Optional[Tuple[float, float]]]:
        """Zwraca None dla pustych adresów"""
        return (address_id, None)
    
    async def _geocode_with_id(self, address_id: int, main_query: str, fallback_query: str) -> Tuple[int, Optional[Tuple[float, float]]]:
        """Geocoding z ID adresu"""
        coordinates = await self.geocode_single_async(main_query, fallback_query)
        return (address_id, coordinates)

def get_addresses_without_coordinates_optimized(limit: int = 100) -> List[Dict]:
    """Zoptymalizowane pobieranie adresów bez współrzędnych"""
    supabase = get_supabase_client()
    
    try:
        # Pobierz tylko potrzebne kolumny dla wydajności
        result = supabase.table("addresses").select(
            "id, city, street_name, district, latitude, longitude"
        ).is_('latitude', 'null').is_('longitude', 'null').limit(limit).execute()
        
        if result.data:
            logger.info(f"📊 Pobrano {len(result.data)} adresów bez współrzędnych")
            return result.data
        else:
            logger.info("✅ Wszystkie adresy mają już współrzędne")
            return []
            
    except Exception as e:
        logger.error(f"❌ Błąd pobierania adresów: {e}")
        return []

def update_coordinates_batch(coordinates_data: List[Tuple[int, Optional[Tuple[float, float]]]]) -> Dict[str, int]:
    """Batch update współrzędnych w bazie danych"""
    supabase = get_supabase_client()
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    # Przygotuj dane do batch update
    updates = []
    for address_id, coordinates in coordinates_data:
        if coordinates:
            lat, lon = coordinates
            updates.append({
                "id": address_id,
                "latitude": lat,
                "longitude": lon
            })
    
    if not updates:
        stats["skipped"] = len(coordinates_data)
        return stats
    
    try:
        # Batch update - znacznie szybsze niż pojedyncze update
        for update_data in updates:
            try:
                result = supabase.table("addresses").update({
                    "latitude": update_data["latitude"],
                    "longitude": update_data["longitude"]
                }).eq("id", update_data["id"]).execute()
                
                if result.data:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    
            except Exception as e:
                logger.error(f"Błąd update adresu {update_data['id']}: {e}")
                stats["failed"] += 1
        
        # Policz pominięte
        stats["skipped"] = len(coordinates_data) - len(updates)
        
        logger.info(f"✅ Batch update: {stats['success']} sukces, {stats['failed']} błędów, {stats['skipped']} pominiętych")
        
    except Exception as e:
        logger.error(f"❌ Błąd batch update: {e}")
        stats["failed"] = len(updates)
        stats["skipped"] = len(coordinates_data) - len(updates)
    
    return stats

async def run_optimized_geocoding(max_addresses: int = None, batch_size: int = BATCH_SIZE) -> None:
    """Główna funkcja zoptymalizowanego geocodingu"""
    print("="*80)
    print("🚀 ZOPTYMALIZOWANY GEOCODER - ASYNC + BATCH PROCESSING")
    print("="*80)
    print(f"📊 Parametry:")
    print(f"   • Rozmiar batcha: {batch_size}")
    print(f"   • Maksymalne adresy: {max_addresses or 'wszystkie'}")
    print(f"   • Równoczesne requesty: {MAX_CONCURRENT_REQUESTS}")
    print(f"   • Opóźnienie: {DELAY_BETWEEN_REQUESTS}s")
    print("="*80)
    
    total_stats = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0
    }
    
    processed_count = 0
    batch_number = 1
    start_time = time.time()
    
    async with OptimizedGeocoder() as geocoder:
        while True:
            # Oblicz limit dla tego batcha
            remaining_limit = batch_size
            if max_addresses:
                remaining_limit = min(batch_size, max_addresses - processed_count)
                if remaining_limit <= 0:
                    break
            
            # Pobierz batch adresów
            addresses = get_addresses_without_coordinates_optimized(limit=remaining_limit)
            
            if not addresses:
                print("✅ Wszystkie adresy mają już współrzędne!")
                break
            
            print(f"\n🔄 BATCH {batch_number} - {len(addresses)} adresów")
            batch_start = time.time()
            
            # Async geocoding całego batcha
            coordinates_results = await geocoder.geocode_batch_async(addresses)
            
            # Batch update w bazie danych
            batch_stats = update_coordinates_batch(coordinates_results)
            
            # Aktualizuj statystyki
            for key in total_stats:
                if key in batch_stats:
                    total_stats[key] += batch_stats[key]
            
            total_stats["processed"] += len(addresses)
            processed_count += len(addresses)
            
            # Statystyki batcha
            batch_time = time.time() - batch_start
            addresses_per_second = len(addresses) / batch_time if batch_time > 0 else 0
            
            print(f"   ✅ Sukces: {batch_stats['success']}")
            print(f"   ❌ Błędy: {batch_stats['failed']}")
            print(f"   ⏭️ Pominięte: {batch_stats['skipped']}")
            print(f"   ⏱️ Czas: {batch_time:.1f}s ({addresses_per_second:.1f} adr/s)")
            
            # Sprawdź limity
            if max_addresses and processed_count >= max_addresses:
                break
            
            if len(addresses) < batch_size:
                print(f"📄 Ostatni batch")
                break
            
            batch_number += 1
            
            # Krótkie opóźnienie między batchami
            await asyncio.sleep(1)
    
    # Podsumowanie końcowe
    total_time = time.time() - start_time
    addresses_per_second = total_stats["processed"] / total_time if total_time > 0 else 0
    
    print("\n" + "="*80)
    print("📊 PODSUMOWANIE ZOPTYMALIZOWANEGO GEOCODINGU")
    print("="*80)
    print(f"📋 Łącznie przetworzonych: {total_stats['processed']}")
    print(f"✅ Pomyślnie geocodowanych: {total_stats['success']}")
    print(f"❌ Błędów geocodingu: {total_stats['failed']}")
    print(f"⏭️ Pominiętych: {total_stats['skipped']}")
    print(f"⏱️ Całkowity czas: {total_time:.1f}s")
    print(f"🚀 Wydajność: {addresses_per_second:.1f} adresów/sekundę")
    
    if total_stats['processed'] > 0:
        success_rate = (total_stats['success'] / total_stats['processed']) * 100
        print(f"📈 Skuteczność: {success_rate:.1f}%")
    
    print("="*80)

if __name__ == "__main__":
    """Test zoptymalizowanego geocodera"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Zoptymalizowany geocoder')
    parser.add_argument('--test', action='store_true', help='Uruchom test')
    parser.add_argument('--update', action='store_true', help='Aktualizuj współrzędne')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help=f'Rozmiar batcha (domyślnie: {BATCH_SIZE})')
    parser.add_argument('--max-addresses', type=int, help='Maksymalna liczba adresów')
    
    args = parser.parse_args()
    
    try:
        if args.test:
            print("🧪 TEST ZOPTYMALIZOWANEGO GEOCODERA")
            print("="*60)
            
            # Test z małą próbką
            asyncio.run(run_optimized_geocoding(max_addresses=10, batch_size=5))
            
        elif args.update:
            asyncio.run(run_optimized_geocoding(
                max_addresses=args.max_addresses,
                batch_size=args.batch_size
            ))
        else:
            print("🚀 ZOPTYMALIZOWANY GEOCODER")
            print("Użycie:")
            print("  python geocoder_optimized.py --test           # Test na 10 adresach")
            print("  python geocoder_optimized.py --update         # Aktualizuj wszystkie")
            print("  python geocoder_optimized.py --update --max-addresses 500  # Limit")
            
    except KeyboardInterrupt:
        print("\n⚠️ Przerwano przez użytkownika")
    except Exception as e:
        print(f"\n❌ Błąd krytyczny: {e}")
        logger.error(f"Błąd w geocoder_optimized: {e}", exc_info=True) 