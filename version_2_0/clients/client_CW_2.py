from concurrent.futures import thread
from email import message
import socket
import threading
import binascii
import sys
import os
import time
# UDP_IP = "192.168.1.226"
UDP_IP = "192.168.1.120"
# UDP_IP = "10.77.102.165"
# UDP_IP = "10.77.68.2"
PORT = 5056
ADDRESS = (UDP_IP, PORT)
FORMAT = 'utf-8'
SIZE = 2048
DISCONNECT_MESSAGE = 'DISCONNECT!'
TIME_OUT = 0.5  # 500ms
NUM_OF_RETRANSMISSIONS = 3
CHUNK_SIZE = 1400  # 1400 Bytes
USER_NAME = ''
TYPE_OF_MESSAGE = [
    'Join_Request',
    'Access_Granted',
    'Request_Users_Present',
    'Response_Users_Present',
    'Send_invite',
    'Forward_invite',
    'Disconnect',
    'ERR_SERVER_FULL',
    'ERR_USERNAME_TAKEN',
    'ERR_INVALID_FORMAT',
    'DISCONNECT!',
    'DISCONNECTING',
    'List'

]

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def create_packet(packet_type="data", seq_no=0, body=""):
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    packet = (f'{packet_type}|{seq_no}|{body}|{checksum}')
    return packet


def parse_packet(message):
    pieces = message.split("|")
    packet_type, seq_no = pieces[:2]
    print(f'TESTING PACKET PACKET_Type, seq_no   {packet_type} {seq_no}')
    body = pieces[2:-1]
    body = "|".join(body)
    print(f'TESTING PACKET BODY   {body}')
    checksum = pieces[-1]
    print(f'TESTING PACKET checksum  {checksum}')

    return packet_type, seq_no, body, checksum


def build_packet_formation(message_type, content=None, length=None):
    len_msg = len(content)
    if length:
        len_msg = length

    msg = (f"{message_type}$;{len_msg}$;{content}")
    # print(f'TESTING MESSAGE_TYPE ---->>>> {message_type}')
    if message_type in TYPE_OF_MESSAGE:
        packet_formation = create_packet("data", 0, msg)
        # print(f'TESTING PACKET FORMATION {packet_formation}')
    return packet_formation


def get_message_type(packet):
    print(f'TESTING DATA RECIEVED ----->>>>{packet.decode(FORMAT)} ')
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[0]
    return message


def get_body_content(packet):
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[2:]
    return message


def get_file(packet):
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    print(f'TESTING FORWARD MESSAGE  {body} body type {type(body)}')
    length = body.split('$;')[:4]
    final_length = len(" ".join(length))
    message = body[final_length+5:]
    # message = body.split()[len+2:]

    print(f'TESTING FORWARD MESSAGE  {message}')
    # file = " ".join(message)
    # print(f'TESTING FORWARD FILE  {file}')
    return message


def handle_server():

    connected = True
    while connected:
        server_data = client.recv(SIZE)
        message = get_message_type(server_data)
        print(f'i am in handle server and the message is {message}')
        # if server is not full we can connect
        if message == 'Access_Granted':
            print(f"Connected to Server: {ADDRESS[0]}")

        # when server sends an invitation we save it
        elif message == 'Forward_invite':
            data = get_body_content(server_data)
            file_data = get_file(server_data).encode(FORMAT)
            sending_user = " ".join(data[:1])
            current_file_name = "".join(data[1])
            file_name = sending_user+'_' + current_file_name

            f = open(file_name, 'wb')
            f.write(file_data)
            print(f'INVITE: {sending_user}')
            f.close()
            message = 'Waiting to recieve more data ...'

        elif message == 'Response_Users_Present':
            print(f'UserList: {get_body_content(server_data)}')

        # if server full disconnect
        elif message == 'ERR_SERVER_FULL':
            print('Server Disconnected: Server Maxed Out')
            print('DISCONNECTING')
            os._exit(os.EX_OK)
        # if invalid message was sent print the message sent by server
        elif message == 'ERR_INVALID_FORMAT':
            print(f'[SERVER] -> {message}')

        else:
            print(f'MESAGE RECIEVED IS NOT RECOGNISED: --> {message}')
        # connected = False


def main():
    connected = True
    t = threading.Thread(target=handle_server)
    t.start()
    while connected:
        # allow time for a server response
        time.sleep(0.5)
        print('i am in MAIN')
        message = input()
        # request user list from the server
        if message == 'List':
            message = build_packet_formation('Request_Users_Present', "")
            client.sendto(message.encode(FORMAT), ADDRESS)
            time.sleep(0.1)
            print(f'TESTING PACKET SENT ----->>>>{message}')

        # close connection with the server
        if message == 'quit':
            message = build_packet_formation('DISCONNECT!', "Ionut")
            client.sendto(message.encode(FORMAT), ADDRESS)
            print('DISCONNECTING')
            connected = False
            print(f'TESTING PACKET SENT ----->>>>{message}')
            os._exit(os.EX_OK)

        # send an invitation to selected users
        if message.split()[0] == 'invite':
            users_ = message.split()[1:-1]
            users = ""
            for user in users_:
                users += f'{user}$;'

            no_of_users = len(users_)

            file_name = message.split()[-1]
            f = open(file_name, 'r')
            file_data = f.read(SIZE)
            body = "".join(users) + file_name + '$;' + file_data
            body = f'{no_of_users}$;{body}'
            message = build_packet_formation(
                'Send_invite', body)
            client.sendto(message.encode(FORMAT), ADDRESS)
            f.close()
            print(f'TESTING PACKET SENT ----->>>>{message}')


if __name__ == '__main__':
    USER_NAME = input('Please enter a user name: ')
    client.sendto(build_packet_formation('Join_Request',
                                         USER_NAME).encode(FORMAT), ADDRESS)

    main()
