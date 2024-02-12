import datetime as dt
import json
import os
from dataclasses import dataclass, field
from typing import List


region_ids = json.loads(os.environ['GOCHS_REGIONS'])


@dataclass
class Message:
    text: str
    date_str: str
    region: 'Region' = None

    @classmethod
    def from_dict(cls, data, region: 'Region' = None):
        return cls(
            text=data.get('text'),
            date_str=data.get('date'),
            region=region
        )

    @property
    def date(self):
        return dt.datetime.strptime(self.date_str + '00', '%Y-%m-%d %H:%M:%S%z')


@dataclass
class Region:
    guid: str
    messages: List[Message] = field(default_factory=list)

    @property
    def name(self):
        return region_ids.get(self.guid)

    @classmethod
    def from_dict(cls, data):
        obj = cls(
            guid=data.get('region')
        )
        for raw_message in data.get('messages') or []:
            obj.messages.append(Message.from_dict(raw_message, obj))
        return obj
