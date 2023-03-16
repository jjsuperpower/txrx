from txrx import Client
import time

PORT = 5001
HOST = '127.0.0.1'
client = Client(HOST, PORT, crypt_key='test', compression=9)
client.connect()


# while(1):
#     # send msg to server
#     msg = input('Enter message: ')
#     client.send(msg)

#     # receive msg from server
#     msg = client.recv()
#     print(msg)

#     print('-' * 20)


# test using opencv to send video frames
import cv2
import numpy as np


while(1):
    # receive msg from client
    frame = client.recv()

    # display frame
    cv2.imshow('frame', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
