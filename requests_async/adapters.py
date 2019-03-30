import ssl
from urllib.parse import urlparse
from urllib3.util.retry import Retry
from urllib3.util import Timeout as TimeoutSauce

from urllib3.exceptions import LocationValueError

import requests_async.exceptions as exceptions
import requests_async.poolmanager as poolmanager

import requests

DEFAULT_POOLBLOCK = False
DEFAULT_POOLSIZE = 1
DEFAULT_RETRIES = 0
DEFAULT_POOL_TIMEOUT = None


def no_verify():
    # ssl.create_default_context()
    sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    sslcontext.options |= ssl.OP_NO_SSLv2
    sslcontext.options |= ssl.OP_NO_SSLv3
    sslcontext.options |= ssl.OP_NO_COMPRESSION
    sslcontext.set_default_verify_paths()
    return sslcontext


class HTTPAdapter(requests.adapters.HTTPAdapter):

    def __init__(self, pool_connections=DEFAULT_POOLSIZE,
                 pool_maxsize=DEFAULT_POOLSIZE, max_retries=DEFAULT_RETRIES,
                 pool_block=DEFAULT_POOLBLOCK):
        if max_retries == DEFAULT_RETRIES:
            self.max_retries = Retry(0, read=False)
        else:
            self.max_retries = Retry.from_int(max_retries)
        self.config = {}
        self.proxy_manager = {}

        super(HTTPAdapter, self).__init__()

        self._pool_connections = pool_connections
        self._pool_maxsize = pool_maxsize
        self._pool_block = pool_block

        self.init_poolmanager(pool_connections, pool_maxsize, block=pool_block)

    def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK, **pool_kwargs):
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block

        self.poolmanager = poolmanager.PoolManager(num_pools=connections, maxsize=maxsize,
                                                   block=block, strict=True, **pool_kwargs)

    def get_connection(self, url, proxies=None):
        parsed = urlparse(url)
        url = parsed.geturl()
        conn = self.poolmanager.connection_from_url(url)

        return conn

    async def send(
            self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ) -> requests.Response:

        try:
            conn = self.get_connection(url=request.url, proxies=None)
        except LocationValueError as e:
            raise exceptions.InvalidURL(e, request=request)

        if isinstance(timeout, tuple):
            try:
                connect, read = timeout
                timeout = TimeoutSauce(connect=connect, read=read)
            except ValueError as e:
                # this may raise a string formatting error.
                err = ("Invalid timeout {}. Pass a (connect, read) "
                       "timeout tuple, or a single float to set "
                       "both timeouts to the same value".format(timeout))
                raise ValueError(err)
        elif isinstance(timeout, TimeoutSauce):
            pass
        else:
            timeout = TimeoutSauce(connect=timeout, read=timeout)

        resp = await conn.urlopen(
            method=request.method,
            url=request.url,
            body=request.body,
            headers=request.headers,
            redirect=False,
            assert_same_host=False,
            preload_content=False,
            decode_content=False,
            retries=self.max_retries,
            timeout=timeout
        )

        return self.build_response(request, resp)

    async def close(self):
        pass

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        raise NotImplementedError("Method is currently not available")

    def cert_verify(self, conn, url, verify, cert):
        raise NotImplementedError("Method is currently not available")

    def request_url(self, request, proxies):
        raise NotImplementedError("Method is currently not available")
