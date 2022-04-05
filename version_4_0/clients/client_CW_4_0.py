from concurrent.futures import thread
from email import message
from http import server
from pickle import FALSE
import socket
import threading
import binascii
import sys
import os
import time
import random
from queue import Queue, Empty
# UDP_IP = "192.168.1.226"
UDP_IP = "192.168.1.120"
# UDP_IP = "10.77.102.165"
# UDP_IP = "10.77.68.2"
PORT = 5056
ADDRESS = (UDP_IP, PORT)
FORMAT = 'utf-8'
SIZE = 2048
DISCONNECT_MESSAGE = 'Disconnect'
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
    'DISCONNECTING',
    'List',
    'ACK',
    'START',
    'END',
    'DATA',

]


saved_message = ""
saved_data = b''
reciving_strings = [
    'START',
    'END',
    'DATA',
]

recieving_type_queue = Queue()
recieving_seq_no_queue = Queue()
recieving_checksum_queue = Queue()


client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def create_packet(packet_type="data", seq_no=0, body=""):
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    packet = (f'{packet_type}|{seq_no}|{body}|{checksum}')
    return packet


def parse_packet(message):
    pieces = message.split("|")
    packet_type, seq_no = pieces[:2]
    # print(f'TESTING PACKET PACKET_Type, seq_no   {packet_type} {seq_no}')
    body = pieces[2:-1]
    body = "|".join(body)
    # print(f'TESTING PACKET BODY   {body}')
    checksum = pieces[-1]
    # print(f'TESTING PACKET checksum  {checksum}')

    return packet_type, seq_no, body, checksum


def build_packet_formation(packet_type, message_type,  seq_no=0, content="", length=None):
    len_msg = len(content)
    if length:
        len_msg = length
    if message_type == "" and content == "":
        msg = ""
    else:
        msg = (f"{message_type}$;{len_msg}$;{content}")
    # print(f'TESTING MESSAGE_TYPE ---->>>> {message_type}')
    if message_type in TYPE_OF_MESSAGE or message_type == "":
        packet_formation = create_packet(packet_type, seq_no, msg)
        # print(f'TESTING PACKET FORMATION {packet_formation}')
    return packet_formation


def send_packet(packet, addr):
    ack = True
    start_seq_no = random.randint(1, 20)
    while ack:
        send_start_packet(addr, start_seq_no)
        try:
            r = recieving_type_queue.get(timeout=0.3)
            if r == 'ACK':
                ack = False
                break
        except Empty:
            pass

    ack = True
    while ack:
        send_data_packet(packet, addr, start_seq_no+1)

        try:
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
                ack = False
                break
        except Empty:
            pass

    ack = True
    while ack:
        send_end_packet(addr, start_seq_no+2)
        try:
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
                ack = False
                break
        except Empty:
            pass


def handle_reciving_data(server_data, packet_type, message):
    seq_no = get_seq_no(server_data)
    if packet_type == "START":
        send_ack_packet(seq_no, ADDRESS)
    elif packet_type == "DATA":
        send_ack_packet(seq_no, ADDRESS)
        global saved_message
        global saved_data
        saved_message = message
        saved_data = server_data
    elif packet_type == "END":
        send_ack_packet(seq_no, ADDRESS)
        return saved_message


def send_start_packet(addr, seq_no):
    start_pkt = build_packet_formation(
        'START', "", seq_no, "")
    client.sendto(start_pkt.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{start_pkt}')


def send_end_packet(addr, seq_no):
    send_ack_before_data = build_packet_formation('END', "", seq_no, "")
    client.sendto(send_ack_before_data.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{send_ack_before_data}')


def send_data_packet(packet, addr, seq_no):
    pack_type, mess_type, content = packet
    packet = build_packet_formation(pack_type, mess_type, seq_no, content)
    client.sendto(packet.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{packet}')


def send_ack_packet(seq_no, addr):
    seq_no = int(seq_no)
    send_ack_before_data = build_packet_formation('ACK', "", seq_no+1, "")
    client.sendto(send_ack_before_data.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{send_ack_before_data}')


def get_message_type(packet):
    print(f'TESTING DATA RECIEVED <<<<-----{packet.decode(FORMAT)} ')
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


def get_packet_type(packet):
    packet_type, _, _, _ = parse_packet(packet.decode(FORMAT))
    return packet_type


def get_seq_no(packet):
    _, seq_no, _, _ = parse_packet(packet.decode(FORMAT))
    return seq_no


def get_checksum(packet):
    _, _, _, checksum = parse_packet(packet.decode(FORMAT))
    return checksum


def handle_server():

    connected = True
    while connected:
        server_data = client.recv(SIZE)
        message = get_message_type(server_data)
        packet_type = get_packet_type(server_data)

        if packet_type != "":
            recieving_type_queue.put(get_packet_type(server_data))
            recieving_seq_no_queue.put(get_seq_no(server_data))
        if packet_type in reciving_strings:
            message = handle_reciving_data(
                server_data, packet_type, message)
            server_data = saved_data

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
        message = ""


def main():
    connected = True
    t = threading.Thread(target=handle_server)
    t.start()
    USER_NAME = input('Please enter a user name: ')
    packet = ('DATA', 'Join_Request', USER_NAME)
    send_packet(packet, ADDRESS)

    while connected:
        # allow time for a server response
        time.sleep(0.5)
        print('i am in MAIN')
        message = input()
        # request user list from the server
        if message == 'List':
            packet = ('DATA', 'Request_Users_Present', "")
            send_packet(packet, ADDRESS)
            time.sleep(0.1)
            print(f'TESTING PACKET SENT ----->>>>{message}')

        # close connection with the server
        if message == 'quit':
            packet = ('DATA', 'Disconnect', "Ionut")
            send_packet(packet, ADDRESS)
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
            packet = ('DATA', 'Send_invite', body)
            send_packet(packet, ADDRESS)
            f.close()
            print(f'TESTING PACKET SENT ----->>>>{message}')


if __name__ == '__main__':

    main()
