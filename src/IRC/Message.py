import json

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

    def replyChannels(self, channels):
        return {'reply':'channels', 'channels':channels}

    def replyNames(self, channel, names):
        return {'reply':'names', 'channel':channel, 'names':names}
