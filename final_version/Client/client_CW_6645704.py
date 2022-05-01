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
import base64
import hashlib
from cryptography.fernet import Fernet


# UDP_IP = "192.168.1.226"
UDP_IP = "192.168.1.120"
# UDP_IP = "172.20.10.3"
# UDP_IP = "10.77.68.2"
KEY = ''
PORT = 5056
ADDRESS = (UDP_IP, PORT)
FORMAT = 'utf-8'
SIZE = 14000
DISCONNECT_MESSAGE = 'Disconnect'
USER_NAME = ''
CONNECTED_USERS = []
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
    'ERR_UNAUTHORIZED_ACCESS',
    'DISCONNECTING',
    'List',
    'ACK',
    'START',
    'END',
    'DATA',

]
EXPECTED_USER_INPUTS = ['help', 'invite', 'quit', 'list']


saved_message = ""
saved_data = b''
reciving_strings = [
    'START',
    'END',
    'DATA',
]

# Queues
recieving_type_queue = Queue()
recieving_seq_no_queue = Queue()
recieving_checksum_queue = Queue()

# generate encryption/decription key this code should be the same for everyone using python
password = 'networking'
password = password.encode(encoding='UTF-8')
key = hashlib.md5(password).hexdigest()
key = key.encode(encoding='UTF-8')
key_64 = base64.urlsafe_b64encode(key)


# create socket
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# method to decript a packet


def decrypt_packet(packet):
    fernet = Fernet(key_64)
    decrypted_packet = fernet.decrypt(packet).decode('utf-8')
    return decrypted_packet


def recalculate_checksum(data):
    _, _, body, _ = parse_packet(decrypt_packet(data))
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    return checksum

# method to encript a packet


def encrypt_packet(packet):
    fernet = Fernet(key_64)
    encrypted_packet = fernet.encrypt(packet.encode('utf-8'))
    return encrypted_packet

# x = 0

# method to create a packet


def create_packet(packet_type="data", seq_no=0, body=""):
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    packet = (f'{packet_type}|{seq_no}|{body}|{checksum}')

    return packet


'''
    global x
    if (x == 0):
        packet = packet + "1"
        x=x+1
'''


# method to parse a packet


def parse_packet(packet):
    # split the packet by |
    part = packet.split("|")
    # first and second parts belong to type and the sequence number
    packet_type, seq_no = part[:2]
    # everythig between the second and last element will be the body
    body = part[2:-1]
    body = "|".join(body)
    # last bit of the packet contains the checksum
    checksum = part[-1]

    return packet_type, seq_no, body, checksum

# method to build packets calls create_packet and returns a packet


def build_packet_formation(packet_type, message_type,  seq_no=0, content="", length=None):
    len_msg = len(content)
    # check if there is any content
    if length:
        # save the content length
        len_msg = length
    # if there is no type or content we send an empty message
    if message_type == "" and content == "":
        msg = ""
    # otherwise we create a message with the type, length and content
    else:
        msg = (f"{message_type}$;{len_msg}$;{content}")
    # check if the type of message being sent is valid to prevent sending unsuported types to the server
    if message_type in TYPE_OF_MESSAGE or message_type == "":
        # create the packet
        packet_formation = create_packet(packet_type, seq_no, msg)

    return packet_formation

# method to send packets, this method will deliver packets as specified in the RFC


def send_packet(packet, addr):
    ack = True
    # create a random sequence number
    start_seq_no = random.randint(1, 20)
    while ack:

        try:
            # wait for a response before retransmiting
            r = recieving_type_queue.get(timeout=0.3)
            if r == 'ACK':
                ack = False
                break
        except Empty:
            # send start packet
            send_start_packet(addr, start_seq_no)
            pass

    ack = True
    # global variable x to test for duplcate packets
    #x = 0
    while ack:

        try:
            # wait for a response before retransmiting
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
                ack = False
                break
        except Empty:
            # send data packet
            send_data_packet(packet, addr, start_seq_no+1)

            pass
        '''
        #Packet Duplication Test
        if (x == 0):
            send_data_packet(packet, addr, start_seq_no+1)
            x=x+1
        '''
    ack = True
    while ack:

        try:
            # wait for a response before retransmiting
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
                ack = False
                break
        except Empty:
            # send end packet
            send_end_packet(addr, start_seq_no+2)
            pass

# checks for incoming packet type and return the message type


