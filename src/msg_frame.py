
import pickle
from typing import Callable, Any
import zlib
import hashlib

class ChecksumError(Exception):
    pass

class MSG_Header():
    def __init__(self):
        self.data_len = None
        self.encrypted = None
        self.compression = None
        self.checksum_type = None
        self.checksum = None

    def pack(self):
        return pickle.dumps(self)

    @staticmethod
    def unpack(bin_header:bytes):
        msg_header = pickle.loads(bin_header)
        if not isinstance(msg_header, MSG_Header):
            raise TypeError('Invalid header type')
        return msg_header

class MSG_Frame():
    '''Message frame class
    
    This class is used to create a message frame object. The message frame
    object is used to send messages between the client and server. The message
    frame object is pickled and sent over the socket connection.

    Attributes:
    
    '''
    def __init__(self, msg:Any) -> None:
        '''Constructor for the MSG_Frame class
        '''

        self.bin_header_len = None
        self.bin_header = None
        self.bin_msg = None
        self.msg = msg


    def pack(self, 
            checksum:str='crc32',
            crypt_fn:Callable=None,
            compression:int=0,
            ) -> None:

        bin_msg = pickle.dumps(self.msg)
        
        if compression > 0:
            bin_msg = zlib.compress(bin_msg, compression)

        if crypt_fn:
            bin_msg = crypt_fn.encrypt(bin_msg)

        msg_check = MSG_Frame.get_checksum(bin_msg, checksum)

        header = MSG_Header()
        header.data_len = len(bin_msg)
        header.encrypted = True if crypt_fn else False
        header.compression = compression
        header.checksum_type = checksum
        header.checksum = msg_check

        self.bin_msg = bin_msg
        self.bin_header = header.pack()
        self.bin_header_len = len(self.bin_header)

    def unpack_header(self) -> MSG_Header:
        # check the header length
        if len(self.bin_header) != self.bin_header_len:
            raise ValueError('Invalid message header length')

        return MSG_Header.unpack(self.bin_header)


    def unpack(self, crypt_fn:Callable=None) -> Any:
        header = self.unpack_header()

        # check the checksum
        MSG_Frame.check_checksum(header.checksum_type, self.bin_msg, header.checksum)

        bin_msg = self.bin_msg

        # decrypt the message
        if header.encrypted:
            bin_msg = crypt_fn.decrypt(bin_msg)

        # decompress the message
        if header.compression > 0:
            bin_msg = zlib.decompress(bin_msg)

        # unpickle the message
        msg = pickle.loads(bin_msg)

        return msg


    @staticmethod
    def get_checksum(data:bytes, check_type:str) -> str:
        if check_type == 'crc32':
            data_check = zlib.crc32(data)
        elif check_type == 'md5':
            data_check = hashlib.md5(data).hexdigest()
        elif check_type == 'sha256':
            data_check = hashlib.sha256(data).hexdigest()
        elif check_type == 'sha512':
            data_check = hashlib.sha512(data).hexdigest()
        else:
            raise ValueError(f'Invalid checksum type: {check_type}')
        return data_check
    
    @staticmethod
    def check_checksum(check_type:str, data:bytes, check:str) -> None:
        data_check = MSG_Frame.get_checksum(data, check_type)
        if data_check != check:
            raise ChecksumError('Invalid checksum')
        