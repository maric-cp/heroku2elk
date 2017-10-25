from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.concurrent import Future

import heroku2elk.main as h2l
from heroku2elk.config import MainConfig
from heroku2elk.lib.amqp import AMQPConnectionSingleton


class TestH2LMobile(AsyncHTTPTestCase):

    def get_app(self):
        conf = MainConfig()
        conf.environments = ['integration']
        conf.apis = ['mobile:v1:GenericAPIHandler']
        h2l.configure_logger()
        self.app = h2l.make_app(conf)
        return self.app

    def setUp(self):
        super().setUp()

    def tearDown(self):
        h2l.close_app(self.app)

    @gen_test
    def test_H2L_mobile_push_to_amqp_success(self):
        conn = AMQPConnectionSingleton.AMQPConnection(self.app.conf)
        self._channel = yield conn.create_amqp_client(self.io_loop)
        self._channel.queue_bind(
            self.on_bindok, "mobile_integration_queue",
            self.app.conf.exchange, "mobile.v1.integration.toto")
        self._channel.basic_consume(self.on_message,
                                    "mobile_integration_queue")
        self.futureMsg = Future()

        payload = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - L"\
                  b"orem ipsum dolor sit amet, consecteteur adipiscing elit"\
                  b" b'quis' b'ad'.\n"
        response = self.http_client.fetch(self.get_url(
            '/mobile/v1/integration/toto'), method='POST', body=payload)

        res = yield self.futureMsg
        self.assertEqual(res, b"123 <40>1 2017-06-21T17:02:55+00:00 host "
                         b"ponzi web.1 - Lorem ipsum dolor sit amet, "
                         b"consecteteur adipiscing elit b'quis' b'ad'.\n")
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)
        self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        if not self.futureMsg.done():
            self.futureMsg.set_result(body)
        self._channel.basic_ack(basic_deliver.delivery_tag)

    def on_bindok(self, unused_frame):
        pass
