import json

from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.concurrent import Future
from tornado.gen import sleep

from heroku2elk.lib import debug, amqp
from heroku2elk import config, main


class TestH2LDebug(AsyncHTTPTestCase):

    def get_app(self):
        conf = config.MainConfig()
        conf.environments = ['integration']
        conf.apis = ['heroku:v1:']
        conf.tornado_debug = True
        conf.logger = main.configure_logger()
        debug.start_debug(conf, 0.01)
        self.app = main.make_app(conf)
        self.app.conf = conf
        return self.app

    def setUp(self):
        super().setUp()

    def tearDown(self):
        main.close_app(self.app)

    def test_H2L_split_error(self):
        payload = (b"50 <40>1 2017-06-14T13:52:29+00:00 host app web.3 "
                   b"- State changed from starting to up\n"
                   b"119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 "
                   b"- Starting process "
                   b"with command `bundle exec rackup config.ru -p 24405`")
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 500)
        self.assertEqual(len(response.body), 0)

    @gen_test
    def test_H2L_heroku_push_to_amqp_success(self):
        self._channel = yield amqp.AMQPConnectionSingleton(
                                    ).get_channel(self.app.conf, self.io_loop)
        self._channel.queue_bind(self.on_bindok, "heroku_integration_queue",
                                 self.app.conf.exchange,
                                 "heroku.v1.integration.toto")
        self._channel.basic_consume(self.on_message,
                                    "heroku_integration_queue")
        self.futureMsg = Future()

        payload = (b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 "
                   b"- Lorem ipsum dolor sit amet, consecteteur adipiscing"
                   b" elit b'quis' b'ad'.\n")
        response = self.http_client.fetch(self.get_url('/heroku/v1/'
                                                       'integration/toto'),
                                          method='POST', body=payload)

        res = yield self.futureMsg
        json_res = json.loads(res.decode('utf-8'))
        self.assertEqual(json_res['app'], 'toto')
        self.assertEqual(json_res['env'], 'integration')
        self.assertEqual(json_res['type'], 'heroku')
        self.assertEqual(json_res['http_content_length'], 122)
        self.assertEqual(json_res['parser_ver'], 'v1')
        self.assertEqual(json_res['message'], '<40>1 2017-06-21T17:02:55+00:00'
                         ' host ponzi web.1 - Lorem ipsum dolor sit amet, '
                         "consecteteur adipiscing elit b'quis' b'ad'.")
        yield sleep(0.5)
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)
        debug.delay = 0.01
        self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        if not self.futureMsg.done():
            self.futureMsg.set_result(body)
        self._channel.basic_ack(basic_deliver.delivery_tag)

    def on_bindok(self, unused_frame):
        pass
