from tornado import gen
from tornado.concurrent import Future
import logging
import pika
from tornado.ioloop import IOLoop
from statsd import StatsClient


class AMQPConnectionSingleton:

    __instance = None

    @gen.coroutine
    def get_channel(self, conf, ioloop=None):
        if ioloop is None:
            ioloop = IOLoop.current()
        ins = AMQPConnectionSingleton.__instance
        if ins is None:
            conn = AMQPConnectionSingleton.AMQPConnection(conf)
            ins = yield conn.create_amqp_client(ioloop)
        return ins

    def close_channel(self):
        if AMQPConnectionSingleton.__instance:
            AMQPConnectionSingleton.__instance.close()
        AMQPConnectionSingleton.__instance = None

    class AMQPConnection:
        def __init__(self, conf):
            self._connection = None
            self._channel = None
            self.config = conf
            self.future_channel = Future()
            self.logger = logging.getLogger("tornado.application")
            self.statsdClient = StatsClient(
                self.config.metrics_host,
                self.config.metrics_port,
                prefix=self.config.metrics_prefix)

        @gen.coroutine
        def on_exchange_declareok(self, unused_frame):
            # Declare the queues
            done = set()
            for api, ver, handler in (e.split(':') for e in self.config.apis):
                if api in done:
                    continue
                done.add(api)
                for env in self.config.environments:
                    yield self.declare_queue("%s_%s_queue" % (api, env))
            self.logger.info("Exchange is declared:{} host:{} port:{}"
                             .format(self.config.exchange,
                                     self.config.host, self.config.port))
            self.future_channel.set_result(self._channel)

        def declare_queue(self, name):
            future_result = Future()

            def on_queue_ready(method_frame):
                future_result.set_result(True)

            self.logger.info("Queue declare:{}".format(name))
            self._channel.queue_declare(on_queue_ready, queue=name,
                                        durable=True, exclusive=False,
                                        auto_delete=False)
            return future_result

        def on_connection_close(self, connection):
            self.logger.error("AMQP is disconnected from exchange:{} "
                              "host:{} port:{} connexion:{}".format(
                                  self.config.exchange,
                                  self.config.host, self.config.port,
                                  connection))
            self._connection = None
            self._channel = None

        def on_connection_open(self, connection):
            self._connection = connection
            connection.channel(on_open_callback=self.on_channel_open)

            self.logger.info("AMQP is connected exchange:{} host:{} "
                             "port:{} connexion:{}".format(
                                 self.config.exchange,
                                 self.config.host, self.config.port,
                                 connection))

        def on_channel_open(self, channel):
            self._channel = channel
            channel.exchange_declare(self.on_exchange_declareok,
                                     exchange=self.config.exchange,
                                     exchange_type='topic')
            self.logger.info("channel open {}".format(channel))
            # Enabled delivery confirmations
            self._channel.confirm_delivery(self.on_delivery_confirmation)

        def on_delivery_confirmation(self, method_frame):
            confirmation_type = method_frame.method.NAME.split('.')[1].lower()
            if confirmation_type == 'ack':
                self.statsdClient.incr('amqp.output_delivered', count=1)
            elif confirmation_type == 'nack':
                self.logger.error("delivery_confirmation failed {}".format(
                    method_frame))
                self.statsdClient.incr('amqp.output_failure', count=1)

        def create_amqp_client(self, ioloop):
            self.logger.info("AMQP connecting to: exchange:{} host:{} "
                             "port: {}".format(
                                 self.config.exchange,
                                 self.config.host, self.config.port))
            credentials = pika.PlainCredentials(self.config.user,
                                                self.config.password)

            pika.TornadoConnection(
                pika.ConnectionParameters(host=self.config.host,
                                          port=self.config.port,
                                          credentials=credentials),
                self.on_connection_open,
                on_close_callback=self.on_connection_close,
                custom_ioloop=ioloop)

            return self.future_channel
