import datetime as dt
import json
import os
from dataclasses import dataclass


region_ids = json.loads(os.environ['GOCHS_REGIONS'])


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
    def notf_type(self):
        if 'обстрел' in self.text.lower():
            return 'shelling'
        if 'ракетная опасность' in self.text.lower():
            return 'missile'
        if 'авиационная опасность' in self.text.lower():
            return 'avia'
        return None


@dataclass
class Region:
    guid: str

    @property
    def name(self):
        return region_ids.get(self.guid)
