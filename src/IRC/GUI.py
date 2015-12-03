"""
IRC.GUI

Provides the classes to handle a given GUI or console interface
for a client
"""
import curses
from curses import textpad
import logging


class BorderedWin(object):
    """Creates a bordered ncurses window"""

    def __init__(self, title, height, width, y, x):
        """ Initialize a new bordered window """
        logging.info(
            "Create Border {height},{width},{y},{x}".format(
                height=height,
                width=width,
                y=y,
                x=x
            )
        )
        self.__border = curses.newwin(height, width, y, x)
        self.__win = self.__border.subwin(height - 2, width - 2, y + 1, x + 1)
        self.__title = title
        self.__win.scrollok(True)

    def getBorder(self):
        """ Return the border part of the window"""
        return self.__border

    def getWin(self):
        """ Return the interior part of the window"""
        return self.__win

    def redraw(self):
        """ Redraw this window"""
        self.__border.border()
        self.__border.addstr(0, 1, self.__title, curses.A_BOLD)
        self.__border.refresh()
        self.__win.refresh()


class ClientConsole(object):
    """ A generic console implementation stub to allow the
    subclassing of a GUI Client implementation"""

    def __init__(self, client):
        """ Initialize Default Console View"""
        self._client = client

    def isGUI(self):
        """ Not running GUI"""
        return False

    def update(self):
        """ Stub """
        pass

    def updateChat(self):
        """ Stub """
        pass

    def updateUsers(self):
        """ Stub """
        pass

    def updateChannels(self):
        """ Stub """
        pass

    def keypress(self):
        """ Retreives the clients input"""
        return self._client.getUserInput()


class ClientGUI(ClientConsole):
    """ An NCurses implementation of a GUI

    Manages all windows and updates accordingly
    """

    def __init__(self, client, screen):
        """ Initialize Curses based GUI Window"""
        super(ClientGUI, self).__init__(client)
        self.__screen = screen
        self.__borders = []

        (height, width) = self.__screen.getmaxyx()
        chanB = BorderedWin("Channels", height - 1, 15, 0, 0)
        self.__borders.append(chanB)
        self.__channelWin = chanB.getWin()

        userB = BorderedWin("Users", height - 1, 15, 0, width - 15)
        self.__userWin = userB.getWin()
        self.__borders.append(userB)

        chatB = BorderedWin(
            "Chat", height - 1,
            userB.getBorder().getbegyx()[1] - chanB.getBorder().getmaxyx()[1],
            0, chanB.getBorder().getmaxyx()[1]
        )
        self.__chatWin = chatB.getWin()
        self.__borders.append(chatB)

        self.__textWin = curses.newwin(1, width, height - 1, 0)
        self.__textPad = textpad.Textbox(self.__textWin)

        self.__allWins = [self.__screen, self.__textWin, ]
        self.__update()

    def isGUI(self):
        """ Client is running in GUI mode"""
        return True

    def __update(self):
        """ Update all the windows on screen"""
        for b in self.__borders:
            b.redraw()

        for w in self.__allWins:
            w.refresh()

    def update(self):
        """ Redraw all windows and update screen"""
        self.__redrawChat()
        self.__redrawUsers()
        self.__redrawChannels()
        self.__update()

    def __redrawChat(self):
        """ Redraw the chat messages window"""
        self.__chatWin.clear()
        chats = self._client.currentChannel().chatHistory()
        count = min(len(chats), self.__chatWin.getmaxyx()[0])
        shown = chats[-count:]
        for c in shown:
            self.__chatWin.addstr(c + "\n")

        self.__update()

    def updateChat(self, ):
        """ Update the chat window on screen"""
        self.__redrawChat()

    def __redrawUsers(self):
        """ Redraw the users window on screen"""
        self.__userWin.clear()

        all_users = [u for u in self._client.currentChannel().userList()]
        all_users.sort(key=lambda u: u.getName())
        count = min(len(all_users), self.__userWin.getmaxyx()[0])
        all_users = all_users[:count]
        for user in all_users:
            self.__userWin.addstr(user.getName() + "\n")

    def updateUsers(self):
        """ Update the users window on screeen"""
        self.__redrawUsers()
        self.__update()

    def __redrawChannels(self):
        """ Redraw the channels window"""
        self.__channelWin.clear()
        all_chans = self._client.getChannels()
        all_chans.sort(key=lambda c: c.getName())
        count = min(len(all_chans), self.__channelWin.getmaxyx()[0])
        show = all_chans[:count]
        for c in show:
            cur = self._client.currentChannel() == c
            if cur:
                attr = curses.A_REVERSE
            elif c in self._client.getJoined():
                attr = curses.A_BOLD
            else:
                attr = curses.A_DIM
            if c.getName() != "None":
                self.__channelWin.addstr(
                    "{chan}\n".format(chan=c.getName()),
                    attr
                )

    def updateChannels(self):
        """ Update the channels window"""
        self.__redrawChannels()
        self.__update()

    def keypress(self):
        """ Recieve keypress from textpad and return string if recieved"""
        k = self.__screen.getch()
        ret = None
        if k == curses.KEY_ENTER or (k < 256 and chr(k) == '\n'):
            ret = self.__textPad.gather()
            self.__textWin.clear()
        else:
            self.__textPad.do_command(k)

        self.__update()
        return ret
