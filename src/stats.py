import copy

from dto import Message


bel_region_districts = {
    'Вся область': {
        'keys': ['област', ],
    },
    'Алексеевский ГО': {
        'keys': ['алексеевск', ],
    },
    'Белгородский р-н': {
        'keys': ['белгородский район', 'белгород ', 'белгород.', ],
    },
    # 'Белгород': {
    #     'keys': ['белгород ', 'белгород.', ],
    # },
    'Борисовский р-н': {
        'keys': ['борисов', ],
    },
    'Валуйский ГО': {
        'keys': ['валуйс', 'валуйк'],
    },
    'Вейделевский р-н': {
        'keys': ['вейделев', ],
    },
    'Волоконовский р-н': {
        'keys': ['волоконов', ],
    },
    'Грайворонский ГО': {
        'keys': ['грайворон', ],
    },
    'Губкинский ГО': {
        'keys': ['губкин', ],
    },
    'Ивнянский р-н': {
        'keys': ['ивня', ],
    },
    'Корочанский р-н': {
        'keys': ['короча', ],
    },
    'Красненский р-н': {
        'keys': ['красненский', ],
    },
    'Красногвардейский р-н': {
        'keys': ['красногвард', ],
    },
    'Краснояружский р-н': {
        'keys': ['краснояружс', ],
    },
    'Новооскольский ГО': {
        'keys': ['новооскол', 'новый оскол'],
    },
    'Прохоровский р-н': {
        'keys': ['прохоров', ],
    },
    'Ракитянский р-н': {
        'keys': ['ракит', ],
    },
    'Ровеньский р-н': {
        'keys': ['ровень', ],
    },
    'Старооскольский ГО': {
        'keys': ['старооскол', 'старый оскол'],
    },
    'Чернянский р-н': {
        'keys': ['чернян', ],
    },
    'Шебекинский ГО': {
        'keys': ['шебекин', ],
    },
    'Яковлевский ГО': {
        'keys': ['яковлевск', ],
    },
}


# TODO: переписать. Регион нотификации вкинуть в дто
def update_stats(msg: Message, districts, stats: dict):
    # {'Вся область': {'shelling': [date, ...], 'missile':  [date, ...], 'avia':  [date, ...]}, ...}
    _stats = copy.deepcopy(stats)
    if msg.notf_type.general == 'alarm':  # дополнительно перепроверяем, что это тревога
        msg_dists = []
        for dist_name in districts.keys():
            # пробегаемся по карте районов. Если ключи района есть в сообщении,
            #   то в статистике для данного района добавляем в соответствующий сообщению список тревог дату
            if any(map(lambda key: key in msg.text.lower(), districts[dist_name]['keys'])):
                msg_dists.append(dist_name)

        # для атаки БПЛА почему-то район писать забывают(
        if not msg_dists and msg.notf_type.name == 'avia':
            msg_dists = ['Вся область', ]

        if not msg_dists:
            return

        for dist_name in msg_dists:
            if _stats.get(dist_name) is None:
                _stats[dist_name] = {}
            if _stats[dist_name].get(msg.notf_type.name) is None:
                _stats[dist_name][msg.notf_type.name] = []
            _stats[dist_name][msg.notf_type.name] += [msg.date, ]

    return _stats
