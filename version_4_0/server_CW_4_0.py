from ast import For
import binascii
from email import message
import socket
import threading
from urllib import response
import time
from queue import Queue, Empty
import random
# from grpc import server
UDP_IP = '0.0.0.0'
PORT = 5056
ADDRESS = (UDP_IP, PORT)
FORMAT = 'utf-8'
SIZE = 2048
DISCONNECT_MESSAGE = 'Disconnect'
SERVER_NAME = "Ionut's Server"
MAX_CLIENTS = 4
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
    'ACK',
    'START',
    'DATA',
    'END'

]

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


server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDRESS)

# -------------------METHODS---------------------------


def send_start_packet(addr, seq_no):
    start_pkt = build_packet_formation(
        'START', "", seq_no, "")
    server.sendto(start_pkt.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{start_pkt}')
    time.sleep(0.5)


def send_data_packet(packet, addr, seq_no):
    pack_type, mess_type, content = packet
    packet = build_packet_formation(pack_type, mess_type, seq_no, content)
    server.sendto(packet.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{packet}')


def send_ack_packet(seq_no, addr):
    send_ack_before_data = build_packet_formation('ACK', "", seq_no+1, "")
    server.sendto(send_ack_before_data.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{send_ack_before_data}')


def send_end_packet(addr, seq_no):
    send_ack_before_data = build_packet_formation('END', "", seq_no, "")
    server.sendto(send_ack_before_data.encode(FORMAT), addr)
    print(f'TESTING PACKET SENT ----->>>>{send_ack_before_data}')


def send_packet(packet, addr):
    ack = True
    start_seq_no = random.randint(1, 20)
    while ack:
        send_start_packet(addr, start_seq_no)
        try:
            if recieving_type_queue.get(timeout=0.3) == 'ACK':
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


def handle_reciving_data(server_data, packet_type, message, addr):
    seq_no = get_seq_no(server_data)
    if packet_type == "START":
        send_ack_packet(seq_no, addr)
    elif packet_type == "DATA":
        send_ack_packet(seq_no, addr)
        global saved_message
        global saved_data
        global saved_packet_type
        saved_packet_type = packet_type
        saved_message = message
        saved_data = server_data
    elif packet_type == "END":
        send_ack_packet(seq_no, addr)
        return saved_message


def create_packet(packet_type, seq_no=0, body=""):
    checksum = str(binascii.crc32(body.encode(FORMAT)) & 0xFFFFFFFF)
    packet = (f'{packet_type}|{seq_no}|{body}|{checksum}')
    return packet


# -------------------PARSE PACKET---------------------------
def parse_packet(message):
    pieces = message.split("|")
    packet_type, seq_no = pieces[:2]
    body = pieces[2:-1]
    body = "|".join(body)
    checksum = pieces[-1]

    return packet_type, seq_no, body, checksum

# -------------------BUILD PACKET---------------------------


def build_packet_formation(packet_type, message_type="", seq_no=0, content=""):
    len_msg = len(content)
    if message_type == "" and content == "":
        msg = ""
    else:
        msg = (f"{message_type}$;{len_msg}$;{content}")
    if message_type in TYPE_OF_MESSAGE or message_type == "":
        packet_formation = create_packet(packet_type, seq_no, msg)
    return packet_formation

# -------------------GET MESSAGE TYPE---------------------------


def get_message_type(packet):
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[0]
    return message

# -------------------GET MESSAGE LENGTH FROM BODY----------------


def get_body_length(packet):
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[1]
    return message

# -------------------GET BODY CONTENT--------------------------


def get_body_content(packet, len=None):

    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[2]
    if len != None:
        message = body.split('$;')
        message = message[2:]
    return message

# -------------------GET FILE--------------------------


def get_file(packet, lent):
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[lent+4]
    file_content = message.join('$;')

    return file_content[1:]

# -------------------GET USER LIST--------------------------


def get_user_list():
    user_list = []
    for user in clients.values():
        user_list.append(user)
    return user_list


# -------------------GET THE TYPE OF PACKET---------------------------


def get_packet_type(packet):
    packet_type, _, _, _ = parse_packet(packet.decode(FORMAT))
    return packet_type

# -------------------GET THE SEQUENCE NUMBER---------------------------


def get_seq_no(packet):
    _, seq_no, _, _ = parse_packet(packet.decode(FORMAT))
    return int(seq_no)

# -------------------GET THE CHECKSUM----------------------------------


def get_checksum(packet):
    _, _, _, checksum = parse_packet(packet.decode(FORMAT))
    return checksum

# -------------------METHODS FINISHED----------------------------------


# -------------ANALISE DATA RECIEVED FROM CLIESNTS----------------------

def analise_data(data, addr):

    msg = get_message_type(data)
    pkt_type = get_packet_type(data)

    msg = handle_reciving_data(data, pkt_type, msg, addr)
    print(f'------------------------------------------------ message is {msg}')
    data = saved_data
    pkt_type = saved_packet_type

    if msg == 'Disconnect':
        print(f'{clients.get(addr)}  DISCONNECTED!')
        clients.pop(addr)
        return pkt_type, DISCONNECT_MESSAGE

    # check if max no of clients is reached
    if msg == 'Join_Request' and len(clients) >= MAX_CLIENTS:
        msg = 'ERR_SERVER_FULL'
        return pkt_type, msg

    elif msg == 'Join_Request':
        user_name = get_body_content(data)
        clients.update({addr: user_name})
        print(f'[USERS LIST] -> {clients}')
        msg = 'Access_Granted'

    elif msg == 'Request_Users_Present':
        msg = 'Response_Users_Present'

    elif msg == 'Send_invite':

        sending_user = clients.get(addr)
        length = int(get_body_content(data, 2)[0])
        forward_to_users = get_body_content(data, 2)[1:1+length]
        file_name = get_body_content(data, 2)[length+1]
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

            print(f'[USERS LIST] after disconnect -> {clients}')
            connected = False

        # send a user list when a client asks for it
        if message == 'Response_Users_Present':
            u_list = ''.join(str(user)+' ' for user in get_user_list())
            message = packet_type, message, u_list
            send_packet(message, addr)

            connected = False

        if message == 'Access_Granted':
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

        # POPULATE QUEUES
        recieving_type_queue.put(get_packet_type(data))
        recieving_checksum_queue.put(get_checksum(data))
        recieving_seq_no_queue.put(get_seq_no(data))
        print(f'TESTING DATA RECIEVED <<<<<----- {data.decode(FORMAT)} ')

        # INITIALISE AND START THREAD THAT HANDLES THE MESSAGES RECEIVED FROM CLIENTS
        thread = threading.Thread(target=handle_client, args=(data, addr))
        thread.start()
        time.sleep(0.1)


# -------------------EXECUTES FIRST--------------------------
if __name__ == '__main__':
    main()
