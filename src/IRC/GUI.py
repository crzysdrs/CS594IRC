import curses
from curses import textpad
import logging


class BorderedWin(object):
    def __init__(self, title, height, width, y, x):
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
        return self.__border

    def getWin(self):
        return self.__win

    def redraw(self):
        self.__border.border()
        self.__border.addstr(0, 1, self.__title, curses.A_BOLD)
        self.__border.refresh()
        self.__win.refresh()


class ClientConsole(object):
    def __init__(self, client):
        self._client = client

    def isGUI(self):
        return False

    def update(self):
        pass

    def updateChat(self):
        pass

    def updateUsers(self):
        pass

    def updateChannels(self):
        pass

    def keypress(self):
        return self._client.getUserInput()


class ClientGUI(ClientConsole):
    def __init__(self, client, screen):
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
        return self.__screen != None

    def __update(self):
        for b in self.__borders:
            b.redraw()

        for w in self.__allWins:
            w.refresh()

    def update(self):
        self.__redrawChat()
        self.__redrawUsers()
        self.__redrawChannels()
        self.__update()

    def __redrawChat(self):
        self.__chatWin.clear()
        chats = self._client.getChats()[self._client.currentChannel()]
        for i in range(0, min(len(chats), self.__chatWin.getmaxyx()[0])):
            self.__chatWin.addstr(chats[i] + "\n")

        self.__update()

    def updateChat(self, ):
        self.__redrawChat()

    def __redrawUsers(self):
        self.__userWin.clear()
        all_users = self._client.getChannels()[self._client.currentChannel()]
        for i in range(0, min(len(all_users), self.__userWin.getmaxyx()[0])):
            self.__userWin.addstr(all_users[i] + "\n")

    def updateUsers(self):
        self.__redrawUsers()
        self.__update()

    def __redrawChannels(self):
        self.__channelWin.clear()
        all_chans = self._client.getChannels().keys()
        for i in range(0, min(len(all_chans), self.__channelWin.getmaxyx()[0])):
            cur = self._client.currentChannel() == all_chans[i]
            if cur:
                attr = curses.A_REVERSE
            elif all_chans[i] in self._client.getJoined():
                attr = curses.A_BOLD
            else:
                attr = curses.A_DIM
            if all_chans[i]:
                self.__channelWin.addstr(
                    "{chan}\n".format(chan=all_chans[i]),
                    attr
                )

    def updateChannels(self):
        self.__redrawChannels()
        self.__update()

    def keypress(self):
        k = self.__screen.getch()
        ret = None
        if k == curses.KEY_ENTER or (k < 256 and chr(k) == '\n'):
            ret = self.__textPad.gather()
            self.__textWin.clear()
        else:
            self.__textPad.do_command(k)

        self.__update()
        return ret
