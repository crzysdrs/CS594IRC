import jsonschema
import json
from abc import ABCMeta, abstractmethod
import signal
import select

IRCNick = '[a-zA-Z0-9]{1,10}'
IRCChannel = '#[a-zA-Z0-9]{1,10}'

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
            'pattern':'^' + IRCNick + '$'
        },
        'channel' : {
            'type':'string',
            'pattern':'^' + IRCChannel + '$'
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
                'msg': {'type':'string'}
            },
            'required':['channels', 'msg']
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
                        'oneOf':[{'$ref' : '#/targets'}],
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
                        'member',
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
    
class IRCMessage:
    def __init__(self, src):
        self.__src = src

    def updateSrc(self, src):
        self.__src = src
        
    def cmdNick(self, nick):
        return {'cmd':'nick', 'src':self.__src, 'update':nick}
    
    def cmdQuit(self, msg):
        return {'cmd':'quit', 'src':self.__src, 'msg':msg}

    def cmdSQuit(self, msg):
        return {'cmd':'squit', 'src':self.__src, 'msg':msg}

    def cmdJoin(self, channels):
        return {'cmd':'join', 'src':self.__src, 'channels':channels}

    def cmdLeave(self, channels, msg):
        return {'cmd':'leave', 'src':self.__src, 'channels':channels, 'msg':msg}

    def cmdChannels(self):
        return {'cmd':'channels', 'src':self.__src}

    def cmdUsers(self, channels):
        return {'cmd':'users', 'src':self.__src, 'channels':channels}

    def cmdMsg(self, msg, targets):
        return {'cmd':'msg', 'src':self.__src, 'msg':msg, 'targets':targets}

    def cmdPing(self, msg):
        return {'cmd':'ping', 'src':self.__src, 'msg':msg}

    def cmdPong(self, msg):
        return {'cmd':'pong', 'src':self.__src, 'msg':msg}

    def errorMsg(self, type, msg):
        return {'error':type, 'msg':msg}

    def replyOk(self):
        return {'reply':'ok'}

    def replyNames(self, names):
        return {'reply':'names', 'names':names}

class InvalidIRCMessage(Exception):
    def __init__(self, socket, msg):
        self.socket = socket
        self.msg = msg
        
class IRCHandler():
    __metaclass__ = ABCMeta
    def __init__(self, src):
        self._ircmsg = IRCMessage(src)
        self.__running = True
        self.__timeout = 0.1
        self.__handlers = {
            'cmd':{
                'nick'     : lambda s, msg: self.receivedNick(s, msg['update']),
                'quit'     : lambda s, msg: self.receivedQuit(s, msg['msg']),
                'squit'    : lambda s, msg: self.receivedSQuit(s, msg['msg']),
                'join'     : lambda s, msg: self.receivedJoin(s, msg['channels']),
                'leave'    : lambda s, msg: self.receivedLeave(s, msg['channels'], msg['msg']),
                'channels' : lambda s, msg: self.receivedChannels(s),
                'users'    : lambda s, msg: self.receivedUsers(s),
                'ping'     : lambda s, msg: self.receivedPing(s, msg['msg']),
                'pong'     : lambda s, msg: self.receivedPong(s, msg['msg']),
                'msg'      : lambda s, msg: self.receivedMsg(s, msg['src'], msg['targets'], msg['msg']),            
            },
            'reply':{
                'ok'   : lambda s, msg: self.receivedOk(s),
                'names': lambda s, msg: self.receivedNames(s, msg['names'])
            },
            'error':{
                'error' : lambda s, msg: self.receivedError(s, msg['error'], msg['msg'])
            }
        }
        signal.signal(signal.SIGINT, self.receivedSignal)
    
    def run(self):
        try:
            while self.__running:
                try:
                    inputready, outputready, exceptready = select.select(self.getSocketList(),[],[],self.__timeout)
                    for s in inputready:
                        self.socketInputReady(s)                    
                    for s in exceptready:
                        self.socketExceptReady(s)
                except InvalidIRCMessage as e:
                    self.sentInvalid(e.socket, e.msg)
        finally:
            self.shutdown()
            
    def sendMsg(self, socket, msg):
        try:
            jsonschema.validate(msg, IRCSchema)
            jmsg = json.dumps(msg, separators=(',', ':')) + "\r\n"
            if len(jmsg) > 1024:
                raise InvalidIRCMessage(socket, "JSON IRC Message Too Long")            
        except jsonschema.exceptions.ValidationError:            
            raise InvalidIRCMessage(socket, msg)
        else:
            socket.send(jmsg)

    def processIRCMsg(self, socket, msg):
        try:
            jmsg = json.loads(msg)
        except ValueError as e:
            self.receivedInvalid(socket, msg)
            return
        
        try:
            jsonschema.validate(jmsg, IRCSchema)
        except jsonschema.exceptions.ValidationError as e:
            self.receivedInvalid(socket, msg)
            return
        
        if 'cmd' in jmsg:
            self.__handlers['cmd'][jmsg['cmd']](socket, jmsg)
        elif 'reply' in jmsg:
            self.__handlers['reply'][jmsg['reply']](socket, jmsg)
        elif 'error' in jmsg:
            self.__handlers['error']['error'](socket, jmsg)
        else:
            raise BaseException("Unhandled Message Type")
            self.receivedInvalid(socket, msg) #how did we get here?
            
    def receiveMsg(self, socket):
        msg = socket.recv(1024)
        if msg == '':
            self.connectionDrop(socket)
        else:
            self.processIRCMsg(socket, msg)

    def stop(self):
        self.__running = False
        
    @abstractmethod
    def getSocketList(self):
        pass

    @abstractmethod
    def socketInputReady(self, socket):
        pass

    @abstractmethod
    def socketExceptReady(self, socket):
        pass
    
    @abstractmethod
    def connectionDrop(self, socket):
        pass

    @abstractmethod
    def receivedNick(self, socket, newnick):
        pass

    @abstractmethod
    def receivedQuit(self, socket, msg):
        pass

    @abstractmethod
    def receivedSQuit(self, socket, msg):
        pass

    @abstractmethod
    def receivedJoin(self, socket, channels):
        pass

    @abstractmethod
    def receivedLeave(self, socket, channels, msg):
        pass

    @abstractmethod
    def receivedChannels(self, socket):
        pass

    @abstractmethod
    def receivedUsers(self, socket, channels):
        pass

    @abstractmethod
    def receivedMsg(self, socket, src, targets, msg):
        pass

    @abstractmethod
    def receivedPing(self, socket, msg):
        pass

    @abstractmethod
    def receivedPong(self, socket, msg):
        pass

    @abstractmethod
    def receivedOk(self, socket):
        pass

    @abstractmethod
    def receivedNames(self, socket, names):
        pass

    @abstractmethod
    def receivedError(self, socket, error_name, error_msg):
        pass
        
    @abstractmethod    
    def receivedInvalid(self, socket, msg):
        pass

    @abstractmethod
    def receivedSignal(self, signal, frame):
        pass

    @abstractmethod
    def sentInvalid(self, socket, msg):
        pass

    @abstractmethod
    def shutdown(self):
        pass
    
