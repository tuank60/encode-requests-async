import logging
import urllib3.connectionpool as connectionpool

import requests_async.connection as connection

log = logging.getLogger(__name__)

_Default = object()


class HTTPConnectionPool(connectionpool.HTTPConnectionPool):
    ConnectionCls = connection.HTTPConnection

    def __enter__(self):
        raise NotImplementedError("Use 'async with ConnectionPool', instead of 'with ConnectionPool'")

    def __aenter__(self):
        return self

    def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        # Return False to re-raise any potential exceptions
        return False

    def _new_conn(self):
        conn = self.ConnectionCls(host=self.host, port=self.port,
                                  timeout=self.timeout.connect_timeout,
                                  strict=self.strict, **self.conn_kw)
        return conn

    def _get_conn(self, timeout=None):
        return self._new_conn()

    async def _make_request(self, conn, method, url, timeout=_Default, chunked=False,
                            **httplib_request_kw):
        await conn.request(method, url, **httplib_request_kw)

        httplib_response = await conn.getresponse()

        return httplib_response

    def close(self):
        raise NotImplementedError("Method is currently not available")

    async def urlopen(self, method, url, body=None, headers=None, retries=None,
                      redirect=True, assert_same_host=True, timeout=_Default,
                      pool_timeout=None, release_conn=None, chunked=False,
                      body_pos=None, **response_kw):
        conn = self._get_conn(timeout=pool_timeout)

        response = await self._make_request(conn, method, url,
                                            timeout=None,
                                            body=body, headers=headers,
                                            chunked=chunked)

        return response

    async def request(self, method, url, fields=None, headers=None, **urlopen_kw):
        raise NotImplementedError("Method is currently not available")

    async def request_encode_url(self, method, url, fields=None, headers=None,
                                 **urlopen_kw):
        raise NotImplementedError("Method is currently not available")

    async def request_encode_body(self, method, url, fields=None, headers=None,
                                  encode_multipart=True, multipart_boundary=None,
                                  **urlopen_kw):
        raise NotImplementedError("Method is currently not available")