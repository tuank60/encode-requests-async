import asyncio
import ssl
import requests
import h11
import io
import urllib3
import urllib3.packages.six.moves.http_client as http_client
import http.client as httpclient
import urllib3.util.timeout as timeout
import urllib


def no_verify():
    # ssl.create_default_context()
    sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    sslcontext.options |= ssl.OP_NO_SSLv2
    sslcontext.options |= ssl.OP_NO_SSLv3
    sslcontext.options |= ssl.OP_NO_COMPRESSION
    sslcontext.set_default_verify_paths()
    return sslcontext


port_by_scheme = {
    'http': 80,
    'https': 443,
}


class HTTPConnection(http_client.HTTPConnection):

    def __init__(self, *args, **kw):
        kw.pop('strict', None)

        super().__init__(*args, **kw)

        self.conn = None
        self.reader = None
        self.writer = None

        self._buffer = None

    def set_tunnel(self, host, port=None, headers=None):
        raise NotImplementedError("Method is currently not available")

    @property
    def host(self):
        return self._dns_host.rstrip('.')

    @host.setter
    def host(self, value):
        self._dns_host = value

    async def _new_conn(self):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._dns_host, self.port),
                self.timeout if self.timeout != timeout.Timeout.DEFAULT_TIMEOUT else None
            )

            self.conn = h11.Connection(our_role=h11.CLIENT)

        except asyncio.TimeoutError:
            raise requests.ConnectTimeout()

        return reader, writer

    def _prepare_conn(self, conn):
        self.reader, self.writer = conn

    async def connect(self):
        conn = await self._new_conn()
        self._prepare_conn(conn)

    async def close(self):
        self.writer.close()
        if hasattr(self.writer, "wait_closed"):
            await self.writer.wait_closed()

    async def send(self, data):
        if self.conn is None:
            await self.connect()
        data = self.conn.send(data)
        self.writer.write(data)

    def putrequest(self, method, url, skip_host=False,
                   skip_accept_encoding=False):
        self._buffer = {'method': method, 'target': url, 'headers': list()}

        if self._http_vsn == 11:
            if not skip_host:
                netloc = ''
                if url.startswith('http'):
                    nil, netloc, nil, nil, nil = urllib.parse.urlsplit(url)

                if netloc:
                    try:
                        netloc_enc = netloc.encode("ascii")
                    except UnicodeEncodeError:
                        netloc_enc = netloc.encode("idna")
                    self.putheader('Host', netloc_enc)
                else:
                    if self._tunnel_host:
                        host = self._tunnel_host
                        port = self._tunnel_port
                    else:
                        host = self.host
                        port = self.port

                    try:
                        host_enc = host.encode("ascii")
                    except UnicodeEncodeError:
                        host_enc = host.encode("idna")

                    # As per RFC 273, IPv6 address should be wrapped with []
                    # when used as Host header

                    if host.find(':') >= 0:
                        host_enc = b'[' + host_enc + b']'

                    if port == self.default_port:
                        self.putheader('Host', host_enc)
                    else:
                        host_enc = host_enc.decode("ascii")
                        self.putheader('Host', "%s:%s" % (host_enc, port))

            if not skip_accept_encoding:
                self.putheader('Accept-Encoding', 'identity')

    def putheader(self, header, *values):
        if hasattr(header, 'encode'):
            header = header.encode('ascii')

        if not http_client._is_legal_header_name(header):
            raise ValueError('Invalid header name %r' % (header,))

        values = list(values)
        for i, one_value in enumerate(values):
            if hasattr(one_value, 'encode'):
                values[i] = one_value.encode('latin-1')
            elif isinstance(one_value, int):
                values[i] = str(one_value).encode('ascii')

            if http_client._is_illegal_header_value(values[i]):
                raise ValueError('Invalid header value %r' % (values[i],))

        value = b'\r\n\t'.join(values)

        self._buffer['headers'].append((header, value))

    async def endheaders(self, message_body=None, *, encode_chunked=False):
        data = h11.Request(**self._buffer)
        await self.send(data=data)

        if message_body:
            data = h11.Data(data=message_body)
            await self.send(data=data)

        data = h11.EndOfMessage()
        await self.send(data=data)

    def request_chunked(self, method, url, body=None, headers=None):
        raise NotImplementedError("Method is currently not available")

    async def request(self, method, url, body=None, headers={}, *, encode_chunked=False):
        header_names = frozenset(k.lower() for k in headers)
        skips = {}
        if 'host' in header_names:
            skips['skip_host'] = 1
        if 'accept-encoding' in header_names:
            skips['skip_accept_encoding'] = 1

        self.putrequest(method=method, url=url)

        for key, value in headers.items():
            self.putheader(key, value)

        if body:
            body = (
                httpclient._encode(body) if isinstance(body, str) else body
            )

        await self.endheaders(message_body=body, encode_chunked=encode_chunked)

    async def getresponse(self):
        status_code = 0
        headers = []
        reason = b""
        buffer = io.BytesIO()

        while True:
            event = self.conn.next_event()
            event_type = type(event)

            if event_type is h11.NEED_DATA:
                try:
                    data = await asyncio.wait_for(self.reader.read(2048), None)
                except asyncio.TimeoutError:
                    raise requests.ReadTimeout()
                self.conn.receive_data(data)

            elif event_type is h11.Response:
                status_code = event.status_code
                headers = [
                    (key.decode(), value.decode()) for key, value in event.headers
                ]
                reason = event.reason

            elif event_type is h11.Data:
                buffer.write(event.data)

            elif event_type is h11.EndOfMessage:
                buffer.seek(0)
                break

        self.writer.close()
        if hasattr(self.writer, "wait_closed"):
            await self.writer.wait_closed()

        resp = urllib3.HTTPResponse(
            body=buffer,
            headers=headers,
            status=status_code,
            reason=reason,
            preload_content=False,
        )

        return resp


class HTTPSConnection(HTTPConnection):

    async def _new_conn(self):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=self._dns_host, port=self.port, ssl=no_verify()),
                self.timeout if self.timeout != timeout.Timeout.DEFAULT_TIMEOUT else None
            )

            self.conn = h11.Connection(our_role=h11.CLIENT)

        except asyncio.TimeoutError:
            raise requests.ConnectTimeout()

        return reader, writer