def handle_reciving_data(server_data, packet_type, message):
    # save packet's sequence number
    seq_no = get_seq_no(server_data)
    # we send an ack packet if packet type is START
    if packet_type == "START":
        send_ack_packet(seq_no, ADDRESS)
    elif packet_type == "DATA" and recalculate_checksum(server_data) == get_checksum(server_data):
        # we send an ack packet if packet type is DATA and checksum is correct
        send_ack_packet(seq_no, ADDRESS)
        global saved_message
        global saved_data
        # kepp a global copy of the message and data for later use
        saved_message = message
        saved_data = server_data
    elif packet_type == "END":
        # we send an ack packet if packet type is END
        send_ack_packet(seq_no, ADDRESS)
        return saved_message

# method for sending a START packet


def send_start_packet(addr, seq_no):
    start_pkt = build_packet_formation(
        'START', "", seq_no, "")
    # encript and send the packet
    client.sendto(encrypt_packet(start_pkt), addr)
    print(f'PACKET SENT[Ionut Client] ----->>>>{start_pkt}')

# method for sending an END packet


def send_end_packet(addr, seq_no):
    send_ack_before_data = build_packet_formation('END', "", seq_no, "")
    # encript and send the packet
    client.sendto(encrypt_packet(send_ack_before_data), addr)
    print(f'PACKET SENT[Ionut Client] ----->>>>{send_ack_before_data}')

# method for sending an DATA packet


def send_data_packet(packet, addr, seq_no):
    pack_type, mess_type, content = packet
    packet = build_packet_formation(pack_type, mess_type, seq_no, content)
    # encript and send the packet
    client.sendto(encrypt_packet(packet), addr)
    print(f'PACKET SENT[Ionut Client] ----->>>>{packet}')

# method for sending an ACK packet


def send_ack_packet(seq_no, addr):
    seq_no = int(seq_no)
    send_ack_before_data = build_packet_formation('ACK', "", seq_no+1, "")
    # encript and send the packet
    client.sendto(encrypt_packet(send_ack_before_data), addr)
    print(f'PACKET SENT[Ionut Client] ----->>>>{send_ack_before_data}')

# retrieve the message type eg. "Join Request"


def get_message_type(packet):
    print(f'PACKET RECEIVED[Ionut Client] <<<<-----{decrypt_packet(packet)} ')
    _, _, body, _ = parse_packet(decrypt_packet(packet))
    message = body.split('$;')[0]
    return message

# retrive the content of body


def get_body_content(packet):
    _, _, body, _ = parse_packet(decrypt_packet(packet))
    message = body.split('$;')[2:]
    return message

# retrieve the file from a data packet


def get_file(packet):
    _, _, body, _ = parse_packet(decrypt_packet(packet))
    length = body.split('$;')[:4]
    final_length = len(" ".join(length))
    file = body[final_length+5:]

    return file

# retrive packet type


def get_packet_type(packet):
    packet_type, _, _, _ = parse_packet(decrypt_packet(packet))
    return packet_type

# retrive sequence number


def get_seq_no(packet):
    _, seq_no, _, _ = parse_packet(decrypt_packet(packet))
    return seq_no

# retrieve checksum


def get_checksum(packet):
    _, _, _, checksum = parse_packet(decrypt_packet(packet))
    return checksum

# method to handle incomming data


