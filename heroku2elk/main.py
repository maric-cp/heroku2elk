"""Main script to start tornado web server.
"""
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from heroku2elk.config import MainConfig, configure_logger
from heroku2elk.lib.amqp import AMQPConnectionSingleton
from heroku2elk.lib.debug import start_debug


def make_app(conf, ioloop=None):
    """
    Create the tornado application
    """

    handlers = []
    for api, vers in conf.handlers.items():
        for ver, hdls in vers.items():
            for hdl in hdls:
                handlers.append((hdl.get_url(api, ver), hdl,
                                 dict(api=api, ver=ver, conf=conf,
                                      )))
    app = tornado.web.Application(handlers)
    app.conf = conf
    app.log = configure_logger()
    return app


def close_app(app):
    AMQPConnectionSingleton().close_channel()
    app.conf.close()


def run(conf):

    app = make_app(conf)
    logger = app.log

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
