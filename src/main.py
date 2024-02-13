import datetime as dt
import itertools
import json
import logging
import time
import os

from dotenv import load_dotenv
import requests

load_dotenv()
from dto import Region
import tg


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s")
region_ids = json.loads(os.environ['GOCHS_REGIONS'])


if __name__ == '__main__':
    last_date = dt.datetime.now(tz=dt.timezone(dt.timedelta(hours=3)))  # - dt.timedelta(hours=24)
    logging.info('Bot started')
    tg.send_message(
        text='Bot started',
        token=os.environ['TG_BOT_TOKEN'],
        chat_id=os.environ['TG_ADMIN_CHAT_ID']
    )

    while True:
        logging.info('Checking new messages')
        try:
            resp = requests.get(
                url='https://push.mchs.ru/new-history',
                params={
                    'region': [','.join(region_ids.keys())],
                    'type': 'all'
                },
                headers={
                    'Accept-Encoding': 'gzip',
                    'Content-MD5': 'fb62712c9475d5f8fac8418dcb6762a2',
                    'Content-Type': 'application/json; charset=utf-8',
                    'Host': 'push.mchs.ru',
                    'User-Agent': 'Dart/3.2 (dart:io)'
                }
            )
            notifications = resp.json()
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
            time.sleep(10)
            continue

        if notifications['code'] != 200:
            err_text = f'MCHS notifications request error: ' \
                       f'code {notifications["code"]}: {notifications["answer"]}'
            logging.error(err_text)
            tg.send_message(
                text=err_text,
                token=os.environ['TG_BOT_TOKEN'],
                chat_id=os.environ['TG_ADMIN_CHAT_ID']
            )
            time.sleep(10)
            continue

        regions = []
        for raw_region in notifications['list']:
            regions.append(Region.from_dict(raw_region))

        messages = itertools.chain.from_iterable([e.messages for e in regions])
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

        logging.info('Waiting 10 sec for next message check...')
        time.sleep(10)
