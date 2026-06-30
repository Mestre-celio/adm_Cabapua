import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta
import json
from app import app, db, Usuario, Aluno, CheckIn

class CTMTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.app = app.test_client()
        
        # Setup context and DB
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        
        # Seed default user
        self.admin = Usuario(
            username='admin',
            nome='Administrador',
            nivel='admin',
            email='admin@ctmcabapua.com.br'
        )
        self.admin.set_password('admin123')
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_admin(self):
        return self.app.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)

    def test_login_logout(self):
        # Test GET login
        response = self.app.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'CTM CABAPUA', response.data)

        # Test POST invalid login
        response = self.app.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Usuario ou senha incorretos', response.data)

        # Test POST valid login
        response = self.login_admin()
        self.assertIn(b'Dashboard', response.data)

        # Test logout
        response = self.app.get('/logout', follow_redirects=True)
        self.assertIn(b'CTM CABAPUA', response.data)

    @patch('app.get_calendar_service')
    def test_aluno_crud_and_birthday_calendar(self, mock_get_calendar):
        # Mock Google Calendar API
        mock_service = MagicMock()
        mock_get_calendar.return_value = mock_service
        mock_service.events.return_value.insert.return_value.execute.return_value = {'id': 'mock-event-123'}

        # Login first
        self.login_admin()

        # 1. Create Aluno
        response = self.app.post('/aluno/novo', data={
            'nome': 'Joao Silva',
            'email': 'joao@silva.com',
            'telefone': '11999999999',
            'data_nascimento': '1990-06-30',
            'tipo_aluno': 'particular',
            'matricula_app': '12345',
            'modalidade': 'Muay Thai',
            'graduacao': 'Grau Branco',
            'plano': 'Mensal',
            'valor': '150.00',
            'vencimento': '2026-07-30',
            'validade_plano_app': '2026-07-30',
            'status': 'ativo'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        
        # Verify in database
        aluno = Aluno.query.filter_by(nome='Joao Silva').first()
        self.assertIsNotNone(aluno)
        self.assertEqual(aluno.email, 'joao@silva.com')
        self.assertEqual(aluno.calendar_event_id, 'mock-event-123')
        
        # Verify calendar event creation was called
        mock_service.events.return_value.insert.assert_called_once()

        # 2. List Alunos
        response = self.app.get('/alunos')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Joao Silva', response.data)

        # 3. Edit Aluno
        response = self.app.post(f'/aluno/{aluno.id}/editar', data={
            'nome': 'Joao Silva Editado',
            'email': 'joao@silva.com',
            'telefone': '11999999999',
            'data_nascimento': '1990-06-30',
            'tipo_aluno': 'particular',
            'matricula_app': '12345',
            'modalidade': 'Muay Thai',
            'graduacao': 'Grau Azul',
            'plano': 'Semestral',
            'valor': '130.00',
            'vencimento': '2026-12-30',
            'validade_plano_app': '2026-12-30',
            'status': 'ativo'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        db.session.refresh(aluno)
        self.assertEqual(aluno.nome, 'Joao Silva Editado')

        # 4. Delete Aluno
        response = self.app.post(f'/aluno/{aluno.id}/excluir', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify deletion
        aluno_deleted = Aluno.query.get(aluno.id)
        self.assertIsNone(aluno_deleted)
        # Verify calendar event deletion was called
        mock_service.events.return_value.delete.assert_called_once()

    def test_checkin_flow(self):
        # Create student for checkin
        aluno = Aluno(
            nome='Maria Souza',
            tipo_aluno='wellhub',
            matricula_app='98765',
            validade_plano_app=date.today() + timedelta(days=10),
            status='ativo'
        )
        db.session.add(aluno)
        db.session.commit()

        self.login_admin()

        # 1. Test registration via Form
        response = self.app.post('/checkin', data={
            'origem': 'wellhub',
            'matricula_app': '98765',
            'codigo': 'ABC-123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Check-in registrado: Maria Souza', response.data)

        # Check CheckIn entry in database
        checkin = CheckIn.query.filter_by(aluno_id=aluno.id).first()
        self.assertIsNotNone(checkin)
        self.assertEqual(checkin.origem, 'wellhub')
        self.assertEqual(checkin.codigo_verificacao, 'ABC-123')

        # 2. Test registration via JSON API
        response = self.app.post('/api/checkin', data=json.dumps({
            'app': 'wellhub',
            'matricula': '98765',
            'codigo_verificacao': 'XYZ-987'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data_json = json.loads(response.data)
        self.assertTrue(data_json['success'])
        self.assertEqual(data_json['aluno'], 'Maria Souza')

        # Check total checkins
        self.assertEqual(CheckIn.query.count(), 2)

    @patch('requests.get')
    @patch('app.get_calendar_service')
    def test_surveyheart_import(self, mock_get_calendar, mock_get):
        # Mock Google Calendar
        mock_service = MagicMock()
        mock_get_calendar.return_value = mock_service
        mock_service.events().insert().execute.return_value = {'id': 'mock-event-999'}

        # Mock SurveyHeart API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [
                {
                    'id': 'response_abc123',
                    'data': {
                        'f_name': 'Carlos Santos',
                        'f_email': 'carlos@santos.com',
                        'f_phone': '11988887777',
                        'f_birthday': '1995-10-15',
                        'f_modality': 'Jiu-Jitsu'
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        self.login_admin()

        # Import
        response = self.app.post('/surveyheart/importar', data={
            'api_token': 'fake-token-123',
            'form_id': 'form_fake_456',
            'field_nome': 'f_name',
            'field_email': 'f_email',
            'field_telefone': 'f_phone',
            'field_nascimento': 'f_birthday',
            'field_modalidade': 'f_modality'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'1 aluno(s) importado(s) com sucesso!', response.data)

        # Check in DB
        aluno = Aluno.query.filter_by(id_externo='response_abc123').first()
        self.assertIsNotNone(aluno)
        self.assertEqual(aluno.nome, 'Carlos Santos')
        self.assertEqual(aluno.email, 'carlos@santos.com')
        self.assertEqual(aluno.data_nascimento, date(1995, 10, 15))
        self.assertEqual(aluno.modalidade, 'Jiu-Jitsu')
        self.assertEqual(aluno.calendar_event_id, 'mock-event-999')

    def test_relatorios(self):
        # Create check-in data and expiring plans
        aluno_wellhub = Aluno(
            nome='Aluno Wellhub',
            tipo_aluno='wellhub',
            matricula_app='wh-1',
            validade_plano_app=date.today() + timedelta(days=2),
            status='ativo'
        )
        aluno_totalpass = Aluno(
            nome='Aluno Totalpass',
            tipo_aluno='totalpass',
            matricula_app='tp-1',
            validade_plano_app=date.today() + timedelta(days=15),  # Not expiring in 7 days
            status='ativo'
        )
        db.session.add_all([aluno_wellhub, aluno_totalpass])
        db.session.commit()

        # Add checkins
        c1 = CheckIn(aluno_id=aluno_wellhub.id, origem='wellhub')
        c2 = CheckIn(aluno_id=aluno_totalpass.id, origem='totalpass')
        c3 = CheckIn(aluno_id=aluno_wellhub.id, origem='wellhub')
        db.session.add_all([c1, c2, c3])
        db.session.commit()

        self.login_admin()

        response = self.app.get('/relatorios')
        self.assertEqual(response.status_code, 200)
        
        # Check if reports page lists checkins by app counts
        self.assertIn(b'WELLHUB', response.data)
        self.assertIn(b'TOTALPASS', response.data)
        
        # Check if student with expiring plan is listed
        self.assertIn(b'Aluno Wellhub', response.data)
        # Student with plan expiring in 15 days should NOT be listed
        self.assertNotIn(b'Aluno Totalpass', response.data)

if __name__ == '__main__':
    unittest.main()
