"""Demo HTTP local y herramientas de consola, sin dependencias externas."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from bot import Bot

ROOT = Path(__file__).resolve().parent


def handler(bot):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No registrar mensajes ni identificadores de conversaciones.

        def send(self, status, payload, kind='application/json; charset=utf-8'):
            data = payload.encode('utf-8') if isinstance(payload, str) else json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/':
                self.send(200, (ROOT / 'static/index.html').read_text(encoding='utf-8'), 'text/html; charset=utf-8')
            elif self.path == '/health':
                self.send(200, {'status': 'ok'})
            else:
                self.send(404, {'error': 'Ruta inexistente'})

        def do_POST(self):
            if self.path != '/api/chat':
                self.send(404, {'error': 'Ruta inexistente'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    self.send(413, {'error': 'Cuerpo vacío o demasiado grande'})
                    return
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('El cuerpo debe ser un objeto JSON.')
                result = bot.reply(payload.get('message'), payload.get('session_id'))
            except (ValueError, UnicodeDecodeError) as exc:
                self.send(400, {'error': str(exc)})
                return
            self.send(200, result)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs='?', choices=['serve', 'chat', 'handoffs'], default='serve')
    args = parser.parse_args()
    database = Path(os.environ.get('BOT_DATABASE', str(ROOT / 'data/bot.sqlite3')))
    database.parent.mkdir(parents=True, exist_ok=True)
    bot = Bot(os.environ.get('BOT_CATALOG', str(ROOT / 'config/courses.json')), database)
    if args.mode == 'handoffs':
        print(json.dumps(bot.handoffs(), ensure_ascii=False, indent=2))
    elif args.mode == 'chat':
        print(bot.menu())
        session = None
        while True:
            try:
                message = input('Vos: ')
            except (EOFError, KeyboardInterrupt):
                break
            if message == '/salir':
                break
            try:
                result = bot.reply(message, session)
                session = result['session_id']
                print(result['reply'])
                if result.get('contact_url'):
                    print(result['contact_url'])
            except ValueError as exc:
                print(exc)
    else:
        port = int(os.environ.get('PORT', '8000'))
        server = ThreadingHTTPServer(('127.0.0.1', port), handler(bot))
        print(f'Demo ICL: http://127.0.0.1:{port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
