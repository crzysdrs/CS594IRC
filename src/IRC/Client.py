#!/usr/bin/env python
import socket
import sys
import argparse
import re
import select
import json
from  more_itertools import unique_everseen
from collections import deque
import IRC
import tty
import curses
from collections import defaultdict
import logging
from IRC.Handler import SocketBuffer
import signal
from IRC.GUI import ClientGUI, ClientConsole

def unique(items):
    return list(unique_everseen(items))

class CommandParseError(Exception):
    def __init__(self, msg):
        self.__msg = msg

    def __str__(self):
        return self.__msg

class CommandParseUnimplemented(CommandParseError):
    def __init__(self, msg):
        self.__msg = msg
    def __str__(self):
        return "Unimplemented: %s" % (self.__msg)

class CmdArg:
    def __init__(self, regex, error):
        self.__regex = regex
        self.__error = error

    def pattern(self):
        return self.__regex

    def error(self):
        return self.__error

class CommandResult:
    def __init__(self, fn, name, args):
        self.__fn = fn
        self.__name = name
        self.__args = args

    def execute(self, client):
        self.__fn(client, *self.__args)

class Command:
    def __init__(self, name, cmd, args=None, extra=False):
        self.__name = name
        if args:
            self.__args = args
        else:
            self.__args = []
        self.__cmd = cmd
        self.__extra = extra
    def name(self):
        return self.__name

    def __pattern(self):
        p = "^/" + self.__name
        for a in self.__args:
            p += '\s+(\S+)'
        p += '\s*'
        if self.__extra:
            p += '(.*)'
        p += '\r?\n?$'
        return p

    def process(self, line):
        m = re.match(self.__pattern(), line)
        if m:
            compare = map (lambda (arg, s): (arg, re.match(arg.pattern(), s), s),  zip(self.__args, m.groups()))
            valid = True
            for (a, v, s) in compare:
                if not v:
                    raise CommandParseError("Invalid Argument: %s, Error: %s" % (s, a.error()))
                    valid = False
            if valid:
                return CommandResult(self.__cmd, self.__name, list(m.groups()))
            else:
                return None
        else:
            raise CommandParseError("%s Expected %d argument(s)" % (line, len(self.__args)))
            return None

class CommandProcessor:
    CHANNEL_LIST = "^({channel},)*{channel}$".format(channel=IRC.Schema.Channel)
    NICK_LIST = "^({nick},)*{nick}$".format(nick=IRC.Schema.Nick)
    def __init__(self):
        self.__cmds = [
            Command('join',
                    self.__joinCmd,
                    args=[
                        CmdArg(self.CHANNEL_LIST, "Invalid Channel List")
                    ]
            ),
            Command('leave',
                    self.__leaveCmd,
                    args=[
                        CmdArg(self.CHANNEL_LIST, "Invalid Channel List")
                    ],
                    extra=True
            ),
            Command('channels',
                    self.__channelsCmd,
            ),
            Command('users',
                    self.__usersCmd,
                    args=[
                        CmdArg(self.CHANNEL_LIST, "Invalid Channel List")
                    ]
            ),
            Command('nick',
                    self.__nickCmd,
                    args=[
                        CmdArg('^{nick}$'.format(nick=IRC.Schema.Nick), "Invalid NickName")
                    ]
            ),
            Command('quit',
                    self.__quitCmd,
                    extra=True
            ),
            Command('msg',
                    self.__msgCmd,
                    args=[
                        CmdArg(self.NICK_LIST, "Invalid Nickname List")
                    ],
                    extra=True
            ),
            Command('chanmsg',
                    self.__chanMsgCmd,
                    extra=True
            ),
            Command('migrate',
                    self.__migrateCmd,
                    args=[
                        CmdArg(IRC.Schema.Channel, "Invalid Channel")
                    ]
            )
        ]

    def __joinCmd(self, client, channels):
        irc_msg = client.getIRCMsg().cmdJoin(unique(channels.split(',')))
        client.sendMsg(client.serverSocket(), irc_msg)

    def __leaveCmd(c, client, channels, msg):
        irc_msg = client.getIRCMsg().cmdLeave(unique(channels.split(',')), msg)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __channelsCmd(c, client):
        irc_msg = client.getIRCMsg().cmdChannels()
        client.sendMsg(client.serverSocket(), irc_msg)

    def __usersCmd(c, client, channels):
        irc_msg = client.getIRCMsg().cmdUsers(unique(channels.split(',')))
        client.sendMsg(client.serverSocket(), irc_msg)

    def __nickCmd(c, client, nick):
        irc_msg = client.getIRCMsg().cmdNick(nick)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __quitCmd(c, client, msg):
        irc_msg = client.getIRCMsg().cmdQuit(msg)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __chanMsgCmd(c, client, msg):
        if client.currentChannel():
            irc_msg = client.getIRCMsg().cmdMsg(msg, [client.currentChannel()])
            client.sendMsg(client.serverSocket(), irc_msg)
        else:
            client.notify("**** You aren't in a channel (/migrate to one) ****")

    def __migrateCmd(c, client, chan):
        if chan == client.currentChannel():
            client.notify("*** Already in {chan} ***".format(chan=chan))
        if chan in client.getChannels():
            client.setChannel(chan)
            client.notify("*** Migrated to {chan} ***".format(chan=chan))
        else:
            client.notify("*** You aren't a member of {chan} ***".format(chan=chan))

    def __msgCmd(c, client, nicks, msg):
        client.sendMsg(client.serverSocket(), client.getIRCMsg().cmdMsg(msg, unique(nicks.split(','))))

    def isCmd(self, line):
        if len(line) > 0:
            return line[0] == '/'
        else:
            return False

    def processCmd(self, line):
        if not self.isCmd(line):
            return CommandResult(self.__chanMsgCmd, 'chanmsg', [line.rstrip()])

        matched_cmd = filter(lambda c: re.match(r'^/{name}\b'.format(name=c.name()), line), self.__cmds)

        if len(matched_cmd) == 0:
            raise CommandParseError("Unknown command %s" % re.match("^(/\S+)", line).group(1))
        elif len(matched_cmd) > 1:
            raise CommandParseError("Multiple commands match.")

        cmd = matched_cmd[0]
        return cmd.process(line)

