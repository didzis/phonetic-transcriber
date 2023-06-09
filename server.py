#!/usr/bin/env python3

import re, asyncio, traceback, json, sys
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


def run_server(address, transcriber, cors=True, debug=False):

    try:
        from .phonetic_transcriber import clean_text
    except ImportError:
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
        if cors:
            headers['Access-Control-Allow-Origin'] = '*'
            headers['Access-Control-Allow-Headers'] = '*'
        data = prep_response(status, headers, body)
        writer.write(data)
        if debug:
            print(f'Sent to {addr} data: {data}')

    async def main_handler(reader: StreamReader, writer: StreamWriter, timeout=30):
        async def session():
            addr = ''
            try:
                async with async_timeout(30):
                    with closing(writer):
                        try:
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

                            if not (path.startswith('/transcribe?') or path == '/transcribe'):
                                write_response(writer, addr, '404 Not Found')
                                return

                            if not (method in ('GET', 'POST', 'OPTIONS') and path.startswith('/transcribe?')) and not (method == 'POST' and path == '/transcribe'):
                                write_response(writer, addr, '400 Bad Request')
                                return

                            if method == 'OPTIONS':
                                write_response(writer, addr, '200 OK')
                                return

                            body = int(headers.get('content-length', 0))

                            if body > 0:
                                body = await reader.read(body)

                            accepted_fmts = set()

                            # accepts = []
                            for accept in headers.get('accept', '*/*').split(','):
                                mime_type, *q = accept.strip().split(';')
                                if len(q) and q[0].startswith('q='):
                                    q = float(q[0].split('=')[1])
                                else:
                                    q = 1.0
                                # accepts.append(dict(mime_type=mime_type, q=q))
                                if mime_type == '*/*':
                                    accepted_fmts = set(['text', 'json'])
                                elif mime_type == 'application/json':
                                    accepted_fmts |= set(['json'])
                                elif mime_type == 'text/plain':
                                    accepted_fmts |= set(['text'])

                            accepted_fmts = set(['text', 'json'])

                            if 'text' in accepted_fmts:
                                response_fmt = 'text'
                            else:
                                response_fmt = list(accepted_fmts)[0]

                            if method == 'POST':
                                content_type = headers.get('content-type', 'text/plain')
                                mime_type, *content_type_params = content_type.split(';')
                                try:
                                    content_type_params = {key:value for key, value in (kv.split('=') for kv in content_type_params)}
                                except:
                                    write_response(writer, addr, '400 Bad Request')
                                    return
                                content_charset = content_type_params.get('charset', 'utf-8')
                                if content_charset.lower() != 'utf-8':
                                    print(f'charset {content_charset} is not  supported')
                                    write_response(writer, addr, '400 Bad Request')
                                    return
                                if mime_type in ('text', 'text/plain'):
                                    text = body.decode('utf8')
                                elif mime_type == 'application/json':
                                    body = body.decode('utf8')
                                    body = json.loads(body)
                                    text = body.get('text')
                                else:
                                    print(f'MIME type {mime_type} is not  supported')
                                    write_response(writer, addr, '400 Bad Request')
                                    return
                            else:
                                text = None

                            qs = parse_qs(path.split('?', 1)[1], True)

                            if not qs.get('text') and not text and not qs.get('word'):
                                write_response(writer, addr, '400 Bad Request')
                                return

                            response_fmt = qs.get('fmt', [response_fmt])[0]
                            sep = qs.get('sep', [' '])[0]
                            unknown_sep = qs.get('unknown_sep', qs.get('usep', [sep]))[0]
                            phoneme_sep = qs.get('phoneme_sep', qs.get('psep', [sep]))[0]

                            if phoneme_sep == 'json' and 'json' in accepted_fmts:
                                phoneme_sep = True

                            preserve_unknown = True
                            unknown_str = qs.get('unknown', qs.get('u', ['true']))[0]
                            if unknown_str in '1tTyY' or unknown_str.lower() in ('true', 'yes'):
                                preserve_unknown = True
                            elif unknown_str in '0fFnN' or unknown_str.lower() in ('false', 'no'):
                                preserve_unknown = False

                            if response_fmt != 'json' and phoneme_sep is True:
                                print(f'error: array response type (sep = True) is only supported with json result format', file=sys.stderr)
                                write_response(writer, addr, '400 Bad Request')
                                return


                            word = clean_text(qs.get('word', [''])[0])
                            if text is None:
                                text = clean_text(qs.get('text', [''])[0])

                            try:
                                if word:
                                    print(f'Transcribing: {word}')
                                    result = transcriber.transcribe(word, phoneme_sep)
                                elif text:
                                    print(f'Transcribing phrase: {text}')
                                    result = transcriber.transcribeText(text, preserve_unknown=preserve_unknown, sep=phoneme_sep, unknown_sep=unknown_sep)
                            except Exception as e:
                                print(traceback.format_exc())
                                print(f'Got exception: {e}')
                                # write_response(writer, addr, '400 Bad Request')
                                write_response(writer, addr, '500 Internal Server Error')
                                return

                            if response_fmt == 'json':
                                result = json.dumps(result, indent=2, ensure_ascii=False)
                                content_type = 'application/json; charset=utf-8'
                            elif response_fmt == 'text':
                                content_type = 'text/plain; charset=utf-8'


                            print(f'Got result: {result}')
                            # print(result.encode('utf8'))

                            write_response(writer, addr, '200 OK', {'Content-Type': content_type}, body=result)

                            # writer.write(b'HTTP/1.1 200 OK\r\n')
                            # writer.write(b'Host: localhost\r\n')
                            # writer.write(b'Content-Length: 2\r\n')
                            # writer.write(b'\r\n')
                            # writer.write(b'OK')

                        except Exception as e:
                            print(traceback.format_exc())
                            print(f'{addr} Exception:', e)
                            write_response(writer, addr, '500 Internal Server Error')

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
    parser.add_argument('--debug', '-d', action='store_true', help='debug mode')

    args = parser.parse_args()

    try:
        from .phonetic_transcriber import PhoneticTranscriberData, default_rules_path, default_exceptions_path, PhoneticTranscriber
        from .phonetic_converter import IPACharacterConverter
    except ImportError:
        from phonetic_transcriber import PhoneticTranscriberData, default_rules_path, default_exceptions_path, PhoneticTranscriber
        from phonetic_converter import IPACharacterConverter

    data = PhoneticTranscriberData(rules_filepath=args.rules or default_rules_path, exceptions_filepath=args.exceptdb or default_exceptions_path)

    transcriber = PhoneticTranscriber(sep=' ', encoder=IPACharacterConverter(), data=data)

    run_server(args.server, transcriber, debug=args.debug)
