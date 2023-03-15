from txrx import Server

PORT = 5001
HOST = '0.0.0.0'

server = Server(HOST, PORT, crypt_key='test')
server.start()
server.wait_for_connection()

client = server.get_clients()[0]

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

while(1):
    # receive msg from client
    frame = server.recv(client)

    # display frame
    cv2.imshow('frame', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
