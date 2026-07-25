import datetime as dt
import json
import logging
import time
import os
from typing import List

import pytz
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter, Retry

load_dotenv()
from dto import Message
import tg
from safe_scheduler import SafeScheduler
import stats


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s")

region_ids = json.loads(os.environ['GOCHS_REGIONS'])
locale = pytz.timezone('Europe/Moscow')
last_date = dt.datetime.now(tz=locale)  # - dt.timedelta(hours=24)

# МЧС периодически рвёт TLS-соединение (SSLZeroReturnError: TLS/SSL connection has been closed).
# Одиночный обрыв переигрываем прямо на транспорте, чтобы он вообще не поднимался выше.
# GET идемпотентен и по умолчанию входит в Retry.allowed_methods.
MCHS_TIMEOUT = (5, 10)  # (connect, read) — без него зависший коннект блокирует весь планировщик
mchs_session = requests.Session()
mchs_session.mount('https://', HTTPAdapter(max_retries=Retry(
    total=2,  # 2 ретрая = до 3 попыток на вызов
    backoff_factor=0.5,  # паузы между попытками: 0с, 1с
    status_forcelist=(500, 502, 503, 504),
)))

# Сколько неудач подряд терпим, прежде чем написать админу.
# Одиночные обрывы не эскалируем: следующий тик через 10 секунд подберёт сообщения сам.
ALERT_AFTER_FAILURES = 3
mchs_failures = 0

# Дневная статистика запускается раз в сутки, поэтому при сбое её перезапускает
# SafeScheduler (через 5 с). Ограничиваем число попыток, иначе при долгой недоступности
# МЧС джоба будет крутиться в цикле бесконечно.
STATS_MAX_ATTEMPTS = 5
stats_attempts = 0


def get_mchs_notifications(region_ids: List[str]):
    global mchs_failures

    try:
        resp = mchs_session.get(
            url='https://push.mchs.ru/new-history',
            params={
                'region': [','.join(region_ids)],
                'type': 'new'  # также доступен 'all', он возвращает 30 сообщений и у него другая структура
            },
            headers={
                'Accept-Encoding': 'gzip',
                'Content-MD5': 'fb62712c9475d5f8fac8418dcb6762a2',
                'Content-Type': 'application/json; charset=utf-8',
                'Host': 'push.mchs.ru',
                'User-Agent': 'Dart/3.2 (dart:io)'
            },
            timeout=MCHS_TIMEOUT
        )
        data = resp.json()
    except requests.exceptions.RequestException as e:
        mchs_failures += 1
        if isinstance(e, requests.exceptions.JSONDecodeError):
            err_text = f'MCHS json decode error: Body: {resp.text}. Exception: {e}'
        else:
            err_text = f'MCHS notifications request error: {e}'

        logging.exception(f'{err_text} (failures in a row: {mchs_failures})')
        # пишем админу только на переходе в состояние "недоступен", а не на каждый блип
        if mchs_failures == ALERT_AFTER_FAILURES:
            tg.send_message(
                text=f'{err_text}\n\nНеудачных попыток подряд: {mchs_failures}',
                token=os.environ['TG_BOT_TOKEN'],
                chat_id=os.environ['TG_ADMIN_CHAT_ID']
            )
        return None
    else:
        if mchs_failures >= ALERT_AFTER_FAILURES:
            tg.send_message(
                text=f'✅ Связь с МЧС восстановлена. Неудачных попыток было: {mchs_failures}',
                token=os.environ['TG_BOT_TOKEN'],
                chat_id=os.environ['TG_ADMIN_CHAT_ID']
            )
        mchs_failures = 0
        return data


def process_new_mchs_messages():
    global last_date

    logging.info('Checking new messages')
    notifications = get_mchs_notifications(region_ids.keys())
    if not notifications:
        return

    if notifications['code'] != 200:
        err_text = f'MCHS notifications request error: ' \
                   f'code {notifications["code"]}: {notifications["answer"]}'
        logging.error(err_text)
        tg.send_message(
            text=err_text,
            token=os.environ['TG_BOT_TOKEN'],
            chat_id=os.environ['TG_ADMIN_CHAT_ID']
        )
        return

    messages = map(Message.from_dict, notifications['list'])
    messages = filter(lambda m: m.date >= last_date, messages)
    messages = sorted(messages, key=lambda m: m.date)

    for message in messages:
        logging.info(message)
        last_date = message.date + dt.timedelta(seconds=1)

        tg.send_message(
            text=tg.prep_msg_text(message),
            token=os.environ['TG_BOT_TOKEN'],
            chat_id=os.environ['TG_CHAT_ID']
        )
    logging.info('Waiting for next message check...')


