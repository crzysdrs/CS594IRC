class InvalidIRCMessage(Exception):
    def __init__(self, socket, msg):
        super(InvalidIRCMessage, self).__init__(self)
        self.socket = socket
        self.msg = msg
