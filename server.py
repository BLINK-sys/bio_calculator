from flask import Flask, request, jsonify, send_from_directory, send_file
import requests
import json
from datetime import datetime, date
from io import BytesIO
import sqlite3
import os
import importlib
import csv

# Попытка импорта pandas, если не удается - используем CSV
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ pandas недоступен, отчеты будут в формате CSV")

app = Flask(__name__)

# Импортируем модули для работы с курсами валют
import valute
import info

# Параметры формулы по умолчанию
DEFAULT_FORMULA_PARAMS = {
    'divider': 1.2,
    'multiplier': 1.12,
    'nds': 1.18,
    'base30': 7500,           # Базовая ставка (фиксированная)
    'rate30': 179,            # Тариф город+город за кг свыше 30
    'pickup30': 10000,        # Забор со склада БИО
    'pickupRate30': 20,       # Тариф забора за кг свыше 30
    'warehouseCount': 26,     # Количество единиц для складских услуг
    'warehouseRate': 400,     # Тариф за единицу складских услуг
    'deliveryCity30': 4000,   # Доставка по Астане
    'cityRate30': 15,         # Тариф доставки по Астане за кг свыше 30
    'rate300': 164,           # Тариф город+город 300-1000 кг
    'rate1000': 143,          # Тариф город+город свыше 1000 кг
    'volumetricFactor': 200   # Коэффициент объемного веса (логисты БИО)
}

def update_exchange_rates():
    """
    Обновляет курсы валют через valute.py и перезагружает info.py
    """
    try:
        # Запускаем обновление курсов
        valute.valute()
        
        # Перезагружаем модуль info для получения обновленных курсов
        importlib.reload(info)
        
        print(f"Курсы валют обновлены: {info.exchange_rates}")
        return info.exchange_rates
    except Exception as e:
        print(f"Ошибка обновления курсов валют: {e}")
        return info.exchange_rates

def calculate_delivery_cost(weight_kg, volume_m3, params):
    """
    Рассчитывает стоимость доставки с настраиваемыми параметрами
    Точное соответствие оригинальному скрипту
    """
    # Объемный вес = объем * 200 (как в оригинале)
    volumetric_weight = volume_m3 * params.get('volumetricFactor', 200)
    
    # Выбираем больший вес для расчета (как в оригинале)
    delivery_weight = max(weight_kg, volumetric_weight)
    
    if delivery_weight <= 30:
        # До 30 кг: 7500 + 10000 + (26*400) + 4000 = 31,900 тг
        # В оригинале: return 31900
        return params.get('delivery30', 31900)
        
    elif delivery_weight <= 300:
        # 30-300 кг: 7500 + (вес-30)*179 + 10000 + (вес-30)*20 + 26*400 + 4000 + (вес-30)*15
        excess_weight = delivery_weight - 30
        warehouse_total = params.get('warehouseCount', 26) * params.get('warehouseRate', 400)
        return (params.get('base30', 7500) + 
                (excess_weight * params.get('rate30', 179)) + 
                params.get('pickup30', 10000) + 
                (excess_weight * params.get('pickupRate30', 20)) + 
                warehouse_total +  # 26*400 = 10400
                params.get('deliveryCity30', 4000) + 
                (excess_weight * params.get('cityRate30', 15)))
                
    elif delivery_weight <= 1000:
        # 300-1000 кг: сумма трех компонентов (как в оригинале)
        excess_300 = delivery_weight - 300
        excess_1000 = max(0, delivery_weight - 1000)
        warehouse_total = params.get('warehouseCount', 26) * params.get('warehouseRate', 400)
        
        # Компонент 1: город+город
        component1 = (params.get('base30', 7500) + 
                   (270 * params.get('rate30', 179)) +  # 270 = 300 - 30
                   (excess_300 * params.get('rate300', 164)) + 
                   (excess_1000 * params.get('rate1000', 143)))
        
        # Компонент 2: забор склад БИО
        component2 = (params.get('pickup30', 10000) + 
                   (270 * params.get('pickupRate30', 20)) +  # 270 = 300 - 30
                   (excess_300 * 15) + excess_1000 + 
                   warehouse_total)  # 26*400 = 10400
        
        # Компонент 3: доставка по Астане
        component3 = (params.get('deliveryCity30', 4000) + 
                   (270 * params.get('cityRate30', 15)) +  # 270 = 300 - 30
                   (excess_300 * 2) + (excess_1000 * 9) + 
                   warehouse_total)  # 26*400 = 10400
        
        return component1 + component2 + component3
        
    else:
        # Свыше 1000 кг - используем формулу для 1000 кг (без рекурсии, как в оригинале)
        excess_300 = 700  # 1000 - 300
        excess_1000 = 0   # 1000 - 1000 = 0
        warehouse_total = params.get('warehouseCount', 26) * params.get('warehouseRate', 400)
        
        # Компонент 1: город+город
        component1 = (params.get('base30', 7500) + 
                     (270 * params.get('rate30', 179)) +  # 270 = 300 - 30
                     (excess_300 * params.get('rate300', 164)) + 
                     (excess_1000 * params.get('rate1000', 143)))
                     
        # Компонент 2: забор склад БИО
        component2 = (params.get('pickup30', 10000) + 
                     (270 * params.get('pickupRate30', 20)) +  # 270 = 300 - 30
                     (excess_300 * 15) + excess_1000 + 
                     warehouse_total)  # 26*400 = 10400
                     
        # Компонент 3: доставка по Астане
        component3 = (params.get('deliveryCity30', 4000) + 
                     (270 * params.get('cityRate30', 15)) +  # 270 = 300 - 30
                     (excess_300 * 2) + (excess_1000 * 9) + 
                     warehouse_total)  # 26*400 = 10400
        
        return component1 + component2 + component3

