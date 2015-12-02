NICK = '[a-zA-Z0-9]{1,10}'
CHANNEL = '#[a-zA-Z0-9]{1,10}'

DEFN = {
    'oneOf': [
        {'$ref': '#/cmd'},
        {'$ref': '#/errors/error'},
        {'$ref': '#/reply'},
    ],
    'targets': {
        'oneOf': [
            {'$ref': '#/target/user'},
            {'$ref': '#/target/channel'},
        ]
    },
    'target': {
        'user': {
            'type': 'string',
            'pattern': '^' + NICK + '$'
        },
        'channel': {
            'type': 'string',
            'pattern': '^' + CHANNEL + '$'
        }
    },
    'cmd': {
        'type': 'object',
        'properties': {
            'cmd': {'type': 'string'},
            'src': {
                'oneOf': [{'$ref': '#/targets'}]
            }
        },
        'oneOf': [
            {'$ref': '#/cmds/nick'},
            {'$ref': '#/cmds/quit'},
            {'$ref': '#/cmds/squit'},
            {'$ref': '#/cmds/join'},
            {'$ref': '#/cmds/leave'},
            {'$ref': '#/cmds/channels'},
            {'$ref': '#/cmds/users'},
            {'$ref': '#/cmds/msg'},
            {'$ref': '#/cmds/ping'},
            {'$ref': '#/cmds/pong'},
        ],
        'required': ['cmd', 'src']
    },
    'cmds': {
        'nick': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['nick']},
                'update': {'type': 'string'},
            },
            'required': ['update']
        },
        'quit': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['quit']},
                'msg': {'type': 'string'},
            },
            'required': ['msg']
        },
        'squit': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['squit']},
                'msg': {'type': 'string'},
            },
            'required': ['msg']
        },
        'join': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['join']},
                'channels': {
                    'type': 'array',
                    'items': {
                        'oneOf': [{'$ref': '#/target/channel'}]
                    },
                    'minItems': 1,
                    'uniqueItems': True
                },
            },
            'required': ['channels']
        },
        'leave': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['leave']},
                'channels': {
                    'type': 'array',
                    'items': {
                        'oneOf': [{'$ref': '#/target/channel'}]
                    },
                    'minItems': 1,
                    'uniqueItems': True
                },
                'msg': {'type': 'string'}
            },
            'required': ['channels', 'msg']
        },
        'channels': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['channels']},
            }
        },
        'users': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['users']},
                'channels': {
                    'type': 'array',
                    'items': {
                        'oneOf': [{'$ref': '#/target/channel'}],
                    },
                    'minItems': 1,
                    'uniqueItems': True
                },
            }
        },
        'msg': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['msg']},
                'targets': {
                    'type': 'array',
                    'items': {
                        'oneOf': [{'$ref': '#/targets'}],
                    },
                    'minItems': 1,
                    'uniqueItems': True
                },
                'msg': {'type': 'string'}
            },
            'required': ['targets', 'msg']
        },
        'ping': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['ping']},
                'msg': {'type': 'string'}
            },
            'required': ['msg']
        },
        'pong': {
            'type': 'object',
            'properties': {
                'cmd': {'enum': ['pong']},
                'msg': {'type': 'string'}
            },
            'required': ['msg']
        }
    },
    'errors': {
        'error': {
            'type': 'object',
            'properties': {
                'error': {
                    'enum': [
                        'badnick', 'nickinuse', 'schema', 'nochannel',
                        'badchannel', 'nonmember', 'member', 'nonexist'
                    ]
                },
                'msg': {
                    'type': 'string'
                }
            },
            'required': ['error', 'msg']
        }
    },
    'reply': {
        'type': 'object',
        'properties': {
            'reply': {
                'type': 'string',
            }
        },
        'oneOf': [
            {'$ref': '#/replies/channels'},
            {'$ref': '#/replies/names'},
        ],
        'required': ['reply']
    },
    'replies': {
        'names': {
            'type': 'object',
            'properties': {
                'reply': {'enum': ['names']},
                'channel': {
                    'type': 'string',
                    'oneOf': [{'$ref': '#/target/channel'}]
                },
                'names': {
                    'type': 'array',
                    'items': {
                        'oneOf': [{'$ref': '#/target/user'}]
                    },
                    'minItems': 0,
                    'uniqueItems': True
                },
            },
            'required': ['reply', 'names']
        },
        'channels': {
            'type': 'object',
            'properties': {
                'reply': {'enum': ['channels']},
                'channels': {
                    'type': 'array',
                    'items': {
                        'oneOf': [{'$ref': '#/target/channel'}]
                    },
                    'minItems': 0,
                    'uniqueItems': True
                },
            },
            'required': ['reply', 'channels']
        }
    }
}
