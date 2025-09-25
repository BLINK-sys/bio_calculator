import requests
from bs4 import BeautifulSoup
import re

def valute_bio():
    """
    Парсит курсы валют с сайта BIO (EUR/USD к рублю)
    Возвращает курсы BIO для конвертации в рубли
    """
    URL = "https://portal.holdingbio.ru/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ищем курсы валют на странице
        bio_rates = {}
        
        # Поиск по различным паттернам
        patterns = [
            r'YE\s*EUR.*?(\d+,\d+)\s*P',
            r'EUR.*?(\d+,\d+)\s*P',
            r'(\d+,\d+)\s*P.*?EUR'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, soup.get_text(), re.IGNORECASE | re.DOTALL)
            if matches:
                try:
                    rate_str = matches[0].replace(',', '.')
                    bio_rates['EUR'] = float(rate_str)
                    print(f"Найден курс EUR: {bio_rates['EUR']}")
                    break
                except ValueError:
                    continue
        
        # Поиск USD курса
        usd_patterns = [
            r'YE\s*USD.*?(\d+,\d+)\s*P',
            r'USD.*?(\d+,\d+)\s*P',
            r'(\d+,\d+)\s*P.*?USD'
        ]
        
        for pattern in usd_patterns:
            matches = re.findall(pattern, soup.get_text(), re.IGNORECASE | re.DOTALL)
            if matches:
                try:
                    rate_str = matches[0].replace(',', '.')
                    bio_rates['USD'] = float(rate_str)
                    print(f"Найден курс USD: {bio_rates['USD']}")
                    break
                except ValueError:
                    continue
        
        # Если не нашли, используем значения по умолчанию
        if not bio_rates:
            print("⚠️ Курсы BIO не найдены на странице, используем значения по умолчанию")
            bio_rates = {'EUR': 109.0, 'USD': 93.0}
        
        print(f"Итоговые курсы BIO: {bio_rates}")
        return bio_rates
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге курсов BIO: {e}")
        print("Используем значения по умолчанию")
        return {'EUR': 109.0, 'USD': 93.0}

def convert_bio_rates_to_tenge(bio_rates, rub_to_tenge_rate):
    """
    Конвертирует курсы BIO (рубль) в тенге
    bio_rates: {'USD': 93.0, 'EUR': 109.0} - курсы к рублю
    rub_to_tenge_rate: курс рубля к тенге
    """
    converted_rates = {}
    
    for currency, rate_in_rub in bio_rates.items():
        # Конвертируем: USD/EUR → рубль → тенге
        rate_in_tenge = rate_in_rub * rub_to_tenge_rate
        converted_rates[currency] = round(rate_in_tenge, 2)
        print(f"BIO {currency}: {rate_in_rub} руб → {rate_in_tenge:.2f} тенге")
    
    return converted_rates

def get_bio_rates():
    """
    Получает курсы BIO и сохраняет их в файл
    """
    rates = valute_bio()
    
    # Сохраняем курсы BIO в отдельный файл
    with open("bio_rates.py", "w", encoding="utf-8") as file:
        file.write(f"bio_rates = {rates}\n")
    
    print("Курсы BIO сохранены в bio_rates.py")
    return rates

def get_bio_rates_in_tenge():
    """
    Получает курсы BIO и конвертирует их в тенге
    Требует курс рубля к тенге из МИГ.кз
    """
    try:
        # Получаем курсы BIO (в рублях)
        bio_rates = valute_bio()
        
        # Получаем курс рубля к тенге из МИГ.кз
        import valute
        import info
        import importlib
        
        # Обновляем курсы МИГ.кз
        valute.valute()
        importlib.reload(info)
        
        # Получаем курс рубля к тенге
        rub_to_tenge = info.exchange_rates.get('RUB', 1.0)
        print(f"Курс рубля к тенге (МИГ.кз): {rub_to_tenge}")
        
        # Конвертируем курсы BIO в тенге
        bio_rates_tenge = convert_bio_rates_to_tenge(bio_rates, rub_to_tenge)
        
        # Сохраняем конвертированные курсы
        with open("bio_rates_tenge.py", "w", encoding="utf-8") as file:
            file.write(f"bio_rates_tenge = {bio_rates_tenge}\n")
        
        print("Курсы BIO в тенге сохранены в bio_rates_tenge.py")
        return bio_rates_tenge
        
    except Exception as e:
        print(f"❌ Ошибка конвертации BIO курсов: {e}")
        # Возвращаем значения по умолчанию
        return {'USD': 93.0, 'EUR': 109.0}

if __name__ == "__main__":
    print("=== Тестирование BIO курсов ===")
    
    # Тест 1: Получение курсов BIO в рублях
    print("\n1. Получение курсов BIO (в рублях):")
    rates_rub = get_bio_rates()
    print(f"Курсы BIO в рублях: {rates_rub}")
    
    # Тест 2: Конвертация в тенге
    print("\n2. Конвертация BIO курсов в тенге:")
    rates_tenge = get_bio_rates_in_tenge()
    print(f"Курсы BIO в тенге: {rates_tenge}")