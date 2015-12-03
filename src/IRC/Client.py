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
                    CmdArg("ChannelList", self.CHANNEL_LIST,
                           "Invalid Channel List")
                ]
            ),
            Command(
                'leave',
                self.__leaveCmd,
                args=[
                    CmdArg("ChannelList", self.CHANNEL_LIST,
                           "Invalid Channel List")
                ],
                extra=True
            ),
            Command(
                'channels',
                self.__channelsCmd,
            ),
            Command(
                'users',
                self.__usersCmd,
                args=[
                    CmdArg("ChannelList", self.CHANNEL_LIST,
                           "Invalid Channel List")
                ]
            ),
            Command(
                'nick',
                self.__nickCmd,
                args=[
                    CmdArg(
                        "NickName",
                        '^{nick}$'.format(nick=IRC.Schema.NICK),
                        "Invalid NickName"
                    )
                ]
            ),
            Command(
                'quit',
                self.__quitCmd,
                extra=True
            ),
            Command(
                'msg',
                self.__msgCmd,
                args=[
                    CmdArg(
                        "ChannelOrNickList", self.CHANNELNICK_LIST,
                        "Invalid Channel or Nickname List"
                    )
                ],
                extra=True
            ),
            Command(
                'chanmsg',
                self.__chanMsgCmd,
                extra=True
            ),
            Command(
                'migrate',
                self.__migrateCmd,
                args=[
                    CmdArg("Channel", IRC.Schema.CHANNEL, "Invalid Channel")
                ]
            ),
            Command(
                'help', self.__helpCmd
            ),
        ]

    def __helpCmd(self, client):
        """ Notify client of potential commands """
        client.notify("#### HELP COMMANDS ####")
        for c in self.__cmds:
            client.notify("#### {helpmsg}".format(helpmsg=c.getHelp()))

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
        if client.serverSocket().isDead():
            client.stop()

    def __chanMsgCmd(self, client, msg):
        """ Send a message to the current channel"""
        if client.currentChannel():
            irc_msg = client.getIRCMsg().cmdMsg(
                msg, [client.currentChannel().getName()])
            client.sendMsg(client.serverSocket(), irc_msg)
        else:
            client.notify("**** You aren't in a channel (/migrate to one) ****")

    def __migrateCmd(self, client, chan_name):
        """ Switch client to new channel """
        chan = client.findChannel(chan_name)
        if chan == None:
            client.notify("**** Unknown channel {chan} ****".format(chan=
                                                                    chan_name))
        elif chan == client.currentChannel():
            client.notify("*** Already in {chan} ***".format(chan=chan.getName(
            )))
        elif chan in client.getJoined():
            client.setChannel(chan)
            if not client.isGUI():
                client.notify("*** Migrated to {chan} ***".format(
                    chan=chan.getName()))
        else:
            client.notify(
                "*** You aren't a member of {chan}) ***".format(
                    chan=chan.getName()
                )
            )

    def __msgCmd(self, client, nicks, msg):
        """ Notify server of message to send privately """
        client.notify("*** {nick}: {msg}".format(nick=client.getNick(),
                                                 msg=msg))
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


class ClientUser(object):
    """ A simple Reference to a Name for storing in Channels """

    def __init__(self, name):
        """ Initialize Name """
        self.__name = name

    def updateName(self, name):
        """ Update on nick change """
        self.__name = name

    def getName(self):
        """ Return the given name """
        return self.__name


class ClientChannel(object):
    """ A channel that stores lists of users

    Allows for easy name switching and storage of history
    """
    MAX_HISTORY = 100  # Length of History Buffer

    def __init__(self, name):
        """ Initialize Channell """
        self.__name = name
        self.__users = []
        self.__history = []

    def addUser(self, user):
        """ Add a user to channel """
        self.__users.append(user)

    def removeUser(self, user):
        """ Remove the user from channel """
        self.__users.remove(user)

    def receivedNames(self, users):
        """ Received a list of names to be used"""
        self.__users = users

    def userList(self):
        """ Return full list of users """
        return self.__users

    def chatHistory(self):
        """ Returns the chat history """
        return self.__history

    def addHistory(self, msg):
        """ Append a message to history, limited length """
        self.__history.append(msg)
        self.__history = self.__history[-self.MAX_HISTORY:]

    def userInChannel(self, user):
        """ Does the given user exist in channel """
        return user in self.__users

    def getName(self):
        """ Get the Name of the Channel """
        return self.__name


