import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from app import handler
from bot import Bot

ROOT = Path(__file__).resolve().parents[1]


class BotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / 'test.sqlite3'
        self.bot = Bot(ROOT / 'config/courses.json', self.database)

    def tearDown(self):
        self.temp.cleanup()

    def test_menu_and_selection(self):
        result = self.bot.reply('hola')
        self.assertIn('1. Instalación', result['reply'])
        selected = self.bot.reply('3', result['session_id'])
        self.assertIn('Heladeras familiares', selected['reply'])

    def test_interest_and_context_survive_restart(self):
        result = self.bot.reply('Me interesa refrigeración comercial')
        restarted = Bot(ROOT / 'config/courses.json', self.database)
        response = restarted.reply('cuánto cuesta', result['session_id'])
        self.assertIn('Refrigeración comercial', response['reply'])
        self.assertIn('pendiente de confirmar', response['reply'])

    def test_inverter_priority_and_word_boundaries(self):
        self.assertIn('Inverter', self.bot.reply('aire acondicionado inverter')['reply'])
        self.assertIn('¿Qué te gustaría', self.bot.reply('placard')['reply'])

    def test_ambiguous_interest(self):
        self.assertIn('varios cursos', self.bot.reply('heladeras y lavarropas')['reply'])

    def test_price_and_modality_from_catalog(self):
        catalog = json.loads((ROOT / 'config/courses.json').read_text())
        catalog['courses'][0].update(price='ARS 100 (dato de prueba)', modality='Virtual (prueba)')
        catalog['advisor_whatsapp'] = '5491100000000'
        file = Path(self.temp.name) / 'catalog.json'
        file.write_text(json.dumps(catalog))
        bot = Bot(file, self.database)
        response = bot.reply('precio y modalidad de split')
        self.assertIn('ARS 100', response['reply'])
        self.assertIn('Virtual', response['reply'])
        self.assertTrue(bot.reply('asesor', response['session_id'])['contact_url'].startswith('https://wa.me/'))

    def test_handoff_is_persistent_and_idempotent(self):
        result = self.bot.reply('lavarropas')
        first = self.bot.reply('asesor', result['session_id'])
        self.assertTrue(first['handoff'])
        self.bot.reply('asesor', result['session_id'])
        tickets = self.bot.handoffs()
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0]['course'], 'lavarropas')
        self.assertEqual(tickets[0]['id'], first['ticket_id'])
        reset = self.bot.reply('menú', result['session_id'])
        self.assertFalse(reset['handoff'])
        self.assertIn('Elegí primero', self.bot.reply('precio', result['session_id'])['reply'])

    def test_invalid_input_and_session_isolation(self):
        for message in ('', 'x' * 2001, None):
            with self.assertRaises(ValueError):
                self.bot.reply(message)
        with self.assertRaises(ValueError):
            self.bot.reply('hola', 'invalid')
        self.bot.reply('lavarropas')
        self.assertIn('Elegí primero', self.bot.reply('precio')['reply'])

    def test_http_contract(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.bot))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertIn('Consultas de cursos', urlopen(url).read().decode())
            self.assertEqual(json.load(urlopen(url + '/health'))['status'], 'ok')
            request = Request(url + '/api/chat', data=json.dumps({'message': '1'}).encode(),
                              headers={'Content-Type': 'application/json'})
            self.assertIn('Instalación', json.load(urlopen(request))['reply'])
            for body in (b'[]', b'{', b'{"message":null}'):
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(url + '/api/chat', data=body))
                self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
