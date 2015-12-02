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
import logging

MAX_JSON_MSG = 1024
RWSIZE = select.PIPE_BUF

class SocketBuffer(object):
    def __init__(self, socket, misc=None):
        self.__sendBuffer = ""
        self.__recvBuffer = ""
        self.__socket = socket
        self.__disconnect = False
        self.__broken = False
        self.__closed = False
        self.__misc = misc

    def getMisc(self):
        return self.__misc

    def accept(self):
        return self.__socket.accept()

    def __dead(self):
        return self.__disconnect or self.__broken or self.__closed

    def readyToSend(self):
        return not self.__dead() and len(self.__sendBuffer) > 0

    def send(self):
        try:
            if not self.__dead():
                (payload, self.__sendBuffer) = (self.__sendBuffer[:RWSIZE], self.__sendBuffer[RWSIZE:])
                if len(payload):
                    logging.debug("Sending Message: %s" % repr(payload))
                    self.__socket.send(payload)
        except socket.error as e:
            self.__broken = True

    def addMessage(self, msg):
        if not self.__dead():
            self.__sendBuffer += msg

    def close(self):
        if not self.__dead():
            while len(self.__sendBuffer):
                self.send()
            self.__socket.close()

        self.__closed = True

    def hasMsg(self):
        return self.__getMsg() != None or self.__dead()

    def __getMsg(self):
        match = re.match("^([^\r\n]{0,1022})\r?\n(.*)$", self.__recvBuffer, flags=re.DOTALL)
        return match

    def getMsg(self):
        match = self.__getMsg()
        if match:
            self.__recvBuffer = match.group(2)
            if len(match.group(1)) == 0:
                return self.getMsg()
            else:
                logging.debug("Passing up message: %s" % repr(match.group(1)))
                return match.group(1)
        else:
            if len(self.__recvBuffer) > 0:
                ditch = re.match("^[^\r\n]*?\r?\n(.*)$", self.__recvBuffer, flags=re.DOTALL)
                if not ditch:
                    logging.warning("Truncating buffer: %s" % repr(self.__recvBuffer))
                    self.__recvBuffer = self.__recvBuffer[-MAX_JSON_MSG:]
                else:
                    logging.warning("Dropping partial: %s" % repr(self.__recvBuffer))
                    self.__recvBuffer = ditch.group(1)

            if self.__dead():
                return ''
            else:
                return None

    def recv(self):
        if self.__disconnect or self.__broken:
            return
        else:
            try:
                recvd = self.__socket.recv(RWSIZE)
                logging.debug("Recvd: %s" % repr(recvd))
                if recvd == '':
                    self.__disconnect = True
                else:
                    self.__recvBuffer += recvd
            except socket.error as e:
                self.__broken = True
                self.__disconnect = True

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
                'users'    : lambda s, msg: self.receivedUsers(s, msg['channels']),
                'ping'     : lambda s, msg: self.receivedPing(s, msg['msg']),
                'pong'     : lambda s, msg: self.receivedPong(s, msg['msg']),
                'msg'      : lambda s, msg: self.receivedMsg(s, msg['src'], msg['targets'], msg['msg']),
            },
            'reply':{
                'channels' : lambda s, msg: self.receivedChannelsReply(s, msg['channels']),
                'names'    : lambda s, msg: self.receivedNames(s, msg['channel'], msg['names']),
            },
            'error':{
                'error' : lambda s, msg: self.receivedError(s, msg['error'], msg['msg'])
            }
        }
        signal.signal(signal.SIGINT, self.receivedSignal)

    def setTimeout(self, timeout):
        self.__timeout = timeout

    def getIRCMsg(self):
        return self._ircmsg

    def isRunning(self):
        return self.__running

    def run(self, shutdown=True):
        def maybeSocket(s):
            if type(s) is SocketBuffer:
                return s.getSocket()
            else:
                return s
        logging.info("RUN")
        try:
            while self.__running:
                try:
                    inputs = self.getInputSocketList()
                    outputs = self.getOutputSocketList()
                    sockets = {maybeSocket(k) : k for k in inputs + outputs}
                    logging.debug("Running Select %d %d Timeout %f" % (len(inputs), len(outputs), self.__timeout))
                    inputready, outputready, exceptready = select.select(
                        map(lambda x: maybeSocket(x), inputs),
                        map(lambda x: maybeSocket(x), outputs),
                        [],
                        self.__timeout
                    )
                    for s in inputready:
                        self.socketInputReady(sockets[s])
                    for s in outputready:
                        sockets[s].send()
                    for s in exceptready:
                        self.socketExceptReady(sockets[s])
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
            if shutdown:
                logging.info("Server shutting down")
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
            socket.addMessage(jmsg)

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
        socket.recv()
        processed = False
        while socket.hasMsg():
            msg = socket.getMsg()
            if msg == None:
                return # This means we don't have a complete message in the buffer
            elif msg == '':
                self.connectionDrop(socket)
                return
            else:
                self.processIRCMsg(socket, msg)
                processed = True
        return processed

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
    def receivedNames(self, socket, channel, names):
        pass

    @abstractmethod
    def receivedChannelsReply(self, socket, channels):
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
