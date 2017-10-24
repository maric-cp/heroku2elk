"""Main script to start tornado web server.
"""
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler

import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from heroku2elk.config import MainConfig
from heroku2elk.lib.amqp import AMQPConnectionSingleton
from heroku2elk.lib.debug import start_debug


def make_app(conf):
    """
    Create the tornado application
    """

    handlers = []
    for api, vers in conf.handlers.items():
        for ver, hdls in vers.items():
            for hdl in hdls:
                handlers.append((hdl.get_url(ver, api), hdl,
                                 dict(api=api, ver=ver, conf=conf)))
    app = tornado.web.Application(handlers)
    app.conf = conf
    app.amqp_conn = AMQPConnectionSingleton.get_channel(conf)
    return app


def close_app(app):
    AMQPConnectionSingleton().close_channel()
    logging.shutdown()


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


def run(conf):

    logger = configure_logger()

    app = make_app(conf)
    if conf.tornado_multiprocessing_activated:
        logger.info("Start H2L in multi-processing mode")
        server = HTTPServer(app)
        server.bind(8080)
        # autodetect number of cores and fork a process for each
        server.start(0)
    else:
        logger.info("Start H2L in single-processing mode")
        app.listen(8080)

    # instantiate an AMQP connection at start to create the queues
    # (needed when logstash starts)
    ins = tornado.ioloop.IOLoop.instance()
    ins.add_future(AMQPConnectionSingleton().get_channel(),
                   lambda x: logger.info("AMQP is connected"))
    conf.logger = logger
    start_debug(conf)
    ins.start()
    close_app(app)


if __name__ == "__main__":
    run(MainConfig())
