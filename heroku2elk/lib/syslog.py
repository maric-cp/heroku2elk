import re
from heroku2elk.config import TruncateConfig

patternStackTrace = re.compile(TruncateConfig.stack_pattern)
patternToken = re.compile(TruncateConfig.token_pattern)


class Splitter:
    def __init__(self, config, statsd):
        self.config = config
        self.statsdClient = statsd

    def split(self, bytes):
        """ Split an heroku syslog encoded payload using the octet counting
        method as described here :
        https://tools.ietf.org/html/rfc6587#section-3.4.1
        """

        lines = []
        while len(bytes) > 0:
            # find first space character
            i = 0
            while bytes[i] != 32:  # 32 is white space in unicode
                i += 1
            msg_len = int(bytes[0:i].decode('utf-8'))
            msg = bytes[i + 1:i + msg_len + 1]

            # remove \n at the end of the line if found
            eol = msg[len(msg)-1]
            if eol == 10 or eol == 13:  # \n or \r in unicode
                msg = msg[:-1]

            decoded_msg = msg.decode('utf-8', 'replace')
            if self.config.truncate_activated:
                # replace token by __TOKEN_REPLACED__
                decoded_msg = patternToken.sub(lambda x:
                                               '{}__TOKEN_REPLACED__{}'
                                               .format(x.group(1), x.group(3)),
                                               decoded_msg)

                max_ = self.config.truncate_max_msg_length
                # TRUNCATE Big logs except stack traces
                if not patternStackTrace.search(decoded_msg
                                                ) and len(decoded_msg) > max_:
                    decoded_msg = '%s __TRUNCATED__ %s' % (
                        decoded_msg[:max_//2], decoded_msg[-max_//2:])
                    self.statsdClient.incr('truncate', count=1)

            lines.append(decoded_msg)

            bytes = bytes[i + 1 + msg_len:]
        return lines
