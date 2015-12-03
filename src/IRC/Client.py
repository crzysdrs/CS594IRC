#!/usr/bin/env python
"""
An IRC Client Implementation

Provides all the tools to process user input commands
and handle IRC messages using the IRCHandler.
"""
import socket as sockmod
import sys
import argparse
import re
from more_itertools import unique_everseen
import IRC
import curses
from collections import defaultdict
import logging
from IRC.Handler import SocketBuffer
import signal
from IRC.GUI import ClientGUI, ClientConsole


def unique(items):
    """ Return list of unique items in list"""
    u = list(unique_everseen(items))
    u.sort()
    return u


class CommandParseError(Exception):
    """ A Command Parser Error"""
    def __init__(self, msg):
        """ Initialize Exception """
        super(CommandParseError, self).__init__(self)
        self.__msg = msg

    def __str__(self):
        """ String representation of Exception"""
        return self.__msg


class CommandParseUnimplemented(CommandParseError):
    """ An unimplemented Command """
    def __init__(self, msg):
        """ Initialize Exception """
        super(CommandParseUnimplemented, self).__init__(self)
        self.__msg = msg

    def __str__(self):
        """ String representation of Exception"""
        return "Unimplemented: %s" % (self.__msg)


class CmdArg(object):
    """ An argument representation for a given command"""
    def __init__(self, title, regex, error):
        """ Create a Command Argument

        Provide a regex to match argument and an error
        if it fails
        """
        self.__title = title
        self.__regex = regex
        self.__error = error

    def pattern(self):
        """Get the pattern of the command"""
        return self.__regex

    def error(self):
        """Get the error of the command"""
        return self.__error

    def title(self):
        """Get the title of arg"""
        return self.__title

class CommandResult(object):
    """ A Processed set of arguments to a commmand"""
    def __init__(self, fn, name, args):
        """ Encapsulate the result of a command process"""
        self.__fn = fn
        self.__name = name
        self.__args = args

    def execute(self, client):
        """Execute the computed command """
        self.__fn(client, *self.__args)


class Command(object):
    """ An IRC user command

    Can detect, process arguments and return a fully formed
    executable CommandResult
    """
    def __init__(self, name, cmd, args=None, extra=False):
        """ Intiailize a Command """
        self.__name = name
        if args:
            self.__args = args
        else:
            self.__args = []
        self.__cmd = cmd
        self.__extra = extra

    def name(self):
        """ Get Command Name"""
        return self.__name

    def __pattern(self):
        """ Compute pattern to match command with arguments"""
        p = r"^/" + self.__name
        for a in self.__args:
            p += r'\s+(\S+)'
        p += r'\s*'
        if self.__extra:
            p += r'(.*)'
        p += r'\r?\n?$'
        return p

    def getHelp(self):
        helpstr = "/{name}".format(name=self.__name)

        for a in self.__args:
            helpstr += " {title}".format(title=a.title())

        if self.__extra:
            helpstr += " Message"

        return helpstr

    def process(self, line):
        """ Process an input line and return a command result

        Possibly throws exception if no command matches.
        """
        m = re.match(self.__pattern(), line)
        if m:
            compare = map(
                lambda (arg, s): (arg, re.match(arg.pattern(), s), s), zip(
                    self.__args, m.groups()
                )
            )
            for (a, v, s) in compare:
                if not v:
                    raise CommandParseError(
                        "Invalid Argument: %s, Error: %s" % (s, a.error())
                    )
            return CommandResult(self.__cmd, self.__name, list(m.groups()))
        else:
            raise CommandParseError(
                "%s Expected %d argument(s)" % (line, len(self.__args))
            )


