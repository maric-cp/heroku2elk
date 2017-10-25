from collections import defaultdict
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
from os import environ
from importlib import import_module

get = environ.get


def configure_logger():
    """
    configure logger object with handlers
    """
    app_log = logging.getLogger("tornado.application")
    app_log.setLevel(logging.INFO)
    default_formatter = logging.Formatter('%(asctime)-15s pid:%(process)s'
                                          ' %(message)s')

    # syslog
    handler = SysLogHandler(address='/dev/log')
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        'heroku2logstash: { "loggerName":"%(name)s", '
        '"asciTime":"%(asctime)s", "pathName":"%(pathname)s", '
        '"logRecordCreationTime":"%(created)f", '
        '"functionName":"%(funcName)s", '
        '"levelNo":"%(levelno)s", "lineNo":"%(lineno)d", "time":"%(msecs)d", '
        '"levelName":"%(levelname)s", "pid": "%(process)s",'
        '"message":"%(message)s"}')
    handler.formatter = formatter
    app_log.addHandler(handler)

    # console log
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.formatter = default_formatter
    app_log.addHandler(ch)

    # File log (max 1 GB: 1 * 2**30 B)
    file_handler = RotatingFileHandler('heroku2logstash.log',
                                       maxBytes=2**30, backupCount=10)
    file_handler.setLevel(logging.INFO)
    file_handler.formatter = default_formatter
    app_log.addHandler(file_handler)
    logging.captureWarnings(True)
    return app_log


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

    def close(self):
        logging.shutdown()
