const { google } = require('googleapis');
const fs = require('fs').promises;
const path = require('path');

const SCOPES = ['https://www.googleapis.com/auth/calendar'];
const TOKEN_PATH = path.join(__dirname, '..', 'token.json');
const CREDENTIALS_PATH = path.join(__dirname, '..', 'credentials.json');

class GoogleCalendarService {
  constructor() {
    this.oauth2Client = null;
  }

  async authorize() {
    const credentials = await this.loadCredentials();
    const { client_secret, client_id, redirect_uris } = credentials.installed || credentials.web;
    
    this.oauth2Client = new google.auth.OAuth2(
      client_id,
      client_secret,
      redirect_uris ? redirect_uris[0] : process.env.GOOGLE_REDIRECT_URI
    );

    try {
      const token = await fs.readFile(TOKEN_PATH, 'utf8');
      this.oauth2Client.setCredentials(JSON.parse(token));
      return this.oauth2Client;
    } catch (error) {
      return await this.getNewToken();
    }
  }

  async loadCredentials() {
    try {
      const content = await fs.readFile(CREDENTIALS_PATH, 'utf8');
      return JSON.parse(content);
    } catch (err) {
      // Return a mock object if file credentials.json does not exist to avoid throwing on boot in production if calendar is not configured
      return { web: { client_id: process.env.GOOGLE_CLIENT_ID, client_secret: process.env.GOOGLE_CLIENT_SECRET, redirect_uris: [process.env.GOOGLE_REDIRECT_URI] } };
    }
  }

  async getNewToken() {
    const authUrl = this.oauth2Client.generateAuthUrl({
      access_type: 'offline',
      scope: SCOPES,
    });
    console.log('Autorize o acesso aqui:', authUrl);
    throw new Error('Token não encontrado. Execute o fluxo de autorização.');
  }

  async criarEventoAniversario(aluno) {
    try {
      await this.authorize();
      const calendar = google.calendar({ version: 'v3', auth: this.oauth2Client });

      const evento = {
        summary: `Aniversário - ${aluno.nome}`,
        description: `Aluno: ${aluno.nome}\nModalidade: ${aluno.modalidade}\nTelefone: ${aluno.telefone}`,
        start: {
          date: aluno.data_nascimento,
        },
        end: {
          date: new Date(new Date(aluno.data_nascimento).getTime() + 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        },
        recurrence: ['RRULE:FREQ=YEARLY'],
        reminders: {
          useDefault: false,
          overrides: [
            { method: 'email', minutes: 24 * 60 },
            { method: 'popup', minutes: 60 },
          ],
        },
      };

      const response = await calendar.events.insert({
        calendarId: 'primary',
        resource: evento,
      });

      return response.data.id;
    } catch (error) {
      console.error('Erro ao criar evento:', error.message);
      return null;
    }
  }

  async deletarEventoAniversario(eventId) {
    if (!eventId) return;
    
    try {
      await this.authorize();
      const calendar = google.calendar({ version: 'v3', auth: this.oauth2Client });
      
      await calendar.events.delete({
        calendarId: 'primary',
        eventId: eventId,
      });
    } catch (error) {
      console.error('Erro ao deletar evento:', error.message);
    }
  }
}

module.exports = new GoogleCalendarService();
