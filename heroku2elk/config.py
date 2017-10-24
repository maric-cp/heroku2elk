from collections import defaultdict
from os import environ
from importlib import import_module
get = environ.get


def _get_mod(name, default_mod):

        if '.' not in name:
            mods, obj = default_mod, name
        else:
            mods, obj = name.rsplit('.', maxsplit=1)
        return getattr(import_module(mods), obj)


def _convert_bare_conf_to_dict(def_, default_mod):

    res = defaultdict(lambda: defaultdict(list))
    for d in def_.split(','):
        name, *rest = d.split(':')
        if rest:
            api, *rest = rest
        else:
            api = '*'
        if rest:
            ver, *rest = rest
        else:
            ver = '*'
        res[api][ver].append(_get_mod(name, default_mod))

    return res


class MainConfig:

    def __init__(self):
        self.tornado_multiprocessing_activated = get(
                     'TORNADO_MULTIPROCESSING_ACTIVATED', 'true') == 'true'
        self.tornado_debug = get('TORNADO_DEBUG', 'false') == 'true'
        self.environments = get('ENVIRONMENTS', 'main').split(',')
        self.apis = get('APIS', 'heroku:v1,api:heartbeat,api:healthcheck'
                        ).split(',')
        self.handlers = _convert_bare_conf_to_dict(
                             get('HANDLERS', 'HerokuHandler:heroku:v1,'
                                 'HealthCheckHandler:api:healthcheck,'
                                 'HealthCheckHandler:api:heartbeat'),
                             'heroku2elk.lib.handlers')
        self.plugins = _convert_bare_conf_to_dict(
                         get('PLUGINS', 'truncate,obfuscate_token:heroku:v1'),
                         'heroku2elk.lib.plugins')

        self.metrics_host = get('METRICS_HOST', 'localhost')
        self.metrics_port = int(get('METRICS_PORT', '8125'))
        self.metrics_prefix = get('METRICS_PREFIX', 'heroku2logstash')

        self.truncate_activated = get('TRUNCATE_ACTIVATION', 'true') == 'true'
        self.truncate_max_msg_length = int(get(
                                        'TRUNCATE_MAX_MSG_LENGTH', '1000'))
        self.stack_pattern = get('TRUNCATE_EXCEPT_STACK_PATTERN', 'stack')
        self.token_pattern = get('REPLACE_TOKEN_PATTERN', '(token":")(.*?)(")')

        self.amqp_activated = get('AMQP_ACTIVATION', 'true') == 'true'
        self.exchange = get('AMQP_MAIN_EXCHANGE', 'logs')
        self.host = get('AMQP_HOST', 'localhost')
        self.port = int(get('AMQP_PORT', 5672))
        self.user = get('AMQP_USER', 'guest')
        self.password = get('AMQP_PASSWORD', 'guest')
