from txrx import Server

PORT = 5001
HOST = '0.0.0.0'

server = Server(HOST, PORT, crypt_key='test')
server.start()
server.wait_for_connection()
server.wait_for_connection()

client1, client2 = server.get_clients()

# while(1):
#     # receive msg from client
#     msg = server.recv(client)
#     print(msg)

#     # send msg to client
#     msg = input('Enter message: ')
#     server.send(client, msg)

#     print('-' * 20)

# test using opencv to receive video frames
import cv2
import numpy as np

cap = cv2.VideoCapture(0)

while(1):
    # send msg to server
    ret, frame = cap.read()
    server.send(client1, frame)
    server.send(client2, frame)
