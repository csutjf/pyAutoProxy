import argparse
import operator
import os
import sys
import random
import threading
import typing
import subprocess
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


def resource(func):
    path = func()

    def _resource():
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(
            os.path.abspath(__file__)))
        return os.path.join(base_path, path)
    return _resource


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


@resource
def get_privoxy_path():
    return 'privoxy.exe'


@read
def read_privoxy_config():
    return 'config.txt'


@write
def write_privoxy_config(*args, **kwargs):
    return 'config.txt'


class ServerHandler(BaseHTTPRequestHandler):
    __script = r"""
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

    def log_message(self, format, *args):
        return

    def get_domains(self):
        try:
            domains = read_domains()
        except FileNotFoundError:
            try:
                domains = fetch_domains()
            except urllib.error.HTTPError:
                domains = ''
            finally:
                write_domains(domains)
        finally:
            domains = str.split(domains, '\n')
            domains = map(str.strip, domains)
            domains = filter(operator.truth, domains)
            domains = filter(lambda x: not str.startswith(x, '#'), domains)
            domains = list(sorted(set(domains)))
            write_domains('\n'.join(domains))
            return domains

    def get_proxies(self):
        proxies = read_proxies()
        proxies = str.split(proxies, ';')
        proxies = map(str.strip, proxies)
        proxies = filter(operator.truth, proxies)
        proxies = tuple(proxies)
        return proxies

    def get_rules(self):
        domains = self.get_domains()
        domains = map(lambda x: str.replace(x, '.', r'\.'), domains)
        domains = map(lambda x: f'if (/(?:^|\\.){x}$/.test(host)) return "+PACHost";', domains)
        rules = '\n'.join(domains)
        return rules

    def do_GET(self):
        response_status = 200
        response_data = None
        content_type = 'application/x-ns-proxy-autoconfig'
        content_disposition = f'attachment; filename="{random.randrange(100000, 999999)}.pac"'

        try:
            try:
                proxies = self.get_proxies()
            except FileNotFoundError:
                message = 'The proxy needs to be defined in the proxies.txt file, e.g.: PROXY 127.0.0.1:8118; SOCKS5 127.0.0.1:1080'
                response_status = 500
                content_type = 'text/plain'
                content_disposition = 'inline'
                response_data = message.encode()
                return

            rules = self.get_rules()
            response_data = self.__script.replace('/*{PROXY-RULES}*/', rules)
            response_data = response_data.replace('/*{PROXY-DEFINES}*/', ';'.join(proxies))
            response_data = response_data.encode()
        finally:
            self.send_response(response_status)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Disposition', content_disposition)
            self.end_headers()
            self.wfile.write(response_data)


def parseargs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--address', default='127.0.0.1')
    parser.add_argument('--port', type=int, default='8000')
    parser.add_argument('--privoxy-address', default='127.0.0.1')
    parser.add_argument('--privoxy-port', type=int, default='8118')
    parser.add_argument('--socks5-proxy-address', default='127.0.0.1')
    parser.add_argument('--socks5-proxy-port', type=int, default='10808')
    return parser.parse_args()


def start_privoxy(listen: typing.Tuple[str, int], forward: typing.Tuple[str, int]):
    try:
        read_privoxy_config()
    except FileNotFoundError:
        write_privoxy_config('\n'.join((
            'log-messages 1',
            'debug 1',
            f'listen-address {listen[0]}:{listen[1]}',
            f'forward-socks5 / {forward[0]}:{forward[1]} .'
        )))
    return subprocess.Popen([], executable=get_privoxy_path())


def run(address: str, port: int):
    server_address = (address, port)
    httpd = HTTPServer(server_address, ServerHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()


def main():
    args = parseargs()

    listen = args.privoxy_address, args.privoxy_port
    forward = args.socks5_proxy_address, args.socks5_proxy_port
    privoxy = start_privoxy(listen=listen, forward=forward)
    del listen, forward

    run(args.address, args.port)
    print(f'PAC host at http://{args.address}:{args.port}/')

    while True:
        try:
            input('Press CTRL+C to quit\n')
        except KeyboardInterrupt:
            privoxy.terminate()
            break


if __name__ == "__main__":
    main()