def handle_server():

    connected = True
    while connected:
        server_data = client.recv(SIZE)
        message = get_message_type(server_data)
        packet_type = get_packet_type(server_data)

        if packet_type != "":
            # save the packet type in a queue
            recieving_type_queue.put(get_packet_type(server_data))
            # save the sequence number in a queue
            recieving_seq_no_queue.put(get_seq_no(server_data))
            # only known packet types are passing through, If the incomming packet is not recognised
            # we ignore it
        if packet_type in reciving_strings:
            # handle reciving data will check for packet type and return a message type
            message = handle_reciving_data(
                server_data, packet_type, message)
            server_data = saved_data

        # if all conditions are met we can connect
        if message == 'Access_Granted':
            print(f"Connected to Server: {ADDRESS[0]}, {ADDRESS[1]}")

        # when server sends an invitation card we save it
        elif message == 'Forward_invite':
            # retrieve body content
            data = get_body_content(server_data)
            # separate the file content from the rest of the body content
            file_data = get_file(server_data).encode(FORMAT)
            # get the sending user name
            sending_user = " ".join(data[:1])
            # get the fine lame
            current_file_name = "".join(data[1])
            # add sending user name to the file name
            file_name = sending_user+'_' + current_file_name

            # open and save the file as username_filename.txt
            f = open(file_name, 'wb')
            f.write(file_data)
            print(f'INVITE: {sending_user}')
            # close the file
            f.close()
            message = 'Waiting to recieve more data ...'
        # retrieve the user names from the body data
        elif message == 'Response_Users_Present':
            global CONNECTED_USERS
            # save the connected users in a global variable for later use
            CONNECTED_USERS = get_body_content(server_data)
            # print the user list
            print(f'UserList: {get_body_content(server_data)}')

        # close the connection if the user name is not available
        elif message == 'ERR_USERNAME_TAKEN':
            print('Disconnected: user name taken')
            print('Disconnecting')
            os._exit(os.EX_OK)

         # if server full disconnect
        elif message == 'ERR_SERVER_FULL':
            print('Disconnected: Server Maxed Out')
            print('Disconnecting')
            os._exit(os.EX_OK)
        # if invalid message was sent print the message sent by server
        elif message == 'ERR_INVALID_FORMAT':
            print(f'[SERVER] -> {message}')
        # if the password we have sent with the join request is incorrect then the conection is droped
        elif message == 'ERR_UNAUTHORIZED_ACCESS':
            print('Server Disconnected: Unauthorised Access Denied')
            print('Disconnecting')
            os._exit(os.EX_OK)
        message = ""


def main():
    connected = True
    t = threading.Thread(target=handle_server)
    t.start()
    USER_NAME = input('Please enter a user name: ')
    KEY = input('Please enther the password: ')
    packet = ('DATA', 'Join_Request', USER_NAME + "$;" + KEY)
    send_packet(packet, ADDRESS)

    while connected:
        # allow time for a server response
        time.sleep(0.5)
        print('/n*** please enter help if you need assistance ***/n')
        message = input().casefold()
        # request user list from the server
        if message == 'list':
            packet = ('DATA', 'Request_Users_Present', "")
            send_packet(packet, ADDRESS)
            time.sleep(0.1)
            # print(f'TESTING PACKET SENT ----->>>>{message}')

        if message == 'help':
            print(
                '- Invitation cards available:  \n\t * Birthday.txt\n\t * Christmas_party.txt\n\t * House_Warming.txt\n\t * Wedding.txt')
            print('\n')
            print(
                '- To request a user-list conected to the server please enter:  \n\t * list')
            print('\n')
            print(
                '- To send an invitation to one of the users please enter:  \n\t * invite <user_name> <file_name.txt>')
            print('\n')
            print(
                '- To send an invitation to more than one user please enter:  \n\t * invite <user_name_1> <user_name_2> <user_name_n> <file_name.txt>')
            print('\n')
            print(
                '- To send an invitation to all users connected please enter:  \n\t *  invite all <file_name.txt>')
            print('\n')
            print('- To disconect please enter:  \n\t *  quit')

        # close connection with the server
        if message == 'quit':
            packet = ('DATA', 'Disconnect', USER_NAME)
            send_packet(packet, ADDRESS)
            print('DISCONNECTING')
            connected = False
            # print(f'TESTING PACKET SENT ----->>>>{message}')
            os._exit(os.EX_OK)

        # send an invitation to selected users
        if message.split()[0] == 'invite':
            users = ""
            users_ = message.split()[1:-1]

            #  if the user whants to send the invitation to all the connected persons
            if users_[0] == 'all':
                global CONNECTED_USERS
                save_users = CONNECTED_USERS[0].split()
                no_of_users = len(save_users)
                for user in save_users:
                    users += f'{user}$;'
            # user whants to send the invitation to a particular person
            else:
                for user in users_:
                    users += f'{user}$;'
                    no_of_users = len(users_)

            # retrive the file name
            file_name = message.split()[-1]

            # open and read the file
            f = open(file_name, 'r')
            file_data = f.read(SIZE)
            # construct the body of the packet as: user$;file$name$;data
            body = "".join(users) + file_name + '$;' + file_data
            # add number of users to body
            body = f'{no_of_users}$;{body}'
            # add the body to the packet
            packet = ('DATA', 'Send_invite', body)
            # send packet
            send_packet(packet, ADDRESS)
            # close the file
            f.close()
            # print(f'TESTING PACKET SENT ----->>>>{message}')


if __name__ == '__main__':

    main()
