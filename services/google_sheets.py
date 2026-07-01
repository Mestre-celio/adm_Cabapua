import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials


class GoogleSheetsService:
    def __init__(self):
        self.client = None
        self._authenticate()

    def _authenticate(self):
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if creds_json:
            try:
                creds_dict = json.loads(creds_json)
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                self.client = gspread.authorize(creds)
            except Exception as e:
                print(f'[GoogleSheets] Erro ao autenticar com env var: {e}')

        if not self.client and os.path.exists('credentials.json'):
            try:
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
                creds = ServiceAccountCredentials.from_json_keyfile('credentials.json', scope)
                self.client = gspread.authorize(creds)
            except Exception as e:
                print(f'[GoogleSheets] Erro ao autenticar com credentials.json: {e}')

    def is_authenticated(self):
        return self.client is not None

    def get_sheet_data(self, spreadsheet_id, worksheet_name=None):
        if not self.client:
            return None
        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            worksheet = sheet.worksheet(worksheet_name) if worksheet_name else sheet.sheet1
            return worksheet.get_all_records()
        except Exception as e:
            print(f'[GoogleSheets] Erro ao ler planilha: {e}')
            return None

    def import_students(self, spreadsheet_id, worksheet_name=None, field_mapping=None):
        records = self.get_sheet_data(spreadsheet_id, worksheet_name)
        if not records:
            return 0

        from app import db, Aluno
        imported = 0

        field_nome = (field_mapping or {}).get('nome', 'Nome')
        field_telefone = (field_mapping or {}).get('telefone', 'Telefone')
        field_email = (field_mapping or {}).get('email', 'Email')
        field_modalidade = (field_mapping or {}).get('modalidade', 'Modalidade')

        for row in records:
            nome = (row.get(field_nome) or '').strip()
            if not nome:
                continue

            if Aluno.query.filter_by(nome=nome).first():
                continue

            aluno = Aluno(nome=nome, status='ativo')

            telefone = row.get(field_telefone, '')
            if telefone:
                aluno.telefone = str(telefone)

            email = row.get(field_email, '')
            if email:
                aluno.email = str(email)

            modalidade = row.get(field_modalidade, '')
            if modalidade:
                aluno.modalidade = str(modalidade)

            db.session.add(aluno)
            imported += 1

        if imported > 0:
            db.session.commit()

        return imported
