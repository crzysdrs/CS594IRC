from jsonschema import validate
import json

IRCSchema = {
    'oneOf': [
        {'$ref':'#/cmd'},
        {'$ref':'#/errors/error'},
        {'$ref':'#/reply'},
    ],
    'targets' : {
        'oneOf': [
            {'$ref':'#/target/user'},
            {'$ref':'#/target/channel'},
        ]
    },
    'target' : {
        'user' : {
            'type':'string',
            'pattern':'^[a-zA-Z0-9]{1,10}$'
        },
        'channel' : {
            'type':'string',
            'pattern':'^#[a-zA-Z0-9]{1,10}$'
        }
    },
    'cmd': {
        'type':'object',
        'properties': {
            'cmd':{'type':'string'},
            'src':{
                'oneOf':[{'$ref':'#/targets'}]
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
        'required':['msg', 'src']
    },
    'cmds' : {
        'nick': {
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['nick']},
                'msg': {'type' : 'string'},
            },
            'required':['msg']
        },
        'quit': {
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['quit']},
                'msg': {'type' : 'string'},
            },
            'required':['msg']
        },
        'squit':{
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['squit']},
                'msg': {'type' : 'string'},
            },
            'required':['msg']
        },
        'join':{
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['join']},
                'channels': {
                    'type' : 'array',
                    'items' : {
                        'oneOf':[{'$ref' : '#/target/channel'}]
                    },
                    'minItems':1,
                    'uniqueItems': True
                },
            },
            'required':['channels']
        },
        'leave': {
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['leave']},
                'channels': {
                    'type' : 'array',
                    'items' : {
                        'oneOf':[{'$ref' : '#/target/channel'}]
                    },
                    'minItems':1,
                    'uniqueItems': True
                },
            },
            'required':['channels']
        },
        'channels':{            
            'type': 'object',
            'properties':{
                'cmd' : {'enum': ['channels']},
            }
        },
        'users': {
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['users']},
                'channels': {
                    'type' : 'array',
                    'items' : {
                        'oneOf':[{'$ref' : '#/target/channel'}],
                    },
                    'minItems':1,
                    'uniqueItems': True
                },
            }
        },
        'msg':{
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['msg']},
                'targets': {
                    'type' : 'array',
                    'items' : {
                        'oneOf':[{'$ref' : '#/targetname'}],
                    },
                    'minItems':1,
                    'uniqueItems': True
                },
                'msg':{'type': 'string'}
            },
            'required':['targets', 'msg']
        },
        'ping': {
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['ping']},
                'msg':{'type': 'string'}
            },
            'required':['msg']
        },
        'pong':{
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['pong']},
                'msg':{'type': 'string'}
            },
            'required':['msg']
        }
    },
    'errors':{
        'error':{
            'type': 'object',
            'properties': {
                'error' : {
                    'enum' : [
                        'badnick',
                        'nickinuse',
                        'schema',
                        'nochannel',
                        'badchannel',
                        'nonmember',
                        'nonexist'
                    ]
                },
                'msg': {
                    'type':'string'
                }
            },
            'required':['error', 'msg']
        }
    },
    'reply':{
        'type':'object',
        'properties':{
            'reply': {
                'type':'string',
            }
        },
        'oneOf': [            
            {'$ref':'#/replies/ok'},
            {'$ref':'#/replies/names'},
        ],
        'required':['reply']
    },
    'replies':{
        'ok':{
            'type':'object',
            'properties': {
                'reply':{'enum':['ok']}
            },
            'required':['reply']
        },
        'names':{
            'type': 'object',
            'properties': {
                'reply' : {'enum': ['names']},
                'names': {
                    'type' : 'array',
                    'items' : {
                        'oneOf':[{'$ref' : '#/targets'}]
                    },
                    'minItems':0,
                    'uniqueItems': True
                },
            },
            'required':['reply', 'names']
        }
    }
}

def ValidateIRC(f):
    def validate(msg):
        validate(f(msg), IRCSchema)
        jmsg = json.dumps(msg)
        if jmsg.length() > 1022:
            raise "JSON IRC Message Too Long"
        return jmsg + "\r\n"
    
    return validate
    
class IRC:
    def __init__():
        pass

    @ValidateIRC
    def cmdNick(nick):
        return {'cmd':'nick', 'nick':nick}
    
    @ValidateIRC
    def cmdQuit(msg):
        return {'cmd':'quit', 'msg':msg}

    @ValidateIRC
    def cmdSQuit(msg):
        return {'cmd':'squit', 'msg':msg}

    @ValidateIRC
    def cmdJoin(channels):
        return {'cmd':'join', 'channels':channels}

    @ValidateIRC
    def cmdLeave(channels, msg):
        return {'cmd':'leave', 'channels':channels, 'msg':msg}

    @ValidateIRC
    def cmdChannels():
        return {'cmd':'channels'}

    @ValidateIRC
    def cmdUsers(channels):
        return {'cmd':'users', 'channels':channels}

    @ValidateIRC
    def cmdMsg(msg, targets):
        return {'cmd':'msg', 'msg':msg, 'targets':targets}

    @ValidateIRC
    def cmdPing(msg):
        return {'cmd':'ping', 'msg':msg}

    @ValidateIRC
    def cmdPong(msg):
        return {'cmd':'pong', 'msg':msg}

    @ValidateIRC
    def errorMsg(type, msg):
        return {'error':type, 'msg':msg}

    @ValidateIRC
    def replyOk():
        return {'reply':'ok'}

    @ValidateIRC
    def replyNames(names):
        return {'reply':'names', 'names':names}
    
