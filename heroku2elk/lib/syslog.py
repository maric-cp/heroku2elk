import re


class Splitter:

    def __init__(self, conf):
        self.patternToken = re.compile(conf.token_pattern)
        self.patternStackTrace = re.compile(conf.stack_pattern)
        if conf.truncate_activated:
            self.truncate_to = conf.truncate_max_msg_length
        else:
            self.truncate_to = -1

    def split(self, bytes):
        # '''Split by lines heroku payload and apply filters.'''

        # lines = []

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
            if self.truncate_to > -1:
                # replace token by __TOKEN_REPLACED__
                decoded_msg = self.patternToken.sub(lambda x:
                                                    '{}__TOKEN_REPLACED__{}'
                                                    .format(x.group(1),
                                                            x.group(3)),
                                                    decoded_msg)

                max_ = self.truncate_to
                # TRUNCATE Big logs except stack traces
                if not self.patternStackTrace.search(
                               decoded_msg) and len(decoded_msg) > max_:
                    decoded_msg = '%s __TRUNCATED__ %s' % (
                        decoded_msg[:max_//2], decoded_msg[-max_//2:])

            lines.append(decoded_msg)

            bytes = bytes[i + 1 + msg_len:]
        return lines