def calculate_volume_from_dimensions(length, width, height):
    """
    Рассчитывает объем из габаритов
    length, width, height - размеры в мм
    возвращает объем в м³
    """
    if length <= 0 or width <= 0 or height <= 0:
        return 0
    
    try:
        # Преобразуем мм в метры и рассчитываем объем
        length_m = length / 1000
        width_m = width / 1000
        height_m = height / 1000
        volume = length_m * width_m * height_m
        return volume
    except (ValueError, IndexError):
        return 0

def save_calculation_to_db(product_name, final_price):
    """
    Сохраняет результаты расчета в базу данных SQLite3
    Только: наименование товара, финальная цена, дата расчета
    """
    try:
        conn = sqlite3.connect('calculations.db')
        cursor = conn.cursor()
        
        # Создаем таблицу если её нет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                final_price REAL NOT NULL,
                calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Вставляем данные расчета
        cursor.execute('''
            INSERT INTO calculations (product_name, final_price)
            VALUES (?, ?)
        ''', (product_name, final_price))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Расчет сохранен в базу: {product_name} - {final_price} KZT")
        
    except Exception as e:
        print(f"❌ Ошибка сохранения в базу: {e}")
        # Не прерываем выполнение при ошибке сохранения

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/exchange-rates')
def get_exchange_rates():
    """API для получения курсов валют из info.py"""
    try:
        # Обновляем курсы валют при каждом запросе
        current_rates = update_exchange_rates()
        
        return jsonify({
            'rates': current_rates,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'error': f'Ошибка получения курсов валют: {str(e)}'
        }), 500

