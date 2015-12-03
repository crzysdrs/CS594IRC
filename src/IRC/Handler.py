"""
The IRC.Handler is a base class for an IRC client or
server. It manages the low level details such as the
socket connections and the data handling with those
sockets. It additionally provides high level knowledge
of incoming/outgoing commands.
"""
import jsonschema
from abc import ABCMeta, abstractmethod
import signal
import select
from IRC.Message import IRCMessage
import IRC.Exceptions
import IRC.Schema
import IRC
import json
import re
import socket as sockmod
import logging

MAX_JSON_MSG = 1024
RWSIZE = select.PIPE_BUF


class SocketBuffer(object):
    """
    The SocketBuffer provides a wrapper around a socket
    so that messages can be buffered before being sent/
    recieved. It also handles cases like socket disconnection.
    """
    def __init__(self, socket, misc=None):
        """ Initialize Socket Buffer"""
        self.__sendBuffer = ""
        self.__recvBuffer = ""
        self.__socket = socket
        self.__disconnect = False
        self.__broken = False
        self.__closed = False
        self.__misc = misc

    def getMisc(self):
        """ Return user provided data for socket"""
        return self.__misc

    def accept(self):
        """ Accept connections on this buffer"""
        return self.__socket.accept()

    def __dead(self):
        """ Socket has been killed in some form"""
        return self.__disconnect or self.__broken or self.__closed

    def readyToSend(self):
        """ Any messages waiting to send"""
        return not self.__dead() and len(self.__sendBuffer) > 0

    def send(self):
        """ Attempt to send the buffer size amount of messages"""
        try:
            if not self.__dead():
                (payload, self.__sendBuffer) = (
                    self.__sendBuffer[:RWSIZE], self.__sendBuffer[RWSIZE:]
                )
                if len(payload):
                    logging.debug("Sending Message: %s" % repr(payload))
                    self.__socket.send(payload)
        except sockmod.error:
            self.__broken = True

    def addMessage(self, msg):
        """ Add a given message to the message queue"""
        if not self.__dead():
            self.__sendBuffer += msg

    def close(self):
        """ Close the socket"""
        if not self.__dead():
            while len(self.__sendBuffer):
                self.send()
            self.__socket.close()

        self.__closed = True

    def hasMsg(self):
        """ Determin if message is in input queue"""
        return self.__getMsg() != None or self.__dead()

    def __getMsg(self):
        """ Find the first message in the input queue"""
        match = re.match(
            "^([^\r\n]{0,1022})\r?\n(.*)$",
            self.__recvBuffer,
            flags=re.DOTALL
        )
        return match

    def getMsg(self):
        """ Return next available message in recv queue (including disconnect) """
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
                ditch = re.match(
                    "^[^\r\n]*?\r?\n(.*)$",
                    self.__recvBuffer,
                    flags=re.DOTALL
                )
                if not ditch:
                    logging.warning(
                        "Truncating buffer: {buf}".format(
                            buf=repr(
                                self.__recvBuffer
                            )
                        )
                    )
                    self.__recvBuffer = self.__recvBuffer[-MAX_JSON_MSG:]
                else:
                    logging.warning(
                        "Dropping partial: {buf}".format(
                            buf=repr(
                                self.__recvBuffer
                            )
                        )
                    )
                    self.__recvBuffer = ditch.group(1)

            if self.__dead():
                return ''
            else:
                return None

    def recv(self):
        """ Recv data from socket when available """
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
            except sockmod.error:
                self.__broken = True
                self.__disconnect = True

    def getSocket(self):
        return self.__socket


