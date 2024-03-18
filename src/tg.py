import datetime as dt
import logging
import time

import requests

from dto import Message


month_names = {
    1: 'января',
    2: 'февраля',
    3: 'марта',
    4: 'апреля',
    5: 'мая',
    6: 'июня',
    7: 'июля',
    8: 'августа',
    9: 'сентября',
    10: 'октября',
    11: 'ноября',
    12: 'декабря',
}


def add_emoji(text: str) -> str:
    emoji = ''
    if 'отбой' in text.lower():
        emoji = '🟢'
    elif 'обстрел' in text.lower():
        emoji = '💥'
    elif 'ракетная опасность' in text.lower():
        emoji = '🚀'
    elif 'авиационная опасность' in text.lower():
        emoji = '✈️'

    if emoji:
        return f'{emoji} {text}'
    else:
        return text


def prep_date(date: dt.datetime) -> str:
    return f'{date.day} {month_names[date.month]} {date.strftime("%Y %H:%M")}'


def prep_msg_text(msg: Message) -> str:
    text = msg.text.removeprefix('РСЧС:').lstrip().removeprefix('Внимание!').lstrip().replace('\r\n', ' ')
    return f'{add_emoji(text)}\n' \
           f'<i>{prep_date(msg.date)}</i>'


def prep_stat_text(date, in_stats: dict) -> str:
    """
    Формирует текст поста для канала статистики
    :param date: дата, за которую собрана статистика
    :param in_stats: словарь вида {'Вся область': {'shelling': [date, ...], 'missile':  [date, ...], 'avia':  [date, ...]}, ...}
    :return: текст сообщения
    """
    # сортируем регионы по алфавиту
    day_stats = {n: s for n, s in sorted(in_stats.items(), key=lambda i: i[0])}

    # выносим пункт "Вся область" на первое место
    all_region_value = day_stats.pop('Вся область', None)
    if all_region_value is not None:
        day_stats = {'Вся область': all_region_value, **day_stats}

    # в каждом районе сортируем тревоги, чтобы везде было одинаково
    for district in day_stats.keys():
        day_stats[district] = {n: s for n, s in sorted(day_stats[district].items(), key=lambda i: i[0])}

    # в каждом типе предупреждений сортируем даты по возрастанию
    for district in day_stats.keys():
        for notf_type in day_stats[district].keys():
            day_stats[district][notf_type] = sorted(day_stats[district][notf_type])

    # вычисляем длину самого большого названия района, чтобы выровнять все названия по правому краю
    max_len = max(map(len, day_stats.keys()))
    emoji_map = {'shelling': '💥', 'missile': '🚀', 'avia': '✈'}
    # форматируем дату в вид 17 марта 2024
    text = f'📆<b> {date.day} {month_names[date.month]} {date.year}</b>\n<pre>'
    for district, notifications in day_stats.items():
        # склеиваем счётчики тревог во что-то типа 🚀2 💥1 ✈3
        text_stats = ' '.join(
            f'{emoji_map[notf_type]}{len(dates)}'
            for notf_type, dates in notifications.items() if dates
        )
        # выравниваем названия района по правому краю
        # и приклеиваем счётчики тревог и журнал времени.
        # Что-то типа
        # '     Вся область  🚀1 \n'
        # '         🚀 в 23:36 '
        date_stats = '\n'.join(
            f'{emoji_map[notf_type]} в {date.strftime("%H:%M")}'.rjust(max_len)
            for notf_type, dates in notifications.items() if dates for date in dates
        )
        text += f'{district.rjust(max_len)}  {text_stats} \n{date_stats}\n\n'
    text += '</pre>'
    return text


def send_message(text: str, token: str, chat_id: str, silent=False):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    while True:
        try:
            requests.get(url, params={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_notification": silent
            })
        except requests.exceptions.RequestException as e:
            logging.exception(f'TG sendMessage error: {e}')
            time.sleep(1)
            continue
        else:
            break
    time.sleep(1)
