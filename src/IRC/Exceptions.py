class InvalidIRCMessage(Exception):
    def __init__(self, socket, msg):
        self.socket = socket
        self.msg = msg
        
