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


def send_message(text: str, token: str, chat_id: str):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    while True:
        try:
            requests.get(url, params={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            })
        except requests.exceptions.RequestException as e:
            logging.exception(f'TG sendMessage error: {e}')
            time.sleep(1)
            continue
        else:
            break
    time.sleep(1)
