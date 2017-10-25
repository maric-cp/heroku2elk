import logging
import json

from tornado import httpclient, gen
from tornado.web import RequestHandler
from statsd import StatsClient
from pika import BasicProperties

from heroku2elk.lib.syslog import Splitter
from heroku2elk.lib.amqp import AMQPConnectionSingleton


class HealthCheckHandler(RequestHandler):
    """ The Heroku HealthCheck handler class
    """

    def initialize(self, api, ver, conf):
        self.statsd_client = StatsClient(conf.metrics_host, conf.metrics_port,
                                         prefix=conf.metrics_prefix)

    @gen.coroutine
    def get(self):
        """ A simple healthCheck handler
            reply 200 to every GET called
        """
        self.statsd_client.incr('heartbeat', count=1)
        self.set_status(200)

    @classmethod
    def get_url(class_, api, ver):
        return "/%s/%s" % (api, ver)


class GenericAPIHandler(RequestHandler):
    '''Generic Handler with support for API versionned urls'''

    def initialize(self, api, ver, conf):
        """
        handler initialisation
        """
        self.conf = conf
        self.api = api
        self.version = ver
        self.plugins = []
        if api in conf.plugins:
            if '*' in conf.plugins[api]:
                self.plugins.extend(conf.plugins[api]['*'])
            if ver in conf.plugins[api]:
                self.plugins.extend(conf.plugins[api][ver])
        if '*' in conf.plugins:
            if '*' in conf.plugins['*']:
                self.plugins.extend(conf.plugins['*']['*'])
        self.logger = logging.getLogger("tornado.application")
        self.statsd_client = StatsClient(conf.metrics_host, conf.metrics_port,
                                         prefix=conf.metrics_prefix)
        self.http_client = httpclient.AsyncHTTPClient()

    @gen.coroutine
    def post(self):
        """
        HTTP Post handler
        :return: HTTPStatus 200
        """
        self.statsd_client.incr('input.mobile', count=1)
        try:
            payload = self.request.body
            self.process_log(payload)
        except:
            self.set_status(500)
        else:
            self.set_status(200)

    @gen.coroutine
    def process_log(self, payload):

        for trans in self.plugins:
            payload = trans(payload, self.conf)

        return payload

    @classmethod
    def get_url(class_, api, ver):
        return "/%s/%s/.*" % (api, ver)


class GenericAMQPHandler(GenericAPIHandler):
    """ The Mobile HTTP handler class
    """

    @gen.coroutine
    def post(self):
        """
        HTTP Post handler
        :return: HTTPStatus 200
        """
        self.statsd_client.incr('input.mobile', count=1)
        try:
            self.routing_key = self.request.uri.replace('/', '.')[1:]
            super().post()
        except:
            self.set_status(500)
        else:
            self.set_status(200)

    @property
    def routing_key(self):
        return self.__rk

    @routing_key.setter
    def routing_key(self, v):
        self.__rk = v

    @gen.coroutine
    def process_log(self, payload):

        payload = yield super().process_log(payload)
        try:
            channel = yield AMQPConnectionSingleton().get_channel(self.conf)
            self.statsd_client.incr('amqp.output', count=1)

            channel.basic_publish(exchange='logs',
                                  routing_key=self.routing_key,
                                  body=payload,
                                  properties=BasicProperties(
                                      # make message persistent
                                      delivery_mode=1,
                                      ),
                                  mandatory=True
                                  )
            return payload

        except Exception as e:
            self.statsd_client.incr('amqp.output_exception', count=1)
            self.logger.error("Error while pushing message to AMQP, exception:"
                              " {} msg: {}, uri: {}"
                              .format(e, payload, self.request.uri))
            raise


class MultiLineHandler(GenericAMQPHandler):

    @gen.coroutine
    def post(self):
        """
        """
        self.statsd_client.incr('input.multiline', count=1)
        try:

            logs, msg = [], self.request.body.decode().strip()
            while msg:
                size, msg = msg.split(maxsplit=1)
                size = int(size)
                log, msg = msg[:size], msg[size:].strip()
                logs.append(log)

        except Exception as e:
            self.logger.error("Exception occured: %s, while proceeding: %s"
                              % (e, self.request.body))
            self.set_status(500)
            return

        raised = False
        for log in logs:
            try:
                yield self.process_log(log)
            except:
                raised = True

        if raised:
            self.set_status(500)
        else:
            self.set_status(200)


class HerokuHandler(GenericAMQPHandler):
    """ The Heroku HTTP drain handler class
    """

    def initialize(self, api, ver, conf):
        """
        handler initialisation
        """
        super().initialize(api, ver, conf)
        self.splitter = Splitter(conf)

    def set_default_headers(self):
        """
        specify the output headers to have an empty payload, as described here:
        https://devcenter.heroku.com/articles/log-drains#https-drain-caveats
        :return:
        """
        self.set_header('Content-Length', '0')

    @gen.coroutine
    def post(self):
        """
        HTTP Post handler
        1. Split the input payload into an array of bytes
        2. send HTTP requests to logstash for each element of the array
        3. aggregate answers
        :return: HTTPStatus 200
        """
        self.statsd_client.incr('input.heroku', count=1)
        # 1. split
        try:
            self.statsd_client.incr('truncate', count=1)
            logs = self.splitter.split(self.request.body)
        except Exception as e:
            self.logger.error("Exception occured: %s, while proceeding: %s"
                              % (e, self.request.body))
            self.set_status(500)
            return

        # 2. forward
        raised = False
        for log in logs:
            payload = dict()
            path = self.request.uri.split('/')[1:]
            payload['type'] = path[0]
            payload['parser_ver'] = path[1]
            payload['env'] = path[2]
            payload['app'] = path[3]
            payload['message'] = log
            payload['http_content_length'] = len(log)
            self.routing_key = "%(type)s.%(parser_ver)s.%(env)s.%(app)s" \
                               % payload
            payload = json.dumps(payload)
            try:
                yield self.process_log(payload)
            except:
                raised = True

        if raised:
            self.set_status(500)
        else:
            self.set_status(200)


class HerokuHandler2(MultiLineHandler):

    def set_default_headers(self):
        """
        specify the output headers to have an empty payload, as described here:
        https://devcenter.heroku.com/articles/log-drains#https-drain-caveats
        :return:
        """
        self.set_header('Content-Length', '0')

    @gen.coroutine
    def process_log(self, log):

        payload = dict()
        path = self.request.uri.split('/')[1:]
        payload['type'] = path[0]
        payload['parser_ver'] = path[1]
        payload['env'] = path[2]
        payload['app'] = path[3]
        payload['message'] = log
        payload['http_content_length'] = len(log)
        self.routing_key = "%(type)s.%(parser_ver)s.%(env)s.%(app)s" % payload
        payload = json.dumps(payload)

        yield super().process_log(payload)
