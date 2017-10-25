import unittest
from unittest.mock import Mock

from heroku2elk.config import MainConfig
from heroku2elk.lib.syslog import Splitter


svc_start = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State " \
            b"changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00"\
            b":00 host app web.3 - Starting process with command `bundle exec"\
            b" rackup config.ru -p 24405`"
svc_start_lines = [
    "<40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed "
    "from starting to up",
    "<40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process "
    "with command `bundle exec rackup config.ru -p 24405`"]


class SyslogSplitterTest(unittest.TestCase):
    def setUp(self):
        self.statsdClient = Mock()

    def test_splitHerokuSample(self):
        stream = (svc_start)
        logs = Splitter(MainConfig()).split(stream)
        self.assertEqual(logs, svc_start_lines)

    def test_splitHerokuSampleWithoutCarriageReturn(self):
        stream = (b"82 <40>1 2012-11-30T06:45:29+00:00 host app web.3 - State"
                  b" changed from starting to up118 <40>1 2012-11-30T06:45:"
                  b"26+00:00 host app web.3 - Starting process with command "
                  b"`bundle exec rackup config.ru -p 24405`")
        logs = Splitter(MainConfig()).split(stream)
        self.assertEqual(logs, [
            "<40>1 2012-11-30T06:45:29+00:00 host app web.3 - State changed "
            "from starting to up",
            "<40>1 2012-11-30T06:45:26+00:00 host app web"
            ".3 - Starting process with command `bundle exec rackup config.r"
            "u -p 24405`"
        ])

    def test_splitFakeLog(self):
        stream = (b"73 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lore"
                  b"m ipsum dolor sit.\n103 <40>1 2017-06-21T16:37:25+00:00 h"
                  b"ost ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur"
                  b" adipiscing.\n127 <40>1 2017-06-21T16:37:25+00:00 host pon"
                  b"zi web.1 - Lorem ipsum dolor sit amet, consecteteur adipis"
                  b"cing elit b'odio' b'ut' b'a'.\n63 <40>1 2017-06-21T16:37:2"
                  b"5+00:00 host ponzi web.1 - Lorem ipsum.")
        logs = Splitter(MainConfig()).split(stream)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum "
            "dolor sit.",
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lor"
            "em ipsum dolor sit amet, consecteteur adipiscing.",
            "<40>1 2017-06-2"
            "1T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, c"
            "onsecteteur adipiscing elit b'odio' b'ut' b'a'.",
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum."
        ])

    def test_splitFakeLog2(self):
        stream = (b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lor"
                  b"em ipsum dolor sit amet, consecteteur adipiscing elit b'qu"
                  b"is' b'ad'.\n64 <40>1 2017-06-21T17:02:55+00:00 host ponzi "
                  b"web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00 "
                  b"host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteu"
                  b"r adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'"
                  b"taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02"
                  b":55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, c"
                  b"onsecteteur adipiscing.")
        logs = Splitter(MainConfig()).split(stream)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum do"
            "lor sit amet, consecteteur adipiscing elit b'quis' b'ad'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum do"
            "lor sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'"
            "a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum do"
            "lor sit amet, consecteteur adipiscing."
        ])

    def test_splitAndTruncate(self):
        stream = (b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lor"
                  b"em ipsum dolor sit amet, consecteteur adipiscing elit b'qu"
                  b"is' b'ad'.\n64 <40>1 2017-06-21T17:02:55+00:00 host ponzi "
                  b"web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00 "
                  b"host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteu"
                  b"r adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'"
                  b"taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02"
                  b":55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, c"
                  b"onsecteteur adipiscing.")
        conf = MainConfig()
        conf.truncate_max_msg_length = 100
        logs = Splitter(conf).split(stream)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            " amet, consecteteur adipiscing elit b'quis' b'ad'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "rem ipsum dolor sit amet, consecteteur adipiscing."
        ])

    def test_noTruncateStacktrance(self):
        stream = (b"140 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - {'s"
                  b"tack':'toto'} Lorem ipsum dolor sit amet, consecteteur adi"
                  b"piscing elit b'quis' b'ad'.\n64 <40>1 2017-06-21T17:02:55+"
                  b"00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-06-2"
                  b"1T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit "
                  b"amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a"
                  b"' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <40>1"
                  b" 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum "
                  b"dolor sit amet, consecteteur adipiscing.")
        conf = MainConfig()
        conf.truncate_max_msg_length = 100
        logs = Splitter(conf).split(stream)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - {'stack':'toto"
            "'} Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'qui"
            "s' b'ad'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "rem ipsum dolor sit amet, consecteteur adipiscing."
        ])

    def test_removeToken(self):
        stream = (b"140 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lor"
                  b"em ipsum dolor sit amet, consecteteur adipiscing elit b'qu"
                  b"is' b'ad'.{\"token\":\"sdfs\"} \n64 <40>1 2017-06-21T17:02"
                  b":55+00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-"
                  b"06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor "
                  b"sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et'"
                  b" b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <"
                  b"40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ip"
                  b"sum dolor sit amet, consecteteur adipiscing.")
        conf = MainConfig()
        conf.truncate_max_msg_length = 100
        logs = Splitter(conf).split(stream)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "elit b'quis' b'ad'.{\"token\":\"__TOKEN_REPLACED__\"} ",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ "
            "rem ipsum dolor sit amet, consecteteur adipiscing."
        ])

    def test_removeToken2(self):
        stream = (b"145 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - "
                  b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit"
                  b" b'quis' b'ad'.{\"toto_token\":\"sdfs\"} \n64 <40>1 2017-"
                  b"06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.\n179"
                  b" <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem"
                  b" ipsum dolor sit amet, consecteteur adipiscing elit b'arc"
                  b"u' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilis"
                  b"i' b'a'.\n104 <40>1 2017-06-21T17:02:55+00:00 host ponzi w"
                  b"eb.1 - Lorem ipsum dolor sit amet, consecteteur adipiscin"
                  b"g.")
        conf = MainConfig()
        conf.truncate_max_msg_length = 100
        logs = Splitter(conf).split(stream)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__"
            " b'quis' b'ad'.{\"toto_token\":\"__TOKEN_REPLACED__\"} ",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__"
            " b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__"
            " rem ipsum dolor sit amet, consecteteur adipiscing."
        ])


if __name__ == '__main__':
    unittest.main()