def retry_stats_later(reason: str):
    """
    Просит SafeScheduler перезапустить сбор статистики через 5 секунд (бросая исключение).
    Исчерпав STATS_MAX_ATTEMPTS попыток, выходит штатно: schedule вернёт джобу
    на завтрашние 08:00, и бесконечного цикла ретраев не получится.
    """
    global stats_attempts

    stats_attempts += 1
    if stats_attempts >= STATS_MAX_ATTEMPTS:
        stats_attempts = 0
        logging.error(f'Stats job gave up after {STATS_MAX_ATTEMPTS} attempts: {reason}')
        tg.send_message(
            text=f'Статистика за вчера не собрана: {reason}\n\n'
                 f'Попыток: {STATS_MAX_ATTEMPTS}. Следующая — завтра в 08:00.',
            token=os.environ['TG_BOT_TOKEN'],
            chat_id=os.environ['TG_ADMIN_CHAT_ID']
        )
        return

    raise RuntimeError(f'{reason}. Attempt {stats_attempts}/{STATS_MAX_ATTEMPTS}, retry in 5s')


def process_stats():
    global stats_attempts

    logging.info('Calculating tomorrow stats')
    notifications = get_mchs_notifications(region_ids.keys())
    if not notifications:
        # get_mchs_notifications уже залогировал ошибку
        logging.warning('For some reason there are no messages')
        retry_stats_later('No response from MCHS')
        return

    if notifications['code'] != 200:
        err_text = f'MCHS notifications request error: ' \
                   f'code {notifications["code"]}: {notifications["answer"]}'
        logging.error(err_text)
        retry_stats_later(err_text)
        return

    stats_attempts = 0
    messages = map(Message.from_dict, notifications['list'])

    # фильтруем сообщения по дате (нас интересуют только вчерашние)
    now = dt.datetime.now(tz=locale)
    yesterday_24 = locale.localize(dt.datetime(now.year, now.month, now.day))  # https://russianpenguin.ru/2019/09/11/python-%D1%87%D0%B5%D0%BC-%D0%BF%D0%BB%D0%BE%D1%85-datetime-replace/
    yesterday_00 = yesterday_24 - dt.timedelta(days=1)
    messages = filter(lambda m: yesterday_00 <= m.date < yesterday_24, messages)

    # отфильтровываем только сообщения с тревогами
    messages = list(filter(lambda m: m.notf_type.general == 'alarm', messages))

    day_stats = {}
    for message in messages:
        logging.info(message)
        day_stats = stats.update_stats(message, stats.bel_region_districts, day_stats)

    tg.send_message(
        text=tg.prep_stat_text(yesterday_00, day_stats),
        token=os.environ['TG_BOT_TOKEN'],
        chat_id=os.environ['TG_STAT_CHAT_ID']
    )
    logging.info('Waiting for next message check...')


def healthcheck():
    tg.send_message(
        text='Healthcheck',
        token=os.environ['TG_BOT_TOKEN'],
        chat_id=os.environ['TG_ADMIN_CHAT_ID'],
        silent=True
    )


if __name__ == '__main__':
    logging.info('МЧС31 Bot started')
    tg.send_message(
        text='МЧС31 Bot started',
        token=os.environ['TG_BOT_TOKEN'],
        chat_id=os.environ['TG_ADMIN_CHAT_ID']
    )

    scheduler = SafeScheduler(reschedule_on_failure=True, seconds_after_failure=5)
    scheduler.every(10).seconds.do(process_new_mchs_messages)
    scheduler.every().day.at("08:00", locale).do(process_stats)
    scheduler.every(60).minutes.do(healthcheck)
    while True:
        scheduler.run_pending()
        time.sleep(1)
