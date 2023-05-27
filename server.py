#!/usr/bin/env python3

import re, asyncio, traceback
from asyncio.streams import StreamReader, StreamWriter
from contextlib import closing
from urllib.parse import parse_qs


# solution idea from: https://github.com/aio-libs/async-timeout/blob/master/async_timeout/__init__.py
class async_timeout:
    def __init__(self, seconds):
        self._seconds = seconds
        self._cancelled = False
    async def __aenter__(self):
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        self._killer = loop.call_at(loop.time() + self._seconds, self._cancel, task)
        return
    async def __aexit__(self, exc_type, exc, tb):
        if not self._killer.cancelled():
            self._killer.cancel()
        if self._cancelled:
            raise asyncio.TimeoutError
        # return True
    def _cancel(self, task):
        self._cancelled = True
        task.cancel()


# based on: https://gist.github.com/2minchul/609255051b7ffcde023be93572b25101


def run_server(address, transcriber, debug=False):

    from phonetic_transcriber import clean_text

    def prep_response(status, headers={}, body=None):
        nonlocal hostname

        if not body:
            body = b''
        elif body and type(body) is str:
            body = body.encode('utf8')

        response = []
        response.append(f'HTTP/1.1 {status}')
        headers['Host'] = hostname
        headers['Content-Length'] = len(body) if body else 0
        for key, value in headers.items():
            response.append(f'{key}: {value}')
        response.append('')
        response.append('')
        return '\r\n'.join(response).encode('utf8') + body

    def write_response(writer, addr, status='200 OK', headers={}, body=None):
        print(f'{addr} {status}')
        writer.write(prep_response(status, headers, body))

    async def main_handler(reader: StreamReader, writer: StreamWriter, timeout=30):
        async def session():
            addr = ''
            try:
                async with async_timeout(30):
                    with closing(writer):
                        data = await reader.readuntil(b'\r\n\r\n')
                        addr = writer.get_extra_info('peername')

                        if debug:
                            print(f'Received {data} from {addr!r}')

                        request = data.decode('utf8').split('\r\n')

                        m = re.match(r'([A-Z]+) ([^\s]+) HTTP\/[.0-9]+', request[0])
                        if not m:
                            print(f'Invalid request received {data} from {addr!r}')
                            return

                        method, path = m.groups()

                        print(f'{addr!r} {method} {path}')

                        headers = {}
                        for line in request[1:]:
                            m = re.match(r'([^:]+): ([^\r\n]+)', line)
                            if m:
                                key, value = m.groups()
                                headers[key.lower()] = value    # we do not process recurring headers

                        if method != 'GET' or not path.startswith('/transcribe'):
                            write_response(writer, addr, '404 Not Found')
                            return

                        if not path.startswith('/transcribe?'):
                            write_response(writer, addr, '400 Bad Request')
                            return

                        qs = parse_qs(path.split('?', 1)[1])

                        if not qs.get('text') and not qs.get('phrase'):
                            write_response(writer, addr, '400 Bad Request')
                            return

                        body = headers.get('content-length', 0)

                        if body > 0:
                            await reader.read(body)

                        text = qs.get('text')
                        phrase = qs.get('phrase')
                        if text:
                            text = clean_text(text[0])
                        elif phrase:
                            phrase = clean_text(phrase[0])

                        # text = clean_text(qs['text'][0])

                        try:
                            if text:
                                print(f'Transcribing: {text}')
                                result = transcriber.transcribe(text)
                            elif phrase:
                                print(f'Transcribing phrase: {phrase}')
                                result = transcriber.transcribePhrase(phrase)
                        except Exception as e:
                            print(traceback.format_exc())
                            print(f'Got exception: {e}')
                            # write_response(writer, addr, '400 Bad Request')
                            write_response(writer, addr, '500 Internal Server Error')
                            return

                        print(f'Got result: {result}')
                        # print(result.encode('utf8'))

                        write_response(writer, addr, '200 OK', {'Content-Type': 'text/html; charset=utf-8'}, body=result)

                        # writer.write(b'HTTP/1.1 200 OK\r\n')
                        # writer.write(b'Host: localhost\r\n')
                        # writer.write(b'Content-Length: 2\r\n')
                        # writer.write(b'\r\n')
                        # writer.write(b'OK')

            except asyncio.TimeoutError:
                print(f'Timeout {addr}')
            finally:
                print(f'Closed connection {addr}')

        asyncio.create_task(session())

    hostname = ''

    async def main():

        nonlocal hostname

        host, *port = address.split(':', 2)
        if len(port) > 0:
            port = int(port[0])
        else:
            port = 8080
        if not host:
            host = '127.0.0.1'
        elif host == '*':
            host = '0.0.0.0'

        # host, port = '127.0.0.1', 8888

        server = await asyncio.start_server(
            main_handler, host, port
        )
        addr = server.sockets[0].getsockname()
        print(f'Serving on {addr}')

        hostname = ':'.join(map(str, addr[:2]))

        async with server:
            await server.serve_forever()


    asyncio.run(main())


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--rules', '-r', metavar='FILE', type=str, help='input rules.json')
    parser.add_argument('--exceptdb', '-e', metavar='FILE', type=str, help='input exceptions.json')
    parser.add_argument('--server', '-s', metavar='HOST:PORT', default='localhost:8080', help='run server listening on [HOST]:PORT')
    parser.add_argument('--debug', '-d', help='debug mode')

    args = parser.parse_args()

    from phonetic_transcriber import PhoneticTranscriberData, default_rules_path, default_exceptions_path, PhoneticTranscriber
    from phonetic_converter import IPACharacterConverter

    data = PhoneticTranscriberData(rules_filepath=args.rules or default_rules_path, exceptions_filepath=args.exceptdb or default_exceptions_path)

    transcriber = PhoneticTranscriber(sep=' ', encoder=IPACharacterConverter(), data=data)

    run_server(args.server, transcriber, debug=args.debug)
