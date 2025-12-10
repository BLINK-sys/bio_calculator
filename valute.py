import requests
import importlib

import info
import bio_rates_tenge


def valute():
    URL = "https://back.halykbank.kz/common/currency-history"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://halykbank.kz/exchange-rates"
    }

    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    data = response.json()
    
    if not data.get("result") or not data.get("data"):
        raise ValueError("Неверный формат ответа от API.")

    # Получаем данные для бизнеса (legalPersons)
    currency_history = data["data"].get("currencyHistory", [])
    if not currency_history:
        raise ValueError("Не найдены данные о курсах валют.")

    # Берем последние актуальные данные
    latest_data = currency_history[0]
    legal_persons = latest_data.get("legalPersons", {})
    
    # Сохраняем существующие курсы из info.py (если есть USD и EUR)
    try:
        existing_rates = info.exchange_rates.copy()
    except:
        existing_rates = {}
    
    # Парсим только RUB - курс продажи для бизнеса
    rub_data = legal_persons.get("RUB/KZT")
    if not rub_data:
        raise ValueError("Не найден курс RUB в данных API.")
    
    sell_rate = rub_data.get("sell")
    if sell_rate is None:
        raise ValueError("Не найден курс продажи RUB.")
    
    # Применяем ту же логику, что была в старом коде (добавляем 1%)
    rate_value = round(sell_rate + (sell_rate * 0.01), 2)
    
    # Обновляем только RUB, сохраняя остальные валюты
    exchange_rates_nb = existing_rates.copy()
    exchange_rates_nb["RUB"] = rate_value
    
    # Добавляем курсы USD и EUR из bio_rates_tenge.py
    try:
        importlib.reload(bio_rates_tenge)
        if hasattr(bio_rates_tenge, 'bio_rates_tenge'):
            bio_rates = bio_rates_tenge.bio_rates_tenge
            if 'USD' in bio_rates:
                exchange_rates_nb["USD"] = bio_rates["USD"]
            if 'EUR' in bio_rates:
                exchange_rates_nb["EUR"] = bio_rates["EUR"]
    except Exception as e:
        print(f"Предупреждение: не удалось загрузить курсы из bio_rates_tenge.py: {e}")

    print(exchange_rates_nb)

    # Записываем в info.py
    with open("info.py", "w", encoding="utf-8") as file:
        file.write(f"exchange_rates = {exchange_rates_nb}\n")

    # Перезагружаем модуль info для получения обновленных курсов
    importlib.reload(info)
    
    print("Курсы валют сохранены в info.py (RUB из Halyk Bank, USD/EUR из bio_rates_tenge.py)")
    exchange_rates = info.exchange_rates
    return exchange_rates


if __name__ == "__main__":
    valute()
