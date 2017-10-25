import json

from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.concurrent import Future

from heroku2elk import main
from heroku2elk.lib import handlers, plugins
from heroku2elk.config import MainConfig
from heroku2elk.lib.amqp import AMQPConnectionSingleton


class TestH2LHerokuHandlerV2(AsyncHTTPTestCase):

    def get_app(self):
        conf = MainConfig()
        conf.environments = ['integration']
        conf.handlers = dict(heroku=dict(v2=[handlers.HerokuHandler2]))
        conf.plugins = {'*': {'*': (plugins.truncate,
                                    plugins.obfuscate_token)}}
        conf.truncate_max_msg_length = -1
        self.conf = conf
        self.app = main.make_app(conf)
        return self.app

    def setUp(self):
        super().setUp()

    def tearDown(self):
        main.close_app(self.app)

    def test_H2L_split_success(self):
        payload = (b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 "
                   b"- State changed from starting to up\n"
                   b"119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 "
                   b"- Starting process "
                   b"with command `bundle exec rackup config.ru -p 24405`")
        response = self.fetch('/heroku/v2/integration/toto', method='POST',
                              body=payload)
        self.assertEqual(response.code, 200)

    def test_H2L_truncate(self):
        self.app.conf.truncate_max_msg_length = 100
        payload = (b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 "
                   b"- State changed from starting to up\n"
                   b"119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 "
                   b"- Starting process "
                   b"with command `bundle exec rackup config.ru -p 24405`")
        response = self.fetch('/heroku/v2/integration/toto', method='POST',
                              body=payload)
        self.assertEqual(response.code, 200)

    def test_H2L_split_error(self):
        payload = (b"50 <40>1 2017-06-14T13:52:29+00:00 host app web.3 "
                   b"- State changed from starting to up\n"
                   b"119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 "
                   b"- Starting process "
                   b"with command `bundle exec rackup config.ru -p 24405`")
        response = self.fetch('/heroku/v2/integration/toto', method='POST',
                              body=payload)
        self.assertEqual(response.code, 500)
        self.assertEqual(len(response.body), 0)

    @gen_test
    def test_H2L_heroku_push_to_amqp_success(self):
        conn = AMQPConnectionSingleton.AMQPConnection(self.conf)
        self._channel = yield conn.create_amqp_client(self.io_loop)
        self._channel.queue_bind(self.on_bindok, "heroku_integration_queue",
                                 self.conf.exchange,
                                 "heroku.v2.integration.toto")
        self._channel.basic_consume(self.on_message,
                                    "heroku_integration_queue")
        self.futureMsg = Future()

        payload = (b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 "
                   b"- Lorem ipsum dolor sit amet, consecteteur adipiscing"
                   b" elit b'quis' b'ad'.\n")
        response = self.http_client.fetch(self.get_url('/heroku/v2/'
                                                       'integration/toto'),
                                          method='POST', body=payload)

        res = yield self.futureMsg
        json_res = json.loads(res.decode('utf-8'))
        self.assertEqual(json_res['app'], 'toto')
        self.assertEqual(json_res['env'], 'integration')
        self.assertEqual(json_res['type'], 'heroku')
        self.assertEqual(json_res['http_content_length'], 122)
        self.assertEqual(json_res['parser_ver'], 'v2')
        self.assertEqual(json_res['message'], '<40>1 2017-06-21T17:02:55+00:00'
                         ' host ponzi web.1 - Lorem ipsum dolor sit amet, '
                         "consecteteur adipiscing elit b'quis' b'ad'.")
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)
        self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        print(body)
        if not self.futureMsg.done():
            self.futureMsg.set_result(body)
        self._channel.basic_ack(basic_deliver.delivery_tag)

    def on_bindok(self, unused_frame):
        pass