@app.route('/api/formula-params')
def get_formula_params():
    """API для получения параметров формулы по умолчанию"""
    return jsonify({
        'params': DEFAULT_FORMULA_PARAMS,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/calculate-price', methods=['POST'])
def calculate_price():
    """API для расчета стоимости товара с настраиваемыми параметрами"""
    try:
        data = request.get_json()
        
        # Получаем данные из запроса
        product_name = data.get('productName', 'Неизвестный товар')
        original_price = float(data.get('originalPrice', 0))
        currency = data.get('currency', 'KZT')
        weight = float(data.get('weight', 0))
        dimensions_data = data.get('dimensions', {})
        length = float(dimensions_data.get('length', 0))
        width = float(dimensions_data.get('width', 0))
        height = float(dimensions_data.get('height', 0))
        
        # Получаем настраиваемые параметры формулы
        formula_params = data.get('formulaParams', {})
        
        # Валидация данных
        if not product_name or original_price <= 0 or not currency or weight <= 0 or length <= 0 or width <= 0 or height <= 0:
            return jsonify({
                'error': 'Неверные данные. Проверьте все поля товара.'
            }), 400
        
        # Расчет объема
        volume = calculate_volume_from_dimensions(length, width, height)
        if volume == 0:
            return jsonify({
                'error': 'Неверные данные габаритов. Проверьте длину, ширину и высоту.'
            }), 400
        
        # Обновляем курсы валют и получаем актуальные
        current_rates = update_exchange_rates()
        
        # Расчет стоимости доставки
        delivery_cost = calculate_delivery_cost(weight, volume, formula_params)
        
        # Получение курса валюты из обновленных данных
        exchange_rate = current_rates.get(currency, 1)
        
        # Применение настраиваемой формулы: (X/divider * курс * multiplier + доставка) * nds
        divider = formula_params.get('divider', 1.2)
        multiplier = formula_params.get('multiplier', 1.12)
        nds = formula_params.get('nds', 1.18)
        
        converted_price = original_price / divider * exchange_rate * multiplier
        price_with_delivery = converted_price + delivery_cost
        final_price = price_with_delivery * nds
        
        # Расчет веса для доставки
        volumetric_factor = formula_params.get('volumetricFactor', 200)
        delivery_weight = max(weight, volume * volumetric_factor)
        
        # Сохраняем расчет в базу данных
        save_calculation_to_db(
            product_name=product_name,
            final_price=final_price
        )
        
        return jsonify({
            'productName': product_name,
            'originalPrice': original_price,
            'currency': currency,
            'exchangeRate': exchange_rate,
            'convertedPrice': round(converted_price, 2),
            'volume': round(volume, 4),
            'deliveryWeight': round(delivery_weight, 2),
            'deliveryCost': round(delivery_cost, 2),
            'priceWithDelivery': round(price_with_delivery, 2),
            'finalPrice': round(final_price, 2),
            'formulaParams': formula_params,
            'calculationSteps': {
                'step1': f'Конвертация: {original_price} / {divider} × {exchange_rate} × {multiplier} = {converted_price:.2f}',
                'step2': f'Добавление доставки: {converted_price:.2f} + {delivery_cost:.2f} = {price_with_delivery:.2f}',
                'step3': f'НДС: {price_with_delivery:.2f} × {nds} = {final_price:.2f}'
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Ошибка расчета: {str(e)}'
        }), 500

@app.route('/api/update-formula-params', methods=['POST'])
def update_formula_params():
    """API для обновления параметров формулы"""
    try:
        data = request.get_json()
        new_params = data.get('params', {})
        
        global DEFAULT_FORMULA_PARAMS
        DEFAULT_FORMULA_PARAMS.update(new_params)
        
        return jsonify({
            'message': 'Параметры формулы обновлены',
            'params': DEFAULT_FORMULA_PARAMS,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Ошибка обновления параметров: {str(e)}'
        }), 500

@app.route('/api/calculation-history')
def get_calculation_history():
    """API для получения истории расчетов из базы данных"""
    try:
        conn = sqlite3.connect('calculations.db')
        cursor = conn.cursor()
        
        # Получаем последние 50 расчетов, отсортированных по дате
        cursor.execute('''
            SELECT id, product_name, final_price, calculation_date
            FROM calculations 
            ORDER BY calculation_date DESC 
            LIMIT 50
        ''')
        
        calculations = []
        for row in cursor.fetchall():
            calculations.append({
                'id': row[0],
                'productName': row[1],
                'finalPrice': row[2],
                'calculationDate': row[3]
            })
        
        conn.close()
        
        return jsonify({
            'calculations': calculations,
            'total': len(calculations),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Ошибка получения истории: {str(e)}'
        }), 500

@app.route('/api/download-report', methods=['POST'])
def download_report():
    """API для скачивания отчета в Excel по выбранному диапазону дат"""
    try:
        data = request.get_json()
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        
        if not start_date or not end_date:
            return jsonify({
                'error': 'Необходимо указать начальную и конечную дату'
            }), 400
        
        # Получаем данные за выбранный период
        query = '''
            SELECT product_name, final_price, calculation_date
            FROM calculations 
            WHERE DATE(calculation_date) BETWEEN ? AND ?
            ORDER BY calculation_date DESC
        '''
        
        if PANDAS_AVAILABLE:
            # Подключаемся к базе данных для pandas
            conn = sqlite3.connect('calculations.db')
            df = pd.read_sql_query(query, conn, params=[start_date, end_date])
            conn.close()

        
        if PANDAS_AVAILABLE:
            if df.empty:
                return jsonify({
                    'error': 'За выбранный период данных не найдено'
                }), 404
            
            # Переименовываем колонки для красивого отображения
            df.columns = ['Наименование товара', 'Финальная цена (KZT)', 'Дата расчета']
            
            # Форматируем дату
            df['Дата расчета'] = pd.to_datetime(df['Дата расчета']).dt.strftime('%d.%m.%Y %H:%M')
            
            # Форматируем цену
            df['Финальная цена (KZT)'] = df['Финальная цена (KZT)'].round(2)
            
            # Создаем Excel файл в памяти
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Отчет по расчетам', index=False)
                
                # Получаем рабочий лист для форматирования
                worksheet = writer.sheets['Отчет по расчетам']
                
                # Автоматически подгоняем ширину колонок
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            output.seek(0)
            
            # Формируем имя файла с датами
            start_date_formatted = start_date.replace('-', '.')
            end_date_formatted = end_date.replace('-', '.')
            filename = f'Отчет_расчетов_{start_date_formatted}-{end_date_formatted}.xlsx'
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )

        else:
            # Альтернативный способ без pandas - CSV
            cursor = conn.cursor()
            cursor.execute(query, [start_date, end_date])
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return jsonify({
                    'error': 'За выбранный период данных не найдено'
                }), 404
            
            # Создаем CSV файл в памяти
            output = BytesIO()
            writer = csv.writer(output)
            
            # Записываем заголовки
            writer.writerow(['Наименование товара', 'Финальная цена (KZT)', 'Дата расчета'])
            
            # Записываем данные
            for row in rows:
                # Форматируем дату
                try:
                    date_obj = datetime.fromisoformat(row[2].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%d.%m.%Y %H:%M')
                except:
                    formatted_date = row[2]
                
                # Форматируем цену
                try:
                    formatted_price = round(float(row[1]), 2)
                except:
                    formatted_price = row[1]
                
                writer.writerow([row[0], formatted_price, formatted_date])
            
            output.seek(0)
            
            # Формируем имя файла с датами
            start_date_formatted = start_date.replace('-', '.')
            end_date_formatted = end_date.replace('-', '.')
            filename = f'Отчет_расчетов_{start_date_formatted}-{end_date_formatted}.csv'
            
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
        
    except Exception as e:
        return jsonify({
            'error': f'Ошибка создания отчета: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("🚀 Запуск сервера калькулятора стоимости товара...")
    print("📊 Доступные API endpoints:")
    print("   - GET  /api/exchange-rates - получение курсов валют (автообновление)")
    print("   - GET  /api/formula-params - получение параметров формулы")
    print("   - POST /api/calculate-price - расчет стоимости товара (с сохранением в БД)")
    print("   - GET  /api/calculation-history - история расчетов")
    print("   - POST /api/download-report - скачивание отчета в Excel")
    print("   - POST /api/update-formula-params - обновление параметров формулы")
    print("🌐 Веб-интерфейс доступен по адресу: http://localhost:5000")
    print("💾 Все расчеты автоматически сохраняются в SQLite3 базу данных")
    print("📊 Отчеты в Excel доступны по выбранному диапазону дат")
    
    # Обновляем курсы валют при запуске сервера
    print("💱 Обновление курсов валют при запуске...")
    update_exchange_rates()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
