import urllib3.util.timeout as urllib3_timeout
import urllib3.exceptions as urllib3_exceptions
import requests_async.exceptions as exceptions
import requests_async.poolmanager as poolmanager
import requests
import requests.adapters as adapters

DEFAULT_POOLBLOCK = False
DEFAULT_POOLSIZE = 1
DEFAULT_RETRIES = 0
DEFAULT_POOL_TIMEOUT = None


class HTTPAdapter(adapters.HTTPAdapter):

    def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK, **pool_kwargs):
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block

        self.poolmanager = poolmanager.PoolManager(num_pools=connections, maxsize=maxsize,
                                                   block=block, strict=True, **pool_kwargs)

    async def close(self):
        pass

    async def send(
            self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ) -> requests.Response:

        try:
            conn = self.get_connection(url=request.url, proxies=None)
        except urllib3_exceptions.LocationValueError as e:
            raise exceptions.InvalidURL(e, request=request)

        if isinstance(timeout, tuple):
            try:
                connect, read = timeout
                timeout = urllib3_timeout.Timeout(connect=connect, read=read)
            except ValueError as e:
                # this may raise a string formatting error.
                err = ("Invalid timeout {}. Pass a (connect, read) "
                       "timeout tuple, or a single float to set "
                       "both timeouts to the same value".format(timeout))
                raise ValueError(err)
        elif isinstance(timeout, urllib3_timeout.Timeout):
            pass
        else:
            timeout = urllib3_timeout.Timeout(connect=timeout, read=timeout)

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

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        raise NotImplementedError("Method is currently not available")

    def cert_verify(self, conn, url, verify, cert):
        raise NotImplementedError("Method is currently not available")

    def request_url(self, request, proxies):
        raise NotImplementedError("Method is currently not available")
