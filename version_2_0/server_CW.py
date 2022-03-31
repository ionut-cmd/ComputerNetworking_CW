from ast import For
import binascii
from email import message
import socket
import threading
from urllib import response
import time


# from grpc import server
UDP_IP = '0.0.0.0'
PORT = 5056
ADDRESS = (UDP_IP, PORT)
FORMAT = 'utf-8'
SIZE = 2048
DISCONNECT_MESSAGE = 'DISCONNECT!'
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
    'DISCONNECT!'

]

clients = {}


server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDRESS)

# -------------------METHODS---------------------------


def create_packet(packet_type="data", seq_no=0, body=""):
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


def build_packet_formation(message_type, content=None):
    len_msg = len(content)
    msg = (f"{message_type}$;{len_msg}$;{content}")
    if message_type in TYPE_OF_MESSAGE:
        packet_formation = create_packet("data", 0, msg)
        print(f'TESTING PACKET SENT ----->>>>{packet_formation}')
    return packet_formation

# -------------------GET MESSAGE TYPE---------------------------


def get_message_type(packet):
    _, _, body, _ = parse_packet(packet.decode(FORMAT))
    message = body.split('$;')[0]
    return message

# -------------------GET MESSAGE LENGTH FROM BODY--------------------------


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


# -------------------METHODS FINISHED---------------------------


# -------------------ANALISE DATA RECIEVED FROM CLIESNTS--------------------------
def analise_data(data, addr):
    # msg = data.decode(FORMAT)
    msg = get_message_type(data)
    if msg == 'DISCONNECT!':
        print(f'{clients.get(addr)}  DISCONNECTED!')
        clients.pop(addr)
        # //TODO DO not send a message back
        return DISCONNECT_MESSAGE.encode(FORMAT)

    # check if max no of clients is reached
    if msg == 'Join_Request' and len(clients) >= MAX_CLIENTS:
        msg = 'ERR_SERVER_FULL'
        return msg.encode(FORMAT)

    elif msg == 'Join_Request':
        user_name = get_body_content(data)
        clients.update({addr: user_name})
        # user_names.append(user_name)
        print(f'[USERS LIST] -> {clients}')
        msg = 'Access_Granted'

    elif msg == 'Request_Users_Present':
        msg = 'Response_Users_Present'
        # print(msg)

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
                forward = build_packet_formation(msg, file)
                server.sendto(forward.encode(FORMAT), (addres[0], addres[1]))

        print(f'FORWOARD TO USERS {forward_to_users}')
        msg = 'invitation_sent'
    else:
        msg = 'ERR_INVALID_FORMAT'

    return msg.encode(FORMAT)


# -------------------HANDLE CLIENT--------------------------
def handle_client(data, addr):
    response = analise_data(data, addr)
    connected = True
    while connected:
        message = response.decode(FORMAT)
        if message == 'invitation_sent':
            connected = False
        if message == DISCONNECT_MESSAGE:

            print(f'[USERS LIST] after disconnect -> {clients}')
            connected = False

        if message == 'Response_Users_Present':
            u_list = ''.join(str(user)+' ' for user in get_user_list())
            message = build_packet_formation(message, u_list)
            server.sendto(message.encode(FORMAT), (addr[0], addr[1]))
            connected = False
        if connected:
            message = build_packet_formation(message, "")
            server.sendto(message.encode(FORMAT), (addr[0], addr[1]))
        connected = False


# -------------------MAIN FUNCTION--------------------------
def main():
    print('[STARTING SERVER]...')
    print(f"[LISTENING] on IP:{UDP_IP}, PORT: {PORT}")

    while True:
        data, addr = server.recvfrom(SIZE)
        print(f'TESTING DATA RECIEVED ----->>>>{data.decode(FORMAT)} ')

        thread = threading.Thread(target=handle_client, args=(data, addr))
        thread.start()
        time.sleep(0.1)


# -------------------EXECUTES FIRST--------------------------
if __name__ == '__main__':
    main()
