import datetime as dt
import json
import os
from dataclasses import dataclass


region_ids = json.loads(os.environ['GOCHS_REGIONS'])


@dataclass
class NotificationType:
    general: str
    name: str = ''


@dataclass
class Message:
    text: str
    date_str: str
    region: 'Region' = None

    @classmethod
    def from_dict(cls, data):
        return cls(
            text=data.get('text'),
            date_str=data.get('date'),
            region=Region(data['region'])
        )

    @property
    def date(self):
        return dt.datetime.strptime(self.date_str + '00', '%Y-%m-%d %H:%M:%S%z')

    @property
    def notf_type(self) -> NotificationType:
        if 'отбой' in self.text.lower():
            return NotificationType('cancel', 'cancel')
        if 'обстрел' in self.text.lower():
            return NotificationType('alarm', 'shelling')
        if 'ракетная опасность' in self.text.lower():
            return NotificationType('alarm', 'missile')
        if 'авиационная опасность' in self.text.lower() or 'опасность атаки бпла' in self.text.lower():
            return NotificationType('alarm', 'avia')
        return NotificationType('other', 'other')


@dataclass
class Region:
    guid: str

    @property
    def name(self):
        return region_ids.get(self.guid)
