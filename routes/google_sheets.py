from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required

google_sheets_bp = Blueprint('google_sheets', __name__)


@google_sheets_bp.route('/google-sheets', methods=['GET', 'POST'])
@login_required
def importar():
    from services.google_sheets import GoogleSheetsService
    service = GoogleSheetsService()
    sheets_connected = service.is_authenticated()

    if request.method == 'POST':
        if not sheets_connected:
            flash('Google Sheets não está configurado!', 'error')
            return redirect(url_for('google_sheets.importar'))

        spreadsheet_id = request.form.get('spreadsheet_id', '').strip()
        if not spreadsheet_id:
            flash('Informe o ID da planilha!', 'error')
            return render_template('google_sheets.html', sheets_connected=sheets_connected)

        worksheet_name = request.form.get('worksheet_name', '').strip() or None
        field_mapping = {
            'nome': request.form.get('field_nome', 'Nome'),
            'telefone': request.form.get('field_telefone', 'Telefone'),
            'email': request.form.get('field_email', 'Email'),
            'modalidade': request.form.get('field_modalidade', 'Modalidade'),
        }

        imported = service.import_students(spreadsheet_id, worksheet_name, field_mapping)
        if imported is None:
            flash('Erro ao importar dados. Verifique o ID da planilha.', 'error')
        elif imported == 0:
            flash('Nenhum novo aluno encontrado para importar.', 'info')
        else:
            flash(f'{imported} aluno(s) importado(s) com sucesso!', 'success')

        return redirect(url_for('google_sheets.importar'))

    return render_template('google_sheets.html', sheets_connected=sheets_connected)
