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
        'required':['cmd', 'src']
    },
    'cmds' : {
        'nick': {
            'type': 'object',
            'properties': {
                'cmd' : {'enum': ['nick']},
                'update': {'type' : 'string'},
            },
            'required':['update']
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
    def validate_irc_msg(*args, **kwargs):
        msg = f(*args, **kwargs)
        validate(msg, IRCSchema)
        jmsg = json.dumps(msg, separators=(',', ':'))
        if len(jmsg) > 1022:
            raise "JSON IRC Message Too Long"
        return jmsg + "\r\n"
    
    return validate_irc_msg
    
class IRC:
    def __init__(self, src):
        self.__src = src

    def updateSrc(self, src):
        self.__src = src
        
    @ValidateIRC
    def cmdNick(self, nick):
        return {'cmd':'nick', 'src':self.__src, 'update':nick}
    
    @ValidateIRC
    def cmdQuit(self, msg):
        return {'cmd':'quit', 'src':self.__src, 'msg':msg}

    @ValidateIRC
    def cmdSQuit(self, msg):
        return {'cmd':'squit', 'src':self.__src, 'msg':msg}

    @ValidateIRC
    def cmdJoin(self, channels):
        return {'cmd':'join', 'src':self.__src, 'channels':channels}

    @ValidateIRC
    def cmdLeave(self, channels, msg):
        return {'cmd':'leave', 'src':self.__src, 'channels':channels, 'msg':msg}

    @ValidateIRC
    def cmdChannels(self):
        return {'cmd':'channels', 'src':self.__src}

    @ValidateIRC
    def cmdUsers(self, channels):
        return {'cmd':'users', 'src':self.__src, 'channels':channels}

    @ValidateIRC
    def cmdMsg(self, msg, targets):
        return {'cmd':'msg', 'src':self.__src, 'msg':msg, 'targets':targets}

    @ValidateIRC
    def cmdPing(self, msg):
        return {'cmd':'ping', 'src':self.__src, 'msg':msg}

    @ValidateIRC
    def cmdPong(self, msg):
        return {'cmd':'pong', 'src':self.__src, 'msg':msg}

    @ValidateIRC
    def errorMsg(self, type, msg):
        return {'error':type, 'msg':msg}

    @ValidateIRC
    def replyOk(self):
        return {'reply':'ok'}

    @ValidateIRC
    def replyNames(self, names):
        return {'reply':'names', 'names':names}
    