class CommandProcessor(object):
    """
    Command Process uses a set of commands and determines which (if
    any) command was requested and executes it.
    """
    CHANNEL_LIST = "^({channel},)*{channel}$".format(channel=IRC.Schema.CHANNEL)
    NICK_LIST = "^({nick},)*{nick}$".format(nick=IRC.Schema.NICK)
    CHANNELNICK_LIST = "^(({nick}|{channel}),)*({nick}|{channel})$".format(
        nick=IRC.Schema.NICK,
        channel=IRC.Schema.CHANNEL
    )

    def __init__(self):
        """ Initialize Set of Commands"""
        self.__cmds = [
            Command(
                'join',
                self.__joinCmd,
                args=[
                    CmdArg("ChannelList", self.CHANNEL_LIST, "Invalid Channel List")
                ]
            ), Command(
                'leave',
                self.__leaveCmd,
                args=[
                    CmdArg("ChannelList", self.CHANNEL_LIST, "Invalid Channel List")
                ],
                extra=True
            ), Command(
                'channels',
                self.__channelsCmd,
            ), Command(
                'users',
                self.__usersCmd,
                args=[
                    CmdArg("ChannelList", self.CHANNEL_LIST, "Invalid Channel List")
                ]
            ), Command(
                'nick',
                self.__nickCmd,
                args=[
                    CmdArg(
                        "NickName",
                        '^{nick}$'.format(nick=IRC.Schema.NICK),
                        "Invalid NickName"
                    )
                ]
            ), Command(
                'quit',
                self.__quitCmd,
                extra=True
            ), Command(
                'msg',
                self.__msgCmd,
                args=[
                    CmdArg(
                        "ChannelOrNickList",
                        self.CHANNELNICK_LIST,
                        "Invalid Channel or Nickname List"
                    )
                ],
                extra=True
            ), Command(
                'chanmsg',
                self.__chanMsgCmd,
                extra=True
            ), Command(
                'migrate',
                self.__migrateCmd,
                args=[
                    CmdArg("Channel", IRC.Schema.CHANNEL, "Invalid Channel")
                ]
            ), Command(
                'help',
                self.__helpCmd
            ),
        ]

    def __helpCmd(self, client):
        """ Notify client of potential commands """
        client.notify("#### HELP COMMANDS ####")
        for c in self.__cmds:
            client.notify(
                "#### {helpmsg}".format(
                    helpmsg=c.getHelp()
                )
            )

    def __joinCmd(self, client, channels):
        """ Notify server of request to join channels """
        irc_msg = client.getIRCMsg().cmdJoin(unique(channels.split(',')))
        client.sendMsg(client.serverSocket(), irc_msg)

    def __leaveCmd(self, client, channels, msg):
        """ Notify server of request to leave channels"""
        irc_msg = client.getIRCMsg().cmdLeave(unique(channels.split(',')), msg)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __channelsCmd(self, client):
        """ Notify server of request to get channels list"""
        irc_msg = client.getIRCMsg().cmdChannels()
        client.sendMsg(client.serverSocket(), irc_msg)

    def __usersCmd(self, client, channels):
        """ Notify server of request to get list of users in channels"""
        irc_msg = client.getIRCMsg().cmdUsers(unique(channels.split(',')), True)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __nickCmd(self, client, nick):
        """ Notify server of change in nickname"""
        irc_msg = client.getIRCMsg().cmdNick(nick)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __quitCmd(self, client, msg):
        """ Notify server of request to quit"""
        irc_msg = client.getIRCMsg().cmdQuit(msg)
        client.sendMsg(client.serverSocket(), irc_msg)

    def __chanMsgCmd(self, client, msg):
        """ Send a message to the current channel"""
        if client.currentChannel():
            irc_msg = client.getIRCMsg().cmdMsg(msg, [client.currentChannel()])
            client.sendMsg(client.serverSocket(), irc_msg)
        else:
            client.notify("**** You aren't in a channel (/migrate to one) ****")

    def __migrateCmd(self, client, chan):
        """ Switch client to new channel """
        if chan == client.currentChannel():
            client.notify("*** Already in {chan} ***".format(chan=chan))
        if chan in client.getJoined():
            client.setChannel(chan)
            if not client.isGUI():
                client.notify("*** Migrated to {chan} ***".format(chan=chan))
        else:
            client.notify(
                "*** You aren't a member of {chan} ***".format(
                    chan=chan
                )
            )

    def __msgCmd(self, client, nicks, msg):
        """ Notify server of message to send privately """
        client.notify("*** {nick}: {msg}".format(nick=client.getNick(), msg=msg))
        client.sendMsg(
            client.serverSocket(), client.getIRCMsg().cmdMsg(
                msg, unique(nicks.split(','))
            )
        )

    def isCmd(self, line):
        """ Determine if input is a command """
        if len(line) > 0:
            return line[0] == '/'
        else:
            return False

    def processCmd(self, line):
        """ Process a given input line into a corresponding command"""
        if not self.isCmd(line):
            return CommandResult(self.__chanMsgCmd, 'chanmsg', [line.rstrip()])

        matched_cmd = filter(lambda c: re.match(r'^/{name}\b'.format(name=c.name()), line), self.__cmds)

        if len(matched_cmd) == 0:
            raise CommandParseError(
                "Unknown command %s" % re.match(
                    "^(/\S+)", line
                ).group(1)
            )
        elif len(matched_cmd) > 1:
            raise CommandParseError("Multiple commands match.")

        cmd = matched_cmd[0]
        return cmd.process(line)


