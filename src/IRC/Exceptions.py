"""
A generic set of exceptions used by IRC Classes
"""

class InvalidIRCMessage(Exception):
    """ Notifies user of a message which is malformed"""
    def __init__(self, socket, msg):
        """ Initalize Invalid IRC message"""
        super(InvalidIRCMessage, self).__init__(self)
        self.socket = socket
        self.msg = msg
