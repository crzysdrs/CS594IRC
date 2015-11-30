import jsonschema
from abc import ABCMeta, abstractmethod
import signal
import select
from Message import IRCMessage
import Exceptions
import Schema
import IRC
import json
import re
import socket

MAX_JSON_MSG = 1024
#RWSIZE = self.PIPE_BUF
RWSIZE = 10

class SocketBuffer():
    def __init__(self, socket):
        self.__sendBuffer = ""
        self.__recvBuffer = ""
        self.__socket = socket
        self.__disconnect = False
        self.__broken = False

    def send(self, msg):
        try:
            if not self.__disconnect and not self.__broken:
                self.__sendBuffer += msg
                (payload, self.__sendBuffer) = (self.__sendBuffer[:RWSIZE], self.__sendBuffer[RWSIZE:])
                if len(payload):
                    self.__socket.send(payload)
        except socket.error as e:
            self.__broken = True

    def hasMsg(self):
        if self.__disconnect:
            return True
        elif self.__getMsg():
            return True
        else:
            return False

    def __getMsg(self):
        match = re.match("^.*?([^\r\n]{1,1022})\r?\n(.*)$", self.__recvBuffer, flags=re.MULTILINE)
        return match

    def __findMsg(self):
        match = self.__getMsg()
        if match:
            self.__recvBuffer = match.group(2)
            return match.group(1)
        else:
            self.__recvBuffer = self.__recvBuffer[-MAX_JSON_MSG:]
            if self.__disconnect:
                return ''
            else:
                return None

    def recv(self):
        if self.__disconnect:
            return self.__findMsg()
        else:
            recvd = self.__socket.recv(RWSIZE)
            if recvd == '':
                self.__disconnect = True
            else:
                self.__recvBuffer += recvd
            return self.__findMsg()

    def getSocket(self):
        return self.__socket

class IRCHandler():
    __metaclass__ = ABCMeta
    def __init__(self, src):
        self._ircmsg = IRCMessage(src)
        self.__running = True
        self.__timeout = 2
        self.__socketBuffers = {}
        self.__handlers = {
            'cmd':{
                'nick'     : lambda s, msg: self.receivedNick(s, msg['src'], msg['update']),
                'quit'     : lambda s, msg: self.receivedQuit(s, msg['src'], msg['msg']),
                'squit'    : lambda s, msg: self.receivedSQuit(s, msg['msg']),
                'join'     : lambda s, msg: self.receivedJoin(s, msg['src'], msg['channels']),
                'leave'    : lambda s, msg: self.receivedLeave(s, msg['src'], msg['channels'], msg['msg']),
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

    def prepareSocketBuffers(self, sockets):
        for s in sockets:
            self.__findSocketBuffer(s)

    def __bufferExist(self, s):
        return s in self.__socketBuffers

    def __findSocketBuffer(self, s):
        if not s in self.__socketBuffers:
            self.__socketBuffers[s] = SocketBuffer(s)
        return self.__socketBuffers[s]

    def getIRCMsg(self):
        return self._ircmsg

    def run(self):
        try:
            while self.__running:
                try:
                    inputready, outputready, exceptready = select.select(
                        self.getInputSocketList(),
                        self.getOutputSocketList(),
                        [],
                        self.__timeout
                    )
                    for s in inputready:
                        self.socketInputReady(s)
                    for s in outputready:
                        self.__findSocketBuffer(s).send("")
                    for s in exceptready:
                        self.socketExceptReady(s)
                except Exceptions.InvalidIRCMessage as e:
                    self.sentInvalid(e.socket, e.msg)

                self.timeStep()
        except select.error as e:
            if e[0] == 4: #interrupted system call
                pass
            else:
                raise e
        #except KeyBoardInterrupt:
        #    print "*** Received Keyboard Interrupt ***"
        #    pass
        finally:
            self.shutdown()

    def sendMsg(self, socket, msg):
        try:
            jsonschema.validate(msg, IRC.Schema.Defn)
            jmsg = json.dumps(msg, separators=(',', ':')) + "\r\n"
            if len(jmsg) > 1024:
                raise Exceptions.InvalidIRCMessage(socket, "JSON IRC Message Too Long")
        except jsonschema.exceptions.ValidationError:
            raise Exceptions.InvalidIRCMessage(socket, msg)
        else:
            self.__findSocketBuffer(socket).send(jmsg)

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
        msg = self.__findSocketBuffer(socket).recv()
        print "Recieved msg '{m}'".format(m=msg)
        if msg == None:
            return False # This means we don't have a complete message in the buffer
        elif msg == '':
            self.connectionDrop(socket)
            del self.__socketBuffers[socket]
            return False
        else:
            self.processIRCMsg(socket, msg)
            return True

    def stop(self):
        self.__running = False


    def timeStep(self):
        pass

    @abstractmethod
    def getInputSocketList(self):
        pass

    @abstractmethod
    def getOutputSocketList(self):
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
    def receivedNick(self, socket, src, newnick):
        pass

    @abstractmethod
    def receivedQuit(self, socket, src, msg):
        pass

    @abstractmethod
    def receivedSQuit(self, socket, msg):
        pass

    @abstractmethod
    def receivedJoin(self, socket, src, channels):
        pass

    @abstractmethod
    def receivedLeave(self, socket, src, channels, msg):
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
