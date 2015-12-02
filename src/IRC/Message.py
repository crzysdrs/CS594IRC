class IRCMessage(object):
    def __init__(self, src):
        """Initialize sender with source"""
        self.__src = src

    def updateSrc(self, src):
        """ Change source """
        self.__src = src

    def cmdNick(self, nick):
        """ Send a nick command"""
        return {'cmd': 'nick', 'src': self.__src, 'update': nick}

    def cmdQuit(self, msg):
        """ Send a quit command"""
        return {'cmd': 'quit', 'src': self.__src, 'msg': msg}

    def cmdSQuit(self, msg):
        """ Send a Squit command"""
        return {'cmd': 'squit', 'src': self.__src, 'msg': msg}

    def cmdJoin(self, channels):
        """ Send a Join command"""
        return {'cmd': 'join', 'src': self.__src, 'channels': channels}

    def cmdLeave(self, channels, msg):
        """ Send a Leave command"""
        return {
            'cmd': 'leave',
            'src': self.__src,
            'channels': channels,
            'msg': msg
        }

    def cmdChannels(self):
        """ Send a Channels command"""
        return {'cmd': 'channels', 'src': self.__src}

    def cmdUsers(self, channels):
        """ Send a Users command"""
        return {'cmd': 'users', 'src': self.__src, 'channels': channels}

    def cmdMsg(self, msg, targets):
        """ Send a Message command"""
        return {'cmd': 'msg', 'src': self.__src, 'msg': msg, 'targets': targets}

    def cmdPing(self, msg):
        """ Send a Ping command"""
        return {'cmd': 'ping', 'src': self.__src, 'msg': msg}

    def cmdPong(self, msg):
        """ Send a Pong command"""
        return {'cmd': 'pong', 'src': self.__src, 'msg': msg}

    def errorMsg(self, etype, msg):
        """ Send a Error reply"""
        return {'error': etype, 'msg': msg}

    def replyChannels(self, channels):
        """ Send a channels reply"""
        return {'reply': 'channels', 'channels': channels}

    def replyNames(self, channel, names):
        """ Send a names reply"""
        return {'reply': 'names', 'channel': channel, 'names': names}
