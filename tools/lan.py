"""Opt-in, paired private-WLAN access. No public-hosting mode."""
import ipaddress
import secrets
import socket
import subprocess
import sys
from http.cookies import SimpleCookie

COOKIE = 'h4_lan'


def private_address(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and any(address in ipaddress.ip_network(net) for net in
                                       ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))


def discover_address():
    if sys.platform == 'darwin':
        for interface in ('en0','en1'):
            try:
                result = subprocess.run(['ipconfig','getifaddr',interface], capture_output=True, text=True, timeout=2)
                value = result.stdout.strip()
                if private_address(value):
                    return value
            except (OSError, subprocess.TimeoutExpired):
                pass
    try:
        # UDP route selection only: connect does not send a packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.connect(('192.0.2.1', 9))
            value = connection.getsockname()[0]
            if private_address(value):
                return value
    except OSError:
        pass
    return None


def loopback(client):
    try:
        return ipaddress.ip_address(client[0]).is_loopback
    except ValueError:
        return False


def access_key():
    return secrets.token_urlsafe(32)


def matches(value, key):
    return bool(value and key) and secrets.compare_digest(value.encode(), key.encode())


def authorized(headers, client, key):
    if not key or loopback(client):
        return True
    try:
        cookies = SimpleCookie()
        cookies.load(headers.get('Cookie',''))
        return matches(cookies[COOKIE].value, key) if COOKIE in cookies else False
    except Exception:
        return False


def cookie(key):
    result = SimpleCookie()
    result[COOKIE] = key
    result[COOKIE]['path'] = '/'
    result[COOKIE]['httponly'] = True
    result[COOKIE]['samesite'] = 'Strict'
    return result.output(header='').strip()
