import socket
import logging
from time import sleep
from struct import pack, unpack
from typing import Any, Callable

from Crypto.Cipher import AES
from hashlib import sha256

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

from msg_frame import MSG_Frame, ChecksumError
from defines import *


class Connection():
    def __init__(self, 
                 host:str, 
                 port:int, 
                 max_retry:int=5, 
                 protocol:str='tcp', 
                 checksum:str='crc32',
                 compression:int=0, 
                 auto_reconnect:bool=False,
                 crypt_key:str=None, 
                 _recv_chunk_size:int=4096):
        self.host = host
        self.port = port
        
        self.crypt_key = crypt_key
        self.checksum = checksum
        self.auto_reconnect = auto_reconnect
        self._recv_chunk_size = _recv_chunk_size
        self.protocol = protocol
        self.max_retry = max_retry
        self.compression = compression       

    def _send(self, connection:socket.socket, msg:Any):
        msg = MSG_Frame(msg, crypt_key=self.crypt_key)
        
        try:
            msg.pack(checksum=self.checksum, compression=self.compression)
        except Exception as e:
            logging.error(f'Error packing message: {e}')
            raise e

        cmd_header = pack(PACKING_FORMAT, MSG_COMMAND, msg.bin_header_len)


        ack = None

        for _ in range(self.max_retry):

            try:
                connection.sendall(cmd_header)
                connection.sendall(msg.bin_header)
                connection.sendall(msg.bin_msg)
                ack = connection.recv(ACK_LEN)

                if ack != Status.OK.value:
                    logging.error('Error sending message')
                else:
                    break

            except ConnectionError as e:
                logging.error(f'Connection Error, clould not send message: {e}')
                continue

            except Exception as e:
                logging.error(f'Error sending message: {e}')
                raise e
        
        if ack != Status.OK.value:
            logging.error('Connection Error, clould not send message')
            raise ConnectionError('Error sending message')
        
        logging.info(f'Sent message to {connection.getpeername()}')

    def _recv_chunks(self, connection:socket.socket, total_size:int) -> bytes:
        ''' 
        When recieving data we need to do it in chunks. 
        This is because we want to keep our buffer size small.
        '''

        data = b''
        bytes_left = total_size

        while bytes_left >= self._recv_chunk_size:
            chunk = connection.recv(self._recv_chunk_size)
            if not chunk:
                logging.error('Connection Error, could not receive message')
                raise ConnectionError('Error receiving message')
            data += chunk
            bytes_left -= len(chunk)

        if bytes_left > 0:
            chunk = connection.recv(bytes_left)
            if not chunk:
                logging.error('Connection Error, could not receive message')
                raise ConnectionError('Error receiving message')
            data += chunk

        return data

    def _recv(self, connection:socket.socket) -> MSG_Frame:
        msg = None
        for _ in range(self.max_retry):
            try:
                cmd_header = connection.recv(CMD_LEN)
                cmd, header_len = unpack(PACKING_FORMAT, cmd_header)

                if cmd != MSG_COMMAND:
                    logging.error('Invalid command header')
                    raise ValueError('Invalid command header')
                
                rx_msg = MSG_Frame(None, crypt_key=self.crypt_key)

                rx_msg.bin_header_len = header_len
                rx_msg.bin_header = connection.recv(header_len)

                header = rx_msg.unpack_header()
                rx_msg.bin_msg = self._recv_chunks(connection, header.data_len)

            
                msg = rx_msg.unpack()

            except ChecksumError as e:
                logging.error(f'Checksum error: {e}')
                connection.sendall(Status.OK.value)
                continue
        
            except ValueError as e:
                logging.error(f'Value error: {e}')
                connection.sendall(Status.ERROR.value)
                continue

            except ConnectionError as e:
                logging.error(f'Connection error: {e}')
                connection.sendall(Status.ERROR.value)
                continue

            except Exception as e:
                logging.error(f'Error unpacking message: {e}')
            
            connection.sendall(Status.OK.value)
            break

        return msg

