const axios = require('axios');

class SurveyHeartService {
  constructor(apiToken) {
    this.apiToken = apiToken;
    this.baseURL = 'https://api.surveyheart.com/v1';
  }

  async getFormResponses(formId, limit = 100) {
    try {
      const response = await axios.get(`${this.baseURL}/forms/${formId}/responses`, {
        headers: {
          'Authorization': `Bearer ${this.apiToken}`,
          'Content-Type': 'application/json'
        },
        params: {
          limit: limit,
          orderBy: '-createdAt'
        }
      });
      return response.data;
    } catch (error) {
      console.error('Erro ao buscar respostas:', error.message);
      return null;
    }
  }

  async importarRespostasComoAlunos(formId, mapeamentoCampos, Aluno, googleCalendar) {
    const respostas = await this.getFormResponses(formId);
    if (!respostas || !respostas.data) {
      return 0;
    }

    let alunosImportados = 0;

    for (const resposta of respostas.data) {
      try {
        const existente = await Aluno.findOne({ where: { id_externo: String(resposta.id) } });
        if (existente) {
          continue;
        }

        const dadosResposta = resposta.data || {};

        const aluno = await Aluno.create({
          id_externo: String(resposta.id),
          nome: dadosResposta[mapeamentoCampos.nome] || '',
          email: dadosResposta[mapeamentoCampos.email] || '',
          telefone: dadosResposta[mapeamentoCampos.telefone] || '',
          modalidade: dadosResposta[mapeamentoCampos.modalidade] || 'Não informada',
          tipo_aluno: 'particular',
          status: 'ativo',
          data_nascimento: mapeamentoCampos.data_nascimento 
            ? dadosResposta[mapeamentoCampos.data_nascimento] 
            : null
        });

        if (aluno.data_nascimento) {
          const eventId = await googleCalendar.criarEventoAniversario(aluno);
          if (eventId) {
            aluno.calendar_event_id = eventId;
            await aluno.save();
          }
        }

        alunosImportados++;
      } catch (error) {
        console.error(`Erro ao importar resposta ${resposta.id}:`, error.message);
        continue;
      }
    }

    return alunosImportados;
  }
}

module.exports = SurveyHeartService;