class IRCClient(IRC.Handler.IRCHandler):
    """ The IRC Client

    Takes the base IRCHandler and uses it to produce
    a fully formed Client for the IRC protocol.
    """

    def __init__(self, host, port, userinput=sys.stdin, autoQuit=False):
        """ Initialize Client"""
        self.__nick = "NEWUSER"
        super(IRCClient, self).__init__(self.__nick, host, port)
        self.__cmdProc = CommandProcessor()
        self.__server = None
        self.__noneChannel = self.__currentChannel = ClientChannel("None")
        self.__input = userinput
        self.__gui = ClientConsole(self)
        self.__tempNames = []
        self.__tempChannels = []
        self.__autoQuit = autoQuit
        self.__allUsers = {}
        self.__allChannels = {self.__noneChannel.getName(): self.__noneChannel}

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
        return [
            c
            for c in self.__allChannels.values()
            if c.userInChannel(self.findOrCreateUser(self.__nick))
        ]

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
            self.currentChannel().addHistory(msg)
        else:
            for c in channels:
                c.addHistory(msg)

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
        return self.__allChannels.values()

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
        if self.__autoQuit and socket == self.__server:
            self.stop()

    def notify(self, msg):
        """ Notify the GUI that there is a new message """
        self.updateChat(msg)

    def findOrCreateUser(self, name):
        """ Find or create a user reference """
        if name in self.__allUsers:
            return self.__allUsers[name]
        else:
            newuser = ClientUser(name)
            self.__allUsers[name] = newuser
            return newuser

    def findChannel(self, name):
        """ Find a a channel with the possibility of failure """
        if name in self.__allChannels:
            return self.__allChannels[name]
        else:
            return None

    def findOrCreateChannel(self, name):
        """ Find and potentially create channel """
        if self.findChannel(name):
            return self.findChannel(name)
        else:
            newchannel = ClientChannel(name)
            self.__allChannels[name] = newchannel
            return newchannel

    def allChannelsWithName(self, name):
        """ Return a list of all channels with a user in them """
        chans = []
        user = self.findOrCreateUser(name)
        for c in self.__allChannels.values():
            if c.userInChannel(user):
                chans.append(c)
        return chans

    def receivedNick(self, socket, src, newnick):
        """ Received a nickname.

        If it's for the client, update the nickname.
        Otherwise update the nickname of the specified clients
        """
        notify = self.allChannelsWithName(src)
        user = self.findOrCreateUser(src)
        user.updateName(newnick)

        if self.__nick == src:
            self.__nick = newnick
            self._ircmsg.updateSrc(newnick)
            self.updateChat(
                "*** You ({oldnick}) are now {newnick} ****".format(
                    oldnick=src,
                    newnick=newnick
                ),
                notify
            )
        else:
            self.updateChat(
                "*** {oldnick} is now {newnick} ****".format(
                    oldnick=src,
                    newnick=newnick
                ),
                notify
            )
        self.__gui.update()

    def receivedQuit(self, socket, src, msg):
        """ Received a quit command

        If it's for the client, shutdown.
        If it's for another client, remove them from chats.
        """
        user = self.findOrCreateUser(src)
        if src == "SERVER":
            notify = self.__allChannels.values()
        else:
            notify = self.allChannelsWithName(src)
            for c in notify:
                c.removeUser(user)

        if src in self.__allUsers:
            del self.__allUsers[src]

        self.updateChat(
            "*** {src} quit ({msg})".format(
                src=src,
                msg=msg
            ),
            notify
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
        user = self.findOrCreateUser(src)
        notify_chan = []
        for c in channels:
            chan = self.findOrCreateChannel(c)
            chan.addUser(user)
            notify_chan.append(chan)

        if src == self.__nick:
            self.notify(
                "*** You joined the channel(s) {channels}".format(
                    channels=",".join(channels)
                )
            )
        else:
            self.updateChat(
                "*** {src} joined the channel".format(src=src),
                notify_chan
            )
        self.__gui.update()

    def receivedLeave(self, socket, src, channels, msg):
        """ Received Leave

        If it's for the user, remove from specified channels.
        If it's for someone else, remove them from channels.
        """
        user = self.findOrCreateUser(src)
        notify_chan = []
        for c in channels:
            chan = self.findOrCreateChannel(c)
            if chan.userInChannel(user):
                chan.removeUser(user)
                notify_chan.append(chan)

        if src == self.__nick and self.__currentChannel in notify_chan:
            self.__currentChannel = self.__noneChannel

        self.updateChat(
            "*** {src} left the channel ({msg})".format(
                src=src,
                msg=msg
            ),
            notify_chan
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

    def filterChannels(self, c):
        return re.match("^#", c) != None

    def receivedMsg(self, socket, src, targets, msg):
        """ Update the chats with the new message depending on target"""

        channels = filter(lambda t: self.filterChannels(t), targets)
        channels = map(lambda c: self.findOrCreateChannel(c), channels)

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
                c = self.findOrCreateChannel(channel)
                newusers = []
                for n in self.__tempNames:
                    newusers.append(self.findOrCreateUser(n))
                c.receivedNames(newusers)

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
                old_set = set(self.__allChannels.keys())
                remove = old_set - new_set
                add = new_set - old_set
                for d in remove:
                    del self.__allChannels[d]
                for a in add:
                    self.findOrCreateChannel(a)

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
