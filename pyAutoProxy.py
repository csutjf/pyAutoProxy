import argparse
import itertools
import operator
import os
import random
import sys
import threading
import typing
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer


def fetch(func):
    url = func()

    def _fetch():
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
        }
        request = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(request)
        content = response.read()
        content = content.decode('utf-8')
        return content

    return _fetch

def read(func):
    filename = func()

    def _read():
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, filename)
        with open(path, mode='r', encoding='utf-8') as f:
            return f.read()

    return _read

def write(func):
    filename = func()

    def _write(content):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, filename)
        with open(path, mode='w', encoding='utf-8') as f:
            f.write(content)

    return _write

@fetch
def fetch_domains():
    return 'https://github.com/zungmou/pyAutoProxy/raw/master/domains.txt'

@read
def read_domains():
    return 'domains.txt'

@write
def write_domains(*args, **kwargs):
    return 'domains.txt'

@read
def read_proxies():
    return 'proxies.txt'

@write
def write_proxies(*args, **kwargs):
    return 'proxies.txt'

def read_else_write(filename, default, only_write=False):
    current_dir = os.path.dirname(__file__)
    path = os.path.join(current_dir, filename)

    try:
        if not only_write:
            with open(path, mode='r', encoding='utf-8') as f:
                return f.read()
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        with open(path, mode='w', encoding='utf-8') as f:
            default = default() if callable(default) else default
            f.write(default)
            return default


class ServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        randint = random.randrange(100000, 999999)
        filename = f'{randint}.pac'
        self.send_response(200)
        self.send_header('Content-type', 'application/x-ns-proxy-autoconfig')
        self.send_header('Content-Disposition',
                         f'inline; filename="{filename}"')
        self.end_headers()
        self.wfile.write(self.merage().encode())

    def log_message(self, format, *args):
        return

    def merage(self):
        def read_else_fetch(readfunc, fetchfunc, writefunc, fetch_fail_default):
            try:
                content = readfunc()
            except FileNotFoundError:
                try:
                    content = fetchfunc()
                except urllib.error.HTTPError:
                    content = fetch_fail_default
                finally:
                    writefunc(content)
            finally:
                return content

        template = \
r"""
var FindProxyForURL = function (init, profiles) {
    return function (url, host) {
        "use strict";
        var result = init, scheme = url.substr(0, url.indexOf(":"));
        do {
            result = profiles[result];
            if (typeof result === "function") result = result(url, host, scheme);
        } while (typeof result !== "string" || result.charCodeAt(0) === 43);
        return result;
    };
}("+Auto", {
    "+Auto": function (url, host, scheme) {
        "use strict";
        /*{PROXY-RULES}*/
        return "DIRECT";
    },
    "+PACHost": function (url, host, scheme) {
        "use strict";
        if (/^127\.0\.0\.1$/.test(host) || /^::1$/.test(host) || /^localhost$/.test(host)) return "DIRECT";
        return "/*{PROXY-DEFINES}*/";
    }
});
"""
        domains = read_else_fetch(read_domains, fetch_domains, write_domains, '')
        domains = str.split(domains, '\n')
        domains = map(str.strip, domains)
        domains = filter(operator.truth, domains)
        domains = filter(lambda x: not str.startswith(x, '#'), domains)
        domains = list(sorted(set(domains)))
        write_domains('\n'.join(domains))

        try:
            proxies = read_proxies()
        except FileNotFoundError:
            while True:
                flash()
                proxies = input('Enter a Proxy, e.g.(PROXY 127.0.0.1:8118; SOCKS5 127.0.0.1:1080):')
                proxies = str.strip(proxies)
                if proxies:
                    write_proxies(proxies)
                    break
        finally:
            proxies = str.split(proxies, ';')
            proxies = map(str.strip, proxies)
            proxies = filter(operator.truth, proxies)
            proxies = list(proxies)

        rules = map(lambda x: str.replace(x, '.', r'\.'), domains)
        rules = map(
            lambda x: f'if (/(?:^|\\.){x}$/.test(host)) return "+PACHost";', rules)
        rules = '\n'.join(rules)
        template = template.replace('/*{PROXY-RULES}*/', rules)
        template = template.replace('/*{PROXY-DEFINES}*/', ';'.join(proxies))
        return template

def flash():
    try:
        import ctypes
        ctypes.windll.user32.FlashWindow(ctypes.windll.kernel32.GetConsoleWindow(), True)
    except ImportError:
        pass

def run(address: str, port: int):
    print('PAC host at http://127.0.0.1:8000/')
    server_address = ('127.0.0.1', 8000)
    httpd = HTTPServer(server_address, ServerHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.setDaemon(True)
    thread.start()
    thread.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--address', default='127.0.0.1')
    parser.add_argument('--port', type=int, default='8080')
    args = parser.parse_args()
    run(args.address, args.port)


if __name__ == "__main__":
    main()
