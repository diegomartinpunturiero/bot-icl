"""Motor conversacional independiente del canal; persistencia local en SQLite."""
import json
import re
import sqlite3
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urlencode


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


class Bot:
    def __init__(self, catalog, database):
        self.catalog = json.loads(Path(catalog).read_text(encoding='utf-8'))
        self.courses = self.catalog['courses']
        ids = [c['id'] for c in self.courses]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('El catálogo debe tener cursos con IDs únicos.')
        phone = self.catalog.get('advisor_whatsapp', '')
        if phone and not re.fullmatch(r'[0-9]{8,15}', phone):
            raise ValueError('advisor_whatsapp debe contener solo dígitos internacionales.')
        self.database = str(database)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, course TEXT, handed_off INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS handoffs (
                    id TEXT PRIMARY KEY, session_id TEXT, course TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'pending');
            ''')

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def menu(self):
        return ('¡Hola! Soy el asistente de ICL. ¿Qué te gustaría aprender?\n' +
                '\n'.join(f'{i}. {c["name"]}' for i, c in enumerate(self.courses, 1)) +
                '\nRespondé con un número o el nombre del curso. También podés escribir '
                '«precio», «modalidad» o «asesor». Escribí «menú» para volver.')

    def reply(self, message, session_id=None):
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            raise ValueError('El mensaje debe contener entre 1 y 2000 caracteres.')
        if session_id is not None:
            try:
                session_id = str(uuid.UUID(session_id))
            except (ValueError, TypeError, AttributeError):
                raise ValueError('session_id debe ser un UUID válido.') from None
        session_id = session_id or str(uuid.uuid4())
        text = normalize(message.strip())
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO sessions(id) VALUES (?)', (session_id,))
            selected, handed_off = db.execute(
                'SELECT course, handed_off FROM sessions WHERE id=?', (session_id,)).fetchone()
            result = {'session_id': session_id, 'handoff': bool(handed_off)}
            if text in ('menu', 'inicio', 'reiniciar'):
                db.execute('UPDATE sessions SET course=NULL, handed_off=0 WHERE id=?', (session_id,))
                result.update(reply=self.menu(), handoff=False)
                return result
            if handed_off:
                result['reply'] = ('Tu solicitud ya está registrada para atención humana. '
                                   'Escribí «menú» si querés volver al bot.')
                return result
            if re.search(r'\b(asesor|persona|humano|inscribir|inscribirme|anotarme)\b', text):
                ticket = str(uuid.uuid4())
                db.execute('INSERT INTO handoffs(id,session_id,course) VALUES (?,?,?)',
                           (ticket, session_id, selected))
                db.execute('UPDATE sessions SET handed_off=1 WHERE id=?', (session_id,))
                result.update(handoff=True, ticket_id=ticket,
                              reply='Registré tu solicitud de atención humana. Código: ' + ticket +
                              '. El equipo debe revisar la bandeja de derivaciones; no hay aviso automático.')
                phone = self.catalog.get('advisor_whatsapp')
                if phone:
                    result['contact_url'] = f'https://wa.me/{phone}?' + urlencode(
                        {'text': f'Hola ICL. Consulta: {selected or "cursos"}. Solicitud: {ticket}'})
                return result
            matches = [c for c in self.courses if any(
                re.search(r'(?<!\w)' + re.escape(normalize(k)) + r'(?!\w)', text)
                for k in c['keywords'])]
            if text.isdigit() and 1 <= int(text) <= len(self.courses):
                matches = [self.courses[int(text)-1]]
            # Inverter puede mencionar también aire acondicionado: priorizar la especialidad.
            if {c['id'] for c in matches} == {'aire', 'inverter'}:
                matches = [c for c in matches if c['id'] == 'inverter']
            if len(matches) > 1:
                result['reply'] = 'Mencionaste varios cursos. Elegí uno para consultar:\n' + self.menu()
                return result
            if matches:
                selected = matches[0]['id']
                db.execute('UPDATE sessions SET course=? WHERE id=?', (selected, session_id))
            course = next((c for c in self.courses if c['id'] == selected), None)
            price = bool(re.search(r'\b(precio|costo|valor|cuanto|arancel|cuota|cuotas)\b', text))
            modality = bool(re.search(r'\b(modalidad|presencial|online|virtual|duracion|horario|horarios)\b', text))
            if not course:
                result['reply'] = ('Elegí primero un curso para consultar precio o modalidad.\n'
                                   if price or modality else '') + self.menu()
            elif matches or price or modality:
                parts = [course['name']]
                if price or matches:
                    parts.append('Precio: ' + (course.get('price') or
                        'pendiente de confirmar. Escribí «asesor» para consultar el arancel vigente.'))
                if modality or matches:
                    parts.append('Modalidad: ' + (course.get('modality') or
                        'pendiente de confirmar. Escribí «asesor» para consultar sede, duración y horarios.'))
                parts.append('Podés consultar «precio», «modalidad», elegir otro curso o pedir un «asesor».')
                result['reply'] = '\n'.join(parts)
            else:
                result['reply'] = 'Puedo ayudarte con cursos, precio y modalidad. Escribí «menú» o «asesor».'
            return result

    def handoffs(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM handoffs ORDER BY created_at')]