def clientIgnore(some_func):
    def inner():
        print "Client received an ignored message."
        return
    return inner

class IRCClient(IRC.Handler.IRCHandler):
    def __init__(self, hostname, port, userinput=sys.stdin):
        self.__nick = "NEWUSER"
        super(IRCClient, self).__init__(self.__nick)
        self.__chats = defaultdict(list)
        self.__maxChat = 100
        self.__cmdProc = CommandProcessor()
        self.__server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__server.connect((hostname, port))
        self.__server = SocketBuffer(self.__server)
        self.__currentChannel = None
        self.__channels = defaultdict(list)
        self.__input = userinput
        self.__gui = ClientConsole(self)
        self.__tempNames = []

    def getChats(self):
        return self.__chats

    def updateChat(self, msg, channels=None):
        if channels == None:
            self.__chats[self.currentChannel()].append(msg)
        else:
            for c in channels:
                self.__chats[c].append(msg)

            for c_k in self.__chats.keys():
                self.__chats[c_k] = self.__chats[c_k][-self.__maxChat:]

        if not self.__gui.isGUI():
            print msg
        else:
            self.__gui.updateChat()

    def guirun(self, screen):
        (height, width) = screen.getmaxyx()
        if height < 10 or width < 50:
            logging.warning("Screen size too small")
            self.stop()
        else:
            self.__gui = ClientGUI(self, screen)
            self.__gui.update()
            self.run(shutdown=False)

    def setInput(self, newinput):
        self.__input = newinput

    def getUserInput(self):
        return self.__input.readline()

    def getChannels(self):
        return self.__channels

    def currentChannel(self):
        return  self.__currentChannel

    def setChannel(self, chan):
        self.__currentChannel = chan
        self.__gui.update()

    def getInputSocketList(self):
        return [self.__input, self.__server]

    def getOutputSocketList(self):
        return filter(lambda s : s.readyToSend(), [self.__server])

    def serverSocket(self):
        return self.__server

    def inputCmd(self, line):
        try:
            cmd = self.__cmdProc.processCmd(line)
            if cmd:
                cmd.execute(self)
        except CommandParseError as e:
            self.notify("Error Encountered Parsing Command: %s" % (e))

    def socketInputReady(self, socket):
        if socket == self.__input:
            line = self.__gui.keypress()
            if line and len(line) > 0:
                self.inputCmd(line)
        else:
            self.receiveMsg(socket)

    def socketExceptReady(self, socket):
        pass #does the client care?

    def connectionDrop(self, socket):
        if socket == self.__server:
            self.stop()

    def notify(self, msg):
        self.updateChat(msg)

    def receivedNick(self, socket, src, newnick):
        notify_chans = []
        for (k, v) in self.__channels.iteritems():
            if src in v:
                notify_chans.append(k)
            self.__channels[k] = map(lambda n : newnick if n == src else n, v)

        if self.__nick == src:
            self.__nick = newnick
            self._ircmsg.updateSrc(newnick)
            self.updateChat("*** You ({oldnick}) are now {newnick} ****".format(oldnick=src, newnick=newnick), self.__channels)
        else:
            self.updateChat("*** {oldnick} is now {newnick} ****".format(oldnick=src, newnick=newnick), notify_chans)
        self.__gui.update()

    def receivedQuit(self, socket, src, msg):
        notify_chans = []
        for (k, v) in self.__channels.iteritems():
            if src in v:
                notify_chans.append(k)
                v.remove(src)

        if src == self.__nick:
            self.stop()
        else:
            self.updateChat("*** {src} quit ({msg})".format(src=src, msg=msg), notify_chans)
            self.__gui.updateUsers()

    def receivedSQuit(self, socket, msg):
        pass

    def receivedJoin(self, socket, src, channels):
        for c in channels:
            self.__channels[c].append(src)
            unique(self.__channels[c])

        if src == self.__nick:
            self.notify("*** You joined the channel {channels}".format(channels=channels))
        else:
            self.updateChat("*** {src} joined the channel".format(src=src), channels)
        self.__gui.update()

    def receivedLeave(self, socket, src, channels, msg):
        delchannels = []
        for (k, v) in self.__channels.iteritems():
            if k in channels:
                if src == self.__nick:
                    if self.__currentChannel == k:
                        self.__currentChannel = None
                    delchannels.append(k)
                else:
                    self.__channels[k] = filter(lambda n : n != src, v)

        for d in delchannels:
            del self.__channels[d]

        if src != self.__nick:
            self.updateChat("*** {src} left the channel ({msg})".format(src=src, msg=msg), channels)
        self.__gui.update()

    @clientIgnore
    def receivedChannels(self, socket):
        pass

    @clientIgnore
    def receivedUsers(self, socket, channels):
        pass

    def receivedMsg(self, socket, src, targets, msg):
        channels = filter(lambda c : c in self.__channels, targets)
        if len(channels) > 0:
            self.updateChat("{src}: {msg}".format(src=src, msg=msg), channels)
        elif self.__nick in targets:
            self.notify("*** {src}: {msg}".format(src=src, msg=msg))

    def receivedPing(self, socket, msg):
        self.sendMsg(socket, self._ircmsg.cmdPong(msg))

    @clientIgnore
    def receivedPong(self, socket, msg):
        pass

    def receivedOk(self, socket):
        pass

    def receivedNames(self, socket, channel, names):
        self.__tempNames.extend(names)
        if len(names) == 0:
            self.__channels[channel] = self.__tempNames
            self.__tempNames = []
        self.__gui.update()

    def receivedError(self, socket, error_name, error_msg):
        self.notify("ERROR: {error_t}: {error_m}".format(error_t=error_name, error_m=error_msg))

    def receivedInvalid(self, socket, msg):
        self.notify("BAD SERVER MSG: {msg}".format(msg=msg))

    def receivedSignal(self, sig, frame):
        if sig == signal.SIGINT:
            msg = "Client interrupted with Ctrl-C."
            logging.info(msg)
            self.notify(msg)
            self.stop()

    def sentInvalid(self, socket, msg):
        self.notify("CLIENT ERROR: {msg}".format(msg=msg))

    def shutdown(self):
        self.notify("*** Shutting Down Client ***")
        self.__server.close()

def main():
    parser = argparse.ArgumentParser(description="IRC Client")
    parser.add_argument('--hostname', help="Hostname", default="localhost")
    parser.add_argument('--port', type=int, help="Port", default=50000)
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--log', default=None)

    args = parser.parse_args()

    if args.log != None:
        logging.basicConfig(filename=args.log, filemode='w', level=logging.DEBUG)

    client = IRCClient(args.hostname, args.port)
    if args.gui:
        #keep the client running even if the GUI needs to redraw
        while client.isRunning():
            curses.wrapper(client.guirun)
    else:
        client.run()

if __name__ == "__main__":
    main()
