from urllib3.util.url import parse_url
import requests_async.connectionpool as connectionpool
import urllib3.exceptions as exceptions
import urllib3.poolmanager as poolmanager

pool_classes_by_scheme = {
    'http': connectionpool.HTTPConnectionPool,
    'https': connectionpool.HTTPSConnectionPool
}


class PoolManager(poolmanager.PoolManager):

    def __init__(self, num_pools=10, headers=None, **connection_pool_kw):
        super().__init__(num_pools=num_pools, headers=headers, connection_pool_kw=connection_pool_kw)
        self.pool_classes_by_scheme = pool_classes_by_scheme

    def __enter__(self):
        raise NotImplementedError("Use 'async with PoolManager', instead of 'with PoolManager'")

    async def __aenter__(self):
        return self

    def __aexit__(self, exc_type, exc_val, exc_tb):
        self.clear()
        # Return False to re-raise any potential exceptions
        return False

    def clear(self):
        pass

    def connection_from_host(self, host, port=None, scheme='http', pool_kwargs=None):
        if not host:
            raise exceptions.LocationValueError("No host specified.")

        request_context = dict()
        request_context['scheme'] = scheme or 'http'
        if not port:
            port = connectionpool.connection.port_by_scheme.get(request_context['scheme'].lower(), 80)
        request_context['port'] = port
        request_context['host'] = host

        return self.connection_from_context(request_context)

    def connection_from_context(self, request_context):
        return self.connection_from_pool_key(pool_key=None, request_context=request_context)

    def connection_from_pool_key(self, pool_key, request_context=None):
        scheme = request_context['scheme']
        host = request_context['host']
        port = request_context['port']
        pool = self._new_pool(scheme, host, port, request_context=request_context)
        return pool

    def connection_from_url(self, url, pool_kwargs=None):
        u = parse_url(url)
        return self.connection_from_host(u.host, port=u.port, scheme=u.scheme,
                                         pool_kwargs=pool_kwargs)

    async def urlopen(self, method, url, redirect=True, **kw):
        raise NotImplementedError("Method is currently not available")

    async def request(self, method, url, fields=None, headers=None, **urlopen_kw):
        raise NotImplementedError("Method is currently not available")

    async def request_encode_url(self, method, url, fields=None, headers=None,
                                 **urlopen_kw):
        raise NotImplementedError("Method is currently not available")

    async def request_encode_body(self, method, url, fields=None, headers=None,
                                  encode_multipart=True, multipart_boundary=None,
                                  **urlopen_kw):
        raise NotImplementedError("Method is currently not available")

