"""
Local DNS server for interception of specific Apple endpoints.
- Intercepts configured hostnames and resolves them to the local device IP.
- Falls back to forwarding to upstream DNS for other queries.

Usage:
    from scripts.dns_server import start_dns_server, stop_dns_server
    srv = start_dns_server(intercept_hosts=['albert.apple.com','gs.apple.com','captive.apple.com'])
    ...
    stop_dns_server(srv)

Notes:
- Listening on port 53 requires elevated privileges. For testing you can run on a high port
  and update the system's DNS settings manually.
- This script uses dnslib (add to requirements.txt).
"""
from __future__ import annotations
import socket
import threading
import logging
from dnslib.server import DNSServer, DNSHandler, BaseResolver
from dnslib import DNSRecord, RR, A, QTYPE

log = logging.getLogger('jarvis.dns')


def _get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


class InterceptResolver(BaseResolver):
    def __init__(self, intercept_hosts=None, target_ip=None, upstream='8.8.8.8'):
        self.intercept_hosts = set(h.lower().rstrip('.') for h in (intercept_hosts or []))
        self.target_ip = target_ip or _get_local_ip()
        self.upstream = upstream

    def resolve(self, request, handler):
        qname = str(request.q.qname).rstrip('.')
        qn = qname.lower()
        reply = request.reply()
        if qn in self.intercept_hosts:
            # Return A record pointing to local server IP
            reply.add_answer(RR(qname, QTYPE.A, rdata=A(self.target_ip), ttl=60))
            log.debug('Intercepted DNS %s -> %s', qname, self.target_ip)
            return reply
        # else forward: simple UDP query to upstream
        try:
            upstream_resp = DNSRecord.question(qname).send(self.upstream, 53, tcp=False, timeout=2)
            return DNSRecord.parse(upstream_resp)
        except Exception as e:
            log.exception('DNS forward failed: %s', e)
            return reply


def start_dns_server(intercept_hosts=None, listen='0.0.0.0', port=53, target_ip=None, upstream='8.8.8.8'):
    resolver = InterceptResolver(intercept_hosts=intercept_hosts, target_ip=target_ip, upstream=upstream)
    server = DNSServer(resolver, port=port, address=listen, logger=log)

    thread = threading.Thread(target=server.start_thread, daemon=True)
    thread.start()
    log.info('DNS server started on %s:%d (intercept: %s -> %s)', listen, port, intercept_hosts, resolver.target_ip)
    return server


def stop_dns_server(server: DNSServer):
    try:
        server.stop()
    except Exception:
        pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    hs = ['albert.apple.com', 'gs.apple.com', 'captive.apple.com']
    srv = start_dns_server(intercept_hosts=hs, port=5353)
    print('DNS interception running (port 5353) for test; CTRL-C to stop')
    try:
        while True:
            pass
    except KeyboardInterrupt:
        stop_dns_server(srv)
        print('stopped')