def clientIgnore(some_func):
    """ Log the result of an unhandled command"""
    def inner():
        logging.warning("Client received an ignored message.")
        return

    return inner


class IRCClient(IRC.Handler.IRCHandler):
    """ The IRC Client

    Takes the base IRCHandler and uses it to produce
    a fully formed Client for the IRC protocol.
    """
    def __init__(self, host, port, userinput=sys.stdin):
        """ Initialize Client"""
        self.__nick = "NEWUSER"
        super(IRCClient, self).__init__(self.__nick, host, port)
        self.__chats = defaultdict(list)
        self.__maxChat = 100
        self.__cmdProc = CommandProcessor()
        self.__server = None
        self.__currentChannel = None
        self.__channels = defaultdict(list)
        self.__input = userinput
        self.__gui = ClientConsole(self)
        self.__tempNames = []
        self.__joined = []
        self.__tempChannels = []

    def connect(self):
        """ Attempt to connect to a given server"""
        try:
            logging.info("Attempting to start client.")
            self.__server = sockmod.socket(sockmod.AF_INET, sockmod.SOCK_STREAM)
            self.__server.connect((self.getHost(), self.getPort()))
            self.__server = SocketBuffer(self.__server)
            logging.info("Client Connected to server.")
            return True
        except sockmod.error as e:
            if e.errno == 111:
                logging.critical(
                    "Can't connect to {host}:{port}. Is the server running?".format(
                        host=self.getHost(),
                        port=self.getPort()
                    )
                )
                return False
            else:
                raise e

    def getNick(self):
        """ Get's the client nickname"""
        return self.__nick

    def getJoined(self):
        """ Return list of joined rooms """
        return self.__joined

    def getChats(self):
        """ Return a dictionary of chat messages for rooms"""
        return self.__chats

    def isGUI(self):
        """ Returns if GUI enabled """
        return self.__gui.isGUI()

    def updateChat(self, msg, channels=None):
        """ Update the corresponding chat messages

        Keeps a record of the chat messages in a given channel
        so that the user can read the transcripts
        """
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
        """ Runs the client in a GUI mode """
        (height, width) = screen.getmaxyx()
        if height < 10 or width < 50:
            logging.warning("Screen size too small")
            self.stop()
        else:
            self.__gui = ClientGUI(self, screen)
            self.__gui.update()
            self.run(shutdown=False)

    def setInput(self, newinput):
        """ Sets the input stream for the client"""
        self.__input = newinput

    def getUserInput(self):
        """ Reads from the current input stream a new line"""
        return self.__input.readline()

    def getChannels(self):
        """ Gets the known available channels"""
        return self.__channels

    def currentChannel(self):
        """ Returns users current channel"""
        return self.__currentChannel

    def setChannel(self, chan):
        """ Sets the current channel"""
        self.__currentChannel = chan
        self.__gui.update()

    def getInputSocketList(self):
        """ Returns  the list of input sockets to listen"""
        return [self.__input, self.__server]

    def getOutputSocketList(self):
        """Returns a list of sockets ready to send messages"""
        return filter(lambda s: s.readyToSend(), [self.__server])

    def serverSocket(self):
        """ Returns the current server socket"""
        return self.__server

    def inputCmd(self, line):
        """ Attempts to execute a given user input line"""
        try:
            cmd = self.__cmdProc.processCmd(line)
            if cmd:
                cmd.execute(self)
        except CommandParseError as e:
            self.notify("Error Encountered Parsing Command: %s" % (e))

    def socketInputReady(self, socket):
        """ Determine what to do with a given socket input"""
        if socket == self.__input:
            line = self.__gui.keypress()
            if line and len(line) > 0:
                self.inputCmd(line)
        else:
            self.receiveMsg(socket)

    def socketExceptReady(self, socket):
        """ Notify client of socket exception"""
        pass  #does the client care?

    def connectionDrop(self, socket):
        """ Server Disconnect, shutdown client. """
        if socket == self.__server:
            self.stop()

    def notify(self, msg):
        """ Notify the GUI that there is a new message """
        self.updateChat(msg)

    def receivedNick(self, socket, src, newnick):
        """ Received a nickname.

        If it's for the client, update the nickname.
        Otherwise update the nickname of the specified clients
        """
        notify_chans = []
        for (k, v) in self.__channels.iteritems():
            if src in v:
                notify_chans.append(k)
            self.__channels[k] = map(lambda n: newnick if n == src else n, v)

        if self.__nick == src:
            self.__nick = newnick
            self._ircmsg.updateSrc(newnick)
            self.updateChat(
                "*** You ({oldnick}) are now {newnick} ****".format(
                    oldnick=src,
                    newnick=newnick
                ),
                self.__channels
            )
        else:
            self.updateChat(
                "*** {oldnick} is now {newnick} ****".format(
                    oldnick=src,
                    newnick=newnick
                ),
                notify_chans
            )
        self.__gui.update()

    def receivedQuit(self, socket, src, msg):
        """ Received a quit command

        If it's for the client, shutdown.
        If it's for another client, remove them from chats.
        """
        notify_chans = []
        for (k, v) in self.__channels.iteritems():
            if src in v:
                notify_chans.append(k)
                v.remove(src)

        if src == self.__nick:
            notify_chans.append(None)

        self.updateChat(
            "*** {src} quit ({msg})".format(
                src=src,
                msg=msg
            ),
            notify_chans
        )
        self.__gui.updateUsers()

        if src == self.__nick:
            self.stop()

    def receivedSQuit(self, socket, msg):
        """ Unused server command """
        pass

    def receivedJoin(self, socket, src, channels):
        """ Received join

        If the join is for the user, add them to the channel.
        If it's for another user, store them in the channel.
        """
        for c in channels:
            self.__channels[c].append(src)
            self.__channels[c] = unique(self.__channels[c])

        if src == self.__nick:
            for c in channels:
                self.__joined.append(c)
                self.__joined = unique(self.__joined)

            self.notify(
                "*** You joined the channel(s) {channels}".format(
                    channels=",".join(channels)
                )
            )
        else:
            self.updateChat(
                "*** {src} joined the channel".format(src=src),
                channels
            )
        self.__gui.update()

    def receivedLeave(self, socket, src, channels, msg):
        """ Received Leave

        If it's for the user, remove from specified channels.
        If it's for someone else, remove them from channels.
        """
        delchannels = []
        for j in self.__joined:
            if j in channels:
                if src == self.__nick:
                    if self.__currentChannel == j:
                        self.__currentChannel = None
                    delchannels.append(j)
                else:
                    self.__channels[j] = filter(lambda n: n != src, self.__channels[j])

        if src == self.__nick:
            for d in delchannels:
                self.__joined.remove(d)

        self.updateChat(
            "*** {src} left the channel ({msg})".format(
                src=src,
                msg=msg
            ),
            channels
        )
        self.__gui.update()

    @clientIgnore
    def receivedChannels(self, socket):
        """ Client does not receive channels messages"""
        pass

    @clientIgnore
    def receivedUsers(self, socket, channels, client_req):
        """ Client does not receive users requests"""
        pass

    def receivedMsg(self, socket, src, targets, msg):
        """ Update the chats with the new message depending on target"""
        channels = filter(lambda c: c in self.__joined, targets)
        if self.__nick in targets:
            self.notify("*** {src}: {msg}".format(src=src, msg=msg))
        elif len(channels) > 0:
            self.updateChat("{src}: {msg}".format(src=src, msg=msg), channels)

    def receivedPing(self, socket, msg):
        """ Reply to ping with pong """
        self.sendMsg(socket, self._ircmsg.cmdPong(msg))

    @clientIgnore
    def receivedPong(self, socket, msg):
        """ Client does not recieve pongs"""
        pass

    def receivedNames(self, socket, channel, names, client):
        """ Receive the names list

        If the user is in GUI mode, update the users window.
        Otherwise print out the user information
        """
        if self.__gui.isGUI() and not client:
            self.__tempNames.extend(names)
            if len(names) == 0:
                self.__channels[channel] = self.__tempNames
                self.__tempNames = []
            self.__gui.update()
        elif len(names) > 0:
            self.notify(
                "{chan}: {users}".format(
                    chan=channel,
                    users=" ".join(names)
                )
            )

    def receivedChannelsReply(self, socket, channels):
        """ Receive the channels list

        If the user is in gui mode update the channels window.
        Otherwise print out the channels list.
        """
        if self.__gui.isGUI():
            self.__tempChannels.extend(channels)

            if channels == []:
                new_set = set(self.__tempChannels)
                old_set = set(self.__channels.keys())
                remove = old_set - new_set
                add = new_set - old_set
                for d in remove:
                    del self.__channels[d]
                for d in add:
                    self.__channels[d] = []

                self.__gui.update()
        elif len(channels) > 0:
            self.notify("CHANNELS: {chans}".format(chans=" ".join(channels)))

    def receivedError(self, socket, error_name, error_msg):
        """ Notify user of error"""
        self.notify(
            "ERROR: {error_t}: {error_m}".format(
                error_t=error_name,
                error_m=error_msg
            )
        )

    def receivedInvalid(self, socket, msg):
        """ Notify user of invalid server message"""
        self.notify("BAD SERVER MSG: {msg}".format(msg=msg))

    def receivedSignal(self, sig, frame):
        """ Handle signal gradefully """
        if sig == signal.SIGINT:
            msg = "Client interrupted with Ctrl-C."
            logging.info(msg)
            self.notify(msg)
            self.stop()
        pass

    def sentInvalid(self, socket, msg):
        """ Notify user that invalid message was sent"""
        self.notify("CLIENT ERROR: {msg}".format(msg=msg))

    def shutdown(self):
        """ Shutdown client"""
        self.notify("*** Shutting Down Client ***")
        self.__server.close()


def main():
    """ Main entry point for IRC Client"""
    parser = argparse.ArgumentParser(description="IRC Client")
    parser.add_argument('--hostname', help="Hostname", default="localhost")
    parser.add_argument('--port', type=int, help="Port", default=50000)
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--log', default=None)

    args = parser.parse_args()

    if args.log != None:
        logging.basicConfig(
            filename=args.log,
            filemode='w',
            level=logging.DEBUG
        )

    client = IRCClient(args.hostname, args.port)
    if client.connect():
        if args.gui:
            #keep the client running even if the GUI needs to redraw
            while client.isRunning():
                curses.wrapper(client.guirun)
        else:
            client.run()


if __name__ == "__main__":
    main()
