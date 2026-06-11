import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import asyncio
from app import app


class WSGIApp:
    """Custom ASGI-to-WSGI bridge for LiteSpeed lswsgi.
    
    Neither a2wsgi nor starlette's WSGIMiddleware work with lswsgi,
    so we manually translate WSGI environ to ASGI scope and run
    the FastAPI app in a fresh event loop per request.
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response):
        import io

        path = environ.get('PATH_INFO', '/')
        method = environ.get('REQUEST_METHOD', 'GET')
        query = environ.get('QUERY_STRING', '')

        headers = []
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').lower()
                headers.append((header_name.encode(), value.encode()))
            elif key == 'CONTENT_TYPE' and value:
                headers.append((b'content-type', value.encode()))
            elif key == 'CONTENT_LENGTH' and value:
                headers.append((b'content-length', value.encode()))

        body = environ.get('wsgi.input', io.BytesIO())
        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        except (ValueError, TypeError):
            content_length = 0
        try:
            body_bytes = body.read(content_length) if content_length > 0 else b''
        except Exception:
            body_bytes = b''

        scope = {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'method': method,
            'path': path,
            'query_string': query.encode('utf-8'),
            'root_path': '',
            'scheme': environ.get('wsgi.url_scheme', 'http'),
            'server': (
                environ.get('SERVER_NAME', 'localhost'),
                int(environ.get('SERVER_PORT', 80)),
            ),
            'headers': headers,
        }

        loop = asyncio.new_event_loop()

        response_headers = []
        response_body = []
        status_code = 200

        async def receive():
            return {'type': 'http.request', 'body': body_bytes, 'more_body': False}

        async def send(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message['status']
                for h in message.get('headers', []):
                    name = h[0].decode() if isinstance(h[0], bytes) else h[0]
                    val = h[1].decode() if isinstance(h[1], bytes) else h[1]
                    response_headers.append((name, val))
            elif message['type'] == 'http.response.body':
                chunk = message.get('body', b'')
                if chunk:
                    response_body.append(chunk)

        try:
            loop.run_until_complete(self.asgi_app(scope, receive, send))
        finally:
            loop.close()

        start_response(f'{status_code} OK', response_headers)
        return response_body


application = WSGIApp(app)
