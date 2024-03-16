import datetime as dt
import json
import logging
import time
import os
from typing import List

import pytz
from dotenv import load_dotenv
import requests

load_dotenv()
from dto import Message
import tg
from safe_scheduler import SafeScheduler
import stats


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s")

region_ids = json.loads(os.environ['GOCHS_REGIONS'])
# locale = dt.timezone(dt.timedelta(hours=3))
locale = pytz.timezone('Europe/Moscow')
last_date = dt.datetime.now(tz=locale)  # - dt.timedelta(hours=24)


def get_mchs_notifications(region_ids: List[str]):
    try:
        resp = requests.get(
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
            }
        )
        return resp.json()
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.JSONDecodeError):
            err_text = f'MCHS json decode error: Body: {resp.text}. Exception: {e}'
        elif isinstance(e, requests.exceptions.RequestException):
            err_text = f'MCHS notifications request error: {e}'
        else:
            err_text = f'Unknown error: {e}'

        logging.exception(err_text)
        tg.send_message(
            text=err_text,
            token=os.environ['TG_BOT_TOKEN'],
            chat_id=os.environ['TG_ADMIN_CHAT_ID']
        )
        return None


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


def process_stats():
    logging.info('Calculating tomorrow stats')
    notifications = get_mchs_notifications(region_ids.keys())
    if not notifications:
        logging.warning('For some reason there are no messages')

    if notifications['code'] != 200:
        err_text = f'MCHS notifications request error: ' \
                   f'code {notifications["code"]}: {notifications["answer"]}'
        logging.error(err_text)
        tg.send_message(
            text=err_text,
            token=os.environ['TG_BOT_TOKEN'],
            chat_id=os.environ['TG_ADMIN_CHAT_ID']
        )
        AttributeError('Will retry on the next tick...')

    messages = map(Message.from_dict, notifications['list'])

    # фильтруем сообщения по дате (нас интересуют только вчерашние)
    now = dt.datetime.now(tz=locale)
    yesterday_00 = dt.datetime(now.year, now.month, now.day, tzinfo=locale) - dt.timedelta(days=1)
    yesterday_24 = yesterday_00 + dt.timedelta(days=1)
    messages = filter(lambda m: yesterday_00 <= m.date < yesterday_24, messages)

    # отфильтровываем только сообщения с тревогами
    messages = list(filter(lambda m: m.notf_type is not None, messages))

    if not messages:
        logging.info('Hooray! No dangerous events yesterday')
        tg.send_message(
            text='К счастью, в этот день ничего не было',
            token=os.environ['TG_BOT_TOKEN'],
            chat_id=os.environ['TG_ADMIN_CHAT_ID']
        )
        return

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
    logging.info('Bot started')
    tg.send_message(
        text='Bot started',
        token=os.environ['TG_BOT_TOKEN'],
        chat_id=os.environ['TG_ADMIN_CHAT_ID']
    )
    scheduler = SafeScheduler(reschedule_on_failure=True, seconds_after_failure=5)
    scheduler.every(10).seconds.do(process_new_mchs_messages)
    scheduler.every().day.at("08:00", locale).do(process_stats)
    scheduler.every().hour.at(":00", locale).do(healthcheck)
    while True:
        scheduler.run_pending()
        time.sleep(1)
