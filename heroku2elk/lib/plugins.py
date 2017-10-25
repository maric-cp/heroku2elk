import re


def truncate(payload, conf):
    'truncate big logs except stack traces'
    pattern = re.compile(conf.stack_pattern)
    max_ = conf.truncate_max_msg_length

    if max_ > -1 and len(payload) > max_ and not pattern.search(payload):
        payload = '%s __TRUNCATED__ %s' % (payload[:max_//2],
                                           payload[-max_//2:])

    return payload


def obfuscate_token(payload, conf):
    'replace token by __TOKEN_REPLACED__'
    pattern = re.compile(conf.token_pattern)
    return pattern.sub(lambda x: '{}__TOKEN_REPLACED__{}'.format(x.group(1),
                                                                 x.group(3)),
                       payload)
