from enum import Enum

PACKING_FORMAT = '>4sI' # 4 bytes for the header type and 4 bytes for the header length

CMD_LEN = 8 # length of the command header
MSG_COMMAND = b'MSG\0'

ACK_LEN = 4 # length of the ack header

class Status(Enum):
    OK = b'OK\0\0'
    ERROR = b'ERR\0'
