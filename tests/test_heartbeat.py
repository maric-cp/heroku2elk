from tornado.testing import AsyncHTTPTestCase

from heroku2elk.config import MainConfig
import heroku2elk.main as h2l


class TestH2LApp(AsyncHTTPTestCase):
    def get_app(self):
        h2l.configure_logger()
        self.app = h2l.make_app(MainConfig())
        return self.app

    def setUp(self):
        super(TestH2LApp, self).setUp()

    def tearDown(self):
        h2l.close_app(self.app)

    def test_health_check(self):
        response = self.fetch('/api/healthcheck')
        self.assertEqual(response.code, 200)

    def test_heartbeat(self):
        response = self.fetch('/api/heartbeat')
        self.assertEqual(response.code, 200)
