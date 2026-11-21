"""Берёт официальный курс тенге с сайта Национального банка РК и пишет rate.json.

Файл переписывается, только если курс или дата изменились.
При любой ошибке скрипт падает с ненулевым кодом: GitHub пришлёт письмо о сбое,
а на сайте останется последний сохранённый курс.
"""
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FEED = 'https://nationalbank.kz/rss/rates_all.xml'
OUT = 'rate.json'
CODES = ('USD', 'EUR')
SANE = (200.0, 2000.0)  # грубая проверка: курс в тенге за 1 единицу валюты


def fetch(url):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (rate bot)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f'НБРК не ответил: {last!r}')


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    rates, dates = {}, set()
    for item in root.iter('item'):
        code = (item.findtext('title') or '').strip()
        if code not in CODES:
            continue
        value = float((item.findtext('description') or '').replace(',', '.'))
        quant = float(item.findtext('quant') or 1)
        rates[code.lower()] = round(value / quant, 4)
        dates.add((item.findtext('pubDate') or '').strip())
    missing = [c for c in CODES if c.lower() not in rates]
    if missing:
        raise SystemExit(f'В ленте НБРК нет курса: {missing}')
    for code, v in rates.items():
        if not SANE[0] <= v <= SANE[1]:
            raise SystemExit(f'Странный курс {code}: {v}')
    if len(dates) != 1:
        raise SystemExit(f'Разные даты в ленте: {dates}')
    date = datetime.strptime(dates.pop(), '%d.%m.%Y').date()
    almaty_today = (datetime.now(timezone.utc) + timedelta(hours=5)).date()
    if not timedelta(days=-3) <= date - almaty_today <= timedelta(days=1):
        raise SystemExit(f'Дата курса {date} далеко от сегодняшней {almaty_today}')
    return date.isoformat(), rates


def main():
    date, rates = parse(fetch(FEED))
    data = {
        'source': 'Национальный банк Республики Казахстан, nationalbank.kz',
        'date': date,
        'usd': rates['usd'],
        'eur': rates['eur'],
    }
    try:
        with open(OUT, encoding='utf-8') as f:
            old = json.load(f)
    except (FileNotFoundError, ValueError):
        old = None
    if old == data:
        print('Курс не изменился:', data)
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('Новый курс:', data)


if __name__ == '__main__':
    sys.exit(main())
