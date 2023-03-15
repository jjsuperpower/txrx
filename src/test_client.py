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

cap = cv2.VideoCapture(0)

while(1):
    # send msg to server
    ret, frame = cap.read()
    client.send(frame)

