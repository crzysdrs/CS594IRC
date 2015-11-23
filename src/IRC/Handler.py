import jsonschema
from abc import ABCMeta, abstractmethod
import signal
import select
from Message import IRCMessage
import Exceptions
import Schema
import IRC
import json

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
                except Exceptions.InvalidIRCMessage as e:
                    self.sentInvalid(e.socket, e.msg)
        finally:
            self.shutdown()
            
    def sendMsg(self, socket, msg):
        try:
            jsonschema.validate(msg, IRC.Schema.Defn)
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
            jsonschema.validate(jmsg, IRC.Schema.Defn)
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
    