class IRCHandler(object):
    """
    The IRCHandler provides an abstraction level layer
    around the low level representation of the sockets
    to provide high level knowledge of incoming/outgoing
    messages

    A handler can use this as a base class and get much
    of the benefits for an easy implementation of client
    or server.
    """
    __metaclass__ = ABCMeta

    def __init__(self, src, host, port):
        """ Initailize all handlers for various message types"""
        cmds = {
            'nick':
            lambda s, msg: self.receivedNick(s, msg['src'], msg['update']),
            'quit':
            lambda s, msg: self.receivedQuit(s, msg['src'], msg['msg']),
            'squit':
            lambda s, msg: self.receivedSQuit(s, msg['msg']),
            'join':
            lambda s, msg: self.receivedJoin(s, msg['src'], msg['channels']),
            'leave':
            lambda s, msg: self.receivedLeave(s, msg['src'], msg['channels'], msg['msg']),
            'channels':
            lambda s, msg: self.receivedChannels(s),
            'users':
            lambda s, msg: self.receivedUsers(s, msg['channels'], msg['client']),
            'ping':
            lambda s, msg: self.receivedPing(s, msg['msg']),
            'pong':
            lambda s, msg: self.receivedPong(s, msg['msg']),
            'msg':
            lambda s, msg: self.receivedMsg(s, msg['src'], msg['targets'], msg['msg']),
        } # yapf: disable
        replies = {
            'channels':
            lambda s, msg: self.receivedChannelsReply(s, msg['channels']),
            'names':
            lambda s, msg: self.receivedNames(s, msg['channel'], msg['names'], msg['client']),
        } # yapf: disable
        errors = {
            'error':
            lambda s, msg: self.receivedError(s, msg['error'], msg['msg'])
        } # yapf: disable
        self._ircmsg = IRCMessage(src)
        self.__running = True
        self.__timeout = 2
        self.__socketBuffers = {}
        self.__host = host
        self.__port = port
        self.__handlers = {'cmd': cmds, 'reply': replies, 'error': errors, }
        signal.signal(signal.SIGINT, self.receivedSignal)

    def getHost(self):
        """ Get the hostname"""
        return self.__host

    def getPort(self):
        """ Get the port information"""
        return self.__port

    @abstractmethod
    def connect(self):
        """ Connect to target"""
        pass

    def setTimeout(self, timeout):
        """ Update the desired timeout"""
        self.__timeout = timeout

    def getIRCMsg(self):
        """ Get the IRC Message Sender"""
        return self._ircmsg

    def isRunning(self):
        """ Is Handler running?"""
        return self.__running

    def run(self, shutdown=True):
        """ Run the handler and process messages"""
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
                    sockets = {maybeSocket(k): k for k in inputs + outputs}
                    #logging.debug(
                    #    "Running Select %d %d Timeout %f" %
                    #    (len(inputs), len(outputs), self.__timeout)
                    #)
                    inputready, outputready, exceptready = select.select(
                        map(lambda x: maybeSocket(x), inputs),
                        map(lambda x: maybeSocket(x), outputs), [],
                        self.__timeout
                    )
                    for s in inputready:
                        self.socketInputReady(sockets[s])
                    for s in outputready:
                        sockets[s].send()
                    for s in exceptready:
                        self.socketExceptReady(sockets[s])
                except IRC.Exceptions.InvalidIRCMessage as e:
                    self.sentInvalid(e.socket, e.msg)

                self.timeStep()
        except select.error as e:
            if e[0] == 4:  #interrupted system call
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
        """ Attempt to send a message on the socket buffer"""
        try:
            jsonschema.validate(msg, IRC.Schema.DEFN)
            jmsg = json.dumps(msg, separators=(',', ':')) + "\r\n"
            if len(jmsg) > 1024:
                raise IRC.Exceptions.InvalidIRCMessage(
                    socket, "JSON IRC Message Too Long"
                )
        except jsonschema.exceptions.ValidationError:
            raise IRC.Exceptions.InvalidIRCMessage(socket, msg)
        else:
            socket.addMessage(jmsg)

    def processIRCMsg(self, socket, msg):
        """ Processes a byte string into a message and calls handler"""
        try:
            jmsg = json.loads(msg)
        except ValueError:
            self.receivedInvalid(socket, msg)
            return

        try:
            jsonschema.validate(jmsg, IRC.Schema.DEFN)
        except jsonschema.exceptions.ValidationError:
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

    def receiveMsg(self, socket):
        """ Receives data from socket and handles all
        available messages"""
        socket.recv()
        processed = False
        while socket.hasMsg():
            msg = socket.getMsg()
            if msg == None:
                return  # Incomplete buffer msg
            elif msg == '':
                self.connectionDrop(socket)
                return
            else:
                self.processIRCMsg(socket, msg)
                processed = True
        return processed

    def stop(self):
        """ Stops the handler"""
        self.__running = False

    def timeStep(self):
        """ Timeout has occured for select """
        pass

    @abstractmethod
    def getInputSocketList(self):
        """Return sockets ready to read"""
        pass

    @abstractmethod
    def getOutputSocketList(self):
        """ Return list of sockets ready to send messages"""
        pass

    @abstractmethod
    def socketInputReady(self, socket):
        """Notify handler of new input"""
        pass

    @abstractmethod
    def socketExceptReady(self, socket):
        """Notify handler of socket exception"""
        pass

    @abstractmethod
    def connectionDrop(self, socket):
        """ Notify handler of dropped connection"""
        pass

    @abstractmethod
    def receivedNick(self, socket, src, newnick):
        """ Notify received Nick """
        pass

    @abstractmethod
    def receivedQuit(self, socket, src, msg):
        """ Notify received Quit """
        pass

    @abstractmethod
    def receivedSQuit(self, socket, msg):
        """ Notify received SQuit """
        pass

    @abstractmethod
    def receivedJoin(self, socket, src, channels):
        """ Notify received Join """
        pass

    @abstractmethod
    def receivedLeave(self, socket, src, channels, msg):
        """ Notify received Leave """
        pass

    @abstractmethod
    def receivedChannels(self, socket):
        """ Notify received Channel """
        pass

    @abstractmethod
    def receivedUsers(self, socket, channels, client_req):
        """ Notify received Users """
        pass

    @abstractmethod
    def receivedMsg(self, socket, src, targets, msg):
        """ Notify received Message"""
        pass

    @abstractmethod
    def receivedPing(self, socket, msg):
        """ Notify received Ping"""
        pass

    @abstractmethod
    def receivedPong(self, socket, msg):
        """ Notify received Pong"""
        pass

    @abstractmethod
    def receivedNames(self, socket, channel, names, client):
        """ Notify received Names"""
        pass

    @abstractmethod
    def receivedChannelsReply(self, socket, channels):
        """ Notify received channels reply"""
        pass

    @abstractmethod
    def receivedError(self, socket, error_name, error_msg):
        """ Notify received errro"""
        pass

    @abstractmethod
    def receivedInvalid(self, socket, msg):
        """ Notify received invalid message"""
        pass

    @abstractmethod
    def receivedSignal(self, sig, frame):
        """ Notify received signal"""
        pass

    @abstractmethod
    def sentInvalid(self, socket, msg):
        """ Notify attempted send of invalid message"""
        pass

    @abstractmethod
    def shutdown(self):
        """ Shutdown handler"""
        pass