class Server(Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.clients = {}

    def start(self):
        if self.protocol == 'udp':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        elif self.protocol == 'tcp':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            logging.error('Invalid protocol')
            raise ValueError('Invalid protocol')

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # allow reuse of address and port
        self.socket.bind((self.host, self.port))
        logging.info(f'Server started on {self.host}:{self.port}')

    def wait_for_connection(self, num_connections:int=1):
        self.socket.listen(1)
        for _ in range(num_connections):
            connection, client_address = self.socket.accept()
            connection.settimeout(5)
            connection.setblocking(True)
            self.clients[str(client_address)] = connection
            logging.info(f'Connection from {client_address}')

    def send(self, addr:str, msg:Any):
        if addr not in self.clients:
            logging.error(f'Invalid address: {addr}')
            raise ValueError('Invalid address')

        success = False
        
        while True:
            try:
                self._send(self.clients[addr], msg)
                return
            except Exception as e:
                if self.auto_reconnect:
                    logging.info('Reconnecting to client, address: {addr}')
                    self.close_connection(addr)
                    while self.clients.get(addr) is None:
                        self.wait_for_connection(1)
                else:
                    raise e
            

    def send_all(self, msg:MSG_Frame):
        for addr, connect in self.clients.items():
            self.send(connect, msg)
    
    def recv(self, addr:str) -> Any:
        if addr not in self.clients:
            logging.error(f'Invalid address: {addr}')
            raise ValueError('Invalid address')
        
        while True:
            try:
                msg = self._recv(self.clients[addr])
                return msg
            except Exception as e:
                if self.auto_reconnect:
                    logging.info('Reconnecting to client, address: {addr}')
                    self.close_connection(addr)
                    while self.clients.get(addr) is None:
                        self.wait_for_connection(1)
                else:
                    raise e
                

    
    def recv_all(self) -> dict:
        msgs = {}
        for addr, connect in self.clients.items():
            msgs[addr] = self.recv(connect)
        return msgs
    
    def get_clients(self) -> list:
        return list(self.clients.keys())
    
    def close_connection(self, addr:str):
        if addr not in self.clients:
            logging.error(f'Invalid address: {addr}')
            raise ValueError('Invalid address')

        self.clients[addr].close()
        del self.clients[addr]
        logging.info(f'Connection to {addr} closed')
    
    def close_all_connections(self):
        for addr, connect in self.clients.items():
            self.close_connection(addr)

    def stop(self):
        self.close_all_connections()
        self.socket.close()
        logging.info('Server closed')

class Client(Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def connect(self, wait:bool=True):
        if self.protocol == 'udp':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        elif self.protocol == 'tcp':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            logging.error('Invalid protocol')
            raise ValueError('Invalid protocol')

        self.socket.setblocking(True)
        if wait:
            while(1):
                try:
                    self.socket.connect((self.host, self.port))
                    logging.info(f'Connected to {self.host}:{self.port}')
                    break
                except:
                    logging.info(f'Waiting for server on {self.host}:{self.port}')
                    sleep(1)
        else:
            for i in range(self.max_retry):
                try:
                    self.socket.connect((self.host, self.port))
                    logging.info(f'Connected to {self.host}:{self.port}')
                    break
                except:
                    if i == self.max_retry - 1:
                        logging.error(f'Could not connect to {self.host}:{self.port}')
                        raise ConnectionError(f'Could not connect to {self.host}:{self.port}')
                    logging.info(f'Waiting for server on {self.host}:{self.port}')
                    sleep(1)

    def send(self, msg:Any):
        success = False

        while True:
            try:
                self._send(self.socket, msg)
                return
            except Exception as e:
                if self.auto_reconnect:
                    logging.info('Resetting connection')
                    self.disconnect()
                    self.connect()
                    logging.info('Reconnected to server')
                else:
                    raise e


    def recv(self) -> Any:
        success = False

        while True:
            try:
                msg = self._recv(self.socket)
                return msg
            except Exception as e:
                if self.auto_reconnect:
                    logging.info('Resetting connection')
                    self.disconnect()
                    self.connect()
                    logging.info('Reconnected to server')
                    continue
                else:
                    raise e

    
    def disconnect(self):
        self.socket.close()
        logging.info(f'Disconnected from {self.host}:{self.port}')

    