from ast import For
import binascii
from email import message
import socket
import threading
from urllib import response
import time
from queue import Queue, Empty
import random
import base64
import hashlib
from cryptography.fernet import Fernet

# from grpc import server
UDP_IP = '0.0.0.0'
PORT = 5056
ADDRESS = (UDP_IP, PORT)
FORMAT = 'utf-8'
SIZE = 14000
DISCONNECT_MESSAGE = 'Disconnect'
SERVER_NAME = "Ionut's Server"
MAX_CLIENTS = 10
TYPE_OF_MESSAGE = [
    'Join_Request',
    'Access_Granted',
    'Request_Users_Present',
    'Response_Users_Present',
    'Send_invite',
    'Forward_invite',
    'Disconnect',
    'Forward_invite_to_chat',
    'Invite_to_chat',
    'Chat',
    'ERR_SERVER_FULL',
    'ERR_USERNAME_TAKEN',
    'ERR_INVALID_FORMAT',
    'ERR_UNAUTHORIZED_ACCESS',
    'ACK',
    'START',
    'DATA',
    'END'

]

retransmit = 1
saved_message = ""
saved_packet_type = ""
saved_data = b''
reciving_strings = [
    'START',
    'END',
    'DATA',
]


recieving_type_queue = Queue()
recieving_seq_no_queue = Queue()
recieving_checksum_queue = Queue()


clients = {}

# generate encryption/decription key
password = 'networking'
password = password.encode(encoding='UTF-8')
key = hashlib.md5(password).hexdigest()
key = key.encode(encoding='UTF-8')
key_64 = base64.urlsafe_b64encode(key)


server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDRESS)

# -------------------METHODS---------------------------

# method to decript a packet


def decrypt_message(message):
    fernet = Fernet(key_64)
    decrypted_message = fernet.decrypt(message).decode('utf-8')
    return decrypted_message

# method to encript a packet


def encrypt_message(message):
    fernet = Fernet(key_64)
    encrypted_message = fernet.encrypt(message.encode('utf-8'))
    return encrypted_message

# method for sending a START packet


def send_start_packet(addr, seq_no):
    start_pkt = build_packet_formation(
        'START', "", seq_no, "")
    server.sendto(encrypt_message(start_pkt), addr)
    print(f'PACKET SENT [Ionut Server]----->>>>{start_pkt}')

# method for sending a DATA packet


def send_data_packet(packet, addr, seq_no):
    pack_type, mess_type, content = packet
    packet = build_packet_formation(pack_type, mess_type, seq_no, content)
    server.sendto(encrypt_message(packet), addr)
    print(f'PACKET SENT[Ionut Server] ----->>>>{packet}')

# method for sending a ACK packet


def send_ack_packet(seq_no, addr):
    send_ack_before_data = build_packet_formation('ACK', "", seq_no+1, "")
    server.sendto(encrypt_message(send_ack_before_data), addr)
    print(f'PACKET SENT[Ionut Server] ----->>>>{send_ack_before_data}')

# method for sending a END packet


def send_end_packet(addr, seq_no):
    send_ack_before_data = build_packet_formation('END', "", seq_no, "")
    server.sendto(encrypt_message(send_ack_before_data), addr)
    print(f'PACKET SENT[Ionut Server] ----->>>>{send_ack_before_data}')

#  method to send packets, this method will deliver packets as specified in the RFC


def send_packet(packet, addr):
    ack = True
    # create a random sequence number
    start_seq_no = random.randint(1, 20)
    while ack:
        # time.sleep(0.3)
        try:
            # wait for a response before retransmiting
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
                ack = False
                break

        except Empty:
            # send start packet
            send_start_packet(addr, start_seq_no)
            pass
    ack = True
    transmit = 0
    while ack:

        try:
            # wait for a response before retransmiting
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
                ack = False
                break
        except Empty:
            if transmit < retransmit:
                # send data packet
                send_data_packet(packet, addr, start_seq_no+1)
                # time.sleep(0.3)
                transmit += 1
            pass

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


def handle_reciving_data(server_data, packet_type, message, addr):
    # save packet's sequence number
    seq_no = get_seq_no(server_data)
    # we send an ack packet if packet type is START
    if packet_type == "START":
        send_ack_packet(seq_no, addr)
    # we send an ack packet if packet type is DATA and checksum is correct
    elif packet_type == "DATA" and recalculate_checksum(server_data) == get_checksum(server_data):
        send_ack_packet(seq_no, addr)
        global saved_message
        global saved_data
        global saved_packet_type
        # kepp a global copy of the message, packet type and data for later use
        saved_packet_type = packet_type
        saved_message = message
        saved_data = server_data
     # we send an ack packet if packet type is END
    elif packet_type == "END":
        send_ack_packet(seq_no, addr)
        return saved_message

# method to create a packet


def create_packet(packet_type, seq_no=0, body=""):
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    packet = (f'{packet_type}|{seq_no}|{body}|{checksum}')
    return packet


# -------------------PARSE PACKET---------------------------
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

# -------------------BUILD PACKET---------------------------

# method to build the packet body


def build_packet_formation(packet_type, message_type="", seq_no=0, content=""):
    len_msg = len(content)
    # if the type and content are missing it means that a START/ACK/END will be sent and it will have an empty body
    if message_type == "" and content == "":
        msg = ""
    else:
        msg = (f"{message_type}$;{len_msg}$;{content}")
    if message_type in TYPE_OF_MESSAGE or message_type == "":
        packet_formation = create_packet(packet_type, seq_no, msg)
    return packet_formation

# -------------------GET MESSAGE TYPE---------------------------


def get_message_type(packet):
    _, _, body, _ = parse_packet(decrypt_message(packet))
    message = body.split('$;')[0]
    return message

# -------------------GET MESSAGE LENGTH FROM BODY----------------


def get_body_length(packet):
    _, _, body, _ = parse_packet(decrypt_message(packet))
    message = body.split('$;')[1]
    return message

# -------------------GET BODY CONTENT--------------------------


def get_body_content(packet, len=None):

    _, _, body, _ = parse_packet(decrypt_message(packet))
    message = body.split('$;')[2]
    if len != None:
        message = body.split('$;')
        message = message[2:]
    return message

# calculate recieveing body checksum


def recalculate_checksum(data):
    _, _, body, _ = parse_packet(decrypt_message(data))
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    return checksum
# -------------------GET FILE--------------------------


def get_file(packet, lent):
    _, _, body, _ = parse_packet(decrypt_message(packet))
    message = body.split('$;')[lent+4]
    file_content = message.join('$;')
    return file_content[1:-1]

# -------------------GET USER LIST--------------------------


def get_user_list():
    user_list = []
    for user in clients.values():
        user_list.append(user)
    return user_list


# -------------------GET THE TYPE OF PACKET---------------------------


def get_packet_type(packet):
    packet_type, _, _, _ = parse_packet(decrypt_message(packet))
    return packet_type

# -------------------GET THE SEQUENCE NUMBER---------------------------


def get_seq_no(packet):
    _, seq_no, _, _ = parse_packet(decrypt_message(packet))
    return int(seq_no)

# -------------------GET THE CHECKSUM----------------------------------


def get_checksum(packet):
    _, _, _, checksum = parse_packet(decrypt_message(packet))
    return checksum


# -------------ANALISE DATA RECIEVED FROM CLIESNTS----------------------

def analise_data(data, addr):

    KEY = 'network'
    msg = get_message_type(data)
    pkt_type = get_packet_type(data)

    msg = handle_reciving_data(data, pkt_type, msg, addr)
    # check if the checksum is correct
    if recalculate_checksum(data) != get_checksum(data):
        msg = ""
    data = saved_data
    pkt_type = saved_packet_type

    # messenging part
    if msg == "Invite_to_chat":
        msg = "Forward_invite_to_chat"
        sending_user = clients.get(addr)
     
        # retrive the user names to forwoard the invitation
        send_to_user= get_body_content(data, 2)[0]
        for addres, client in clients.items():
            if client == send_to_user:
                address = addres
                packet = pkt_type, msg, ""
                send_packet(packet, address)
        msg = 'invitation_sent'

    if msg == 'Chat':
        send_to_user= get_body_content(data, 2)[0]
        user_message = get_body_content(data, 2)[1]
        for addres, client in clients.items():
            if client == send_to_user:
                address = addres
        packet = pkt_type, 'Chat', user_message
        send_packet(packet, address)

    # if message type is Disconect we pop the user name from the clients list
    if msg == 'Disconnect':
        print(f'Disconnected: {clients.get(addr)}')
        clients.pop(addr)
        print(f'Client list: {clients.values()}')
        return pkt_type, DISCONNECT_MESSAGE

    # if message is a join request and the KEY is incorrect refuse access
    if msg == 'Join_Request' and get_body_content(data, 2)[1] != KEY:
        msg = 'ERR_UNAUTHORIZED_ACCESS'
        print(f'Client list: {clients.values()}')
        # send back an error message
        return pkt_type, msg
    # if message is a join request and the user name already exists refuse access
    if msg == 'Join_Request' and get_body_content(data) in clients.values():
        msg = 'ERR_USERNAME_TAKEN'
        print(f'Client list: {clients.values()}')
        # send back an error message
        return pkt_type, msg

    # check if max no of clients is reached refuse access
    if msg == 'Join_Request' and len(clients) >= MAX_CLIENTS:
        msg = 'ERR_SERVER_FULL'
        print(f'Client list: {clients.values()}')
        # send back an error message
        return pkt_type, msg

    # if message is a join request and the KEY is correct allow access
    elif msg == 'Join_Request' and get_body_content(data, 2)[1] == KEY:

        user_name = get_body_content(data)
        # add the new user to the clients list
        clients.update({addr: user_name})
        print(f'Connected: {user_name}')
        # send bacl an access granted
        msg = 'Access_Granted'
    # if a user is requesting a list of present connected users we respond back with the list
    elif msg == 'Request_Users_Present':
        msg = 'Response_Users_Present'

    # if a user is sending an invitation card, we forward it to the users requested
    elif msg == 'Send_invite':
        # retrive the user name from clients dict
        sending_user = clients.get(addr)
        # calculate length of the whole message
        length = int(get_body_content(data, 2)[0])
        # retrive the user names to forwoard the invitation
        forward_to_users = get_body_content(data, 2)[1:1+length]
        # retrive file name
        file_name = get_body_content(data, 2)[length+1]
        # send the invitation card to all the users
        for addres, client in clients.items():
            if client in forward_to_users:
                msg = 'Forward_invite'
                file = sending_user + '$;' + file_name + \
                    '$;' + get_file(data, length)
                forward = pkt_type, msg, file

                send_packet(forward, addres)
        print(f'FORWOARD TO USERS {forward_to_users}')
        msg = 'invitation_sent'

    return pkt_type, msg


# -------------------HANDLE CLIENT--------------------------
def handle_client(data, addr):
    packet_type, response = analise_data(data, addr)
    connected = True
    while connected:
        # checks the type of message recieved
        message = response
        packet_type = packet_type

        # if an invitation has been sent we brake out of the loop
        if message == 'invitation_sent':
            connected = False
        if message == DISCONNECT_MESSAGE:

            # print(f'[USERS LIST] after disconnect -> {clients}')
            connected = False

        # send a user list when a client asks for it
        if message == 'Response_Users_Present':
            u_list = ''.join(str(user)+' ' for user in get_user_list())
            message = packet_type, message, u_list
            send_packet(message, addr)

            connected = False
        # allow access to user
        if message == 'Access_Granted':
            message = packet_type, message, ""
            send_packet(message, addr)

            connected = False
        # send error message
        if message == 'ERR_USERNAME_TAKEN':
            message = packet_type, message, ""
            send_packet(message, addr)
            connected = False
        # send error message
        if message == 'ERR_SERVER_FULL':
            message = packet_type, message, ""
            send_packet(message, addr)
            connected = False
        # send error message
        if message == 'ERR_UNAUTHORIZED_ACCESS':
            message = packet_type, message, ""
            send_packet(message, addr)
            connected = False
        connected = False


# -------------------MAIN FUNCTION--------------------------
def main():
    print('[STARTING SERVER]...')
    print(f"[LISTENING] on IP:{UDP_IP}, PORT: {PORT}")

    while True:
        data, addr = server.recvfrom(SIZE)
        #  code used to test for paket loss
        
        # rand = random.randint(0, 7)
        # print("random number: ", rand)
        # if (rand < 4):
        #     print("Packet Force Lost")
        #     continue
        # print("cont random: ", rand)
        
        # POPULATE QUEUES
        recieving_type_queue.put(get_packet_type(data))
        recieving_checksum_queue.put(get_checksum(data))
        recieving_seq_no_queue.put(get_seq_no(data))
        print(
            f'PACKET RECIEVED[Ionut Server] <<<<<----- {decrypt_message(data)} ')

        # INITIALISE AND START THREAD THAT HANDLES THE MESSAGES RECEIVED FROM CLIENTS
        thread = threading.Thread(target=handle_client, args=(data, addr))
        thread.start()
        time.sleep(0.1)


# -------------------EXECUTES FIRST--------------------------
if __name__ == '__main__':
    main()
