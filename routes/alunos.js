const express = require('express');
const router = express.Router();
const db = require('../models');
const googleCalendar = require('../services/googleCalendar');
const { Op } = require('sequelize');

router.get('/alunos', async (req, res) => {
  try {
    const { tipo = 'todos', busca = '' } = req.query;
    
    let where = {};
    if (tipo !== 'todos') {
      where.tipo_aluno = tipo;
    }
    if (busca) {
      where.nome = { [Op.like]: `%${busca}%` };
    }

    const alunos = await db.Aluno.findAll({
      where,
      order: [['nome', 'ASC']]
    });

    res.render('alunos', { alunos, tipo_filtro: tipo, busca, messages: req.flash() });
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao carregar alunos');
    res.redirect('/dashboard');
  }
});

router.get('/aluno/novo', (req, res) => {
  res.render('aluno_form', { aluno: null, messages: req.flash() });
});

router.post('/aluno/novo', async (req, res) => {
  try {
    const aluno = await db.Aluno.create({
      nome: req.body.nome,
      email: req.body.email,
      telefone: req.body.telefone,
      tipo_aluno: req.body.tipo_aluno,
      matricula_app: req.body.matricula_app,
      modalidade: req.body.modalidade,
      graduacao: req.body.graduacao,
      plano: req.body.plano,
      valor: parseFloat(req.body.valor) || 0,
      status: req.body.status || 'ativo',
      data_nascimento: req.body.data_nascimento || null,
      validade_plano_app: req.body.validade_plano_app || null,
      vencimento: req.body.vencimento || null
    });

    if (aluno.data_nascimento) {
      const eventId = await googleCalendar.criarEventoAniversario(aluno);
      if (eventId) {
        aluno.calendar_event_id = eventId;
        await aluno.save();
      }
    }

    req.flash('success', 'Aluno cadastrado com sucesso!');
    res.redirect('/alunos');
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao cadastrar aluno');
    res.redirect('/aluno/novo');
  }
});

router.get('/aluno/:id/editar', async (req, res) => {
  try {
    const aluno = await db.Aluno.findByPk(req.params.id);
    if (!aluno) {
      req.flash('error', 'Aluno não encontrado');
      return res.redirect('/alunos');
    }
    res.render('aluno_form', { aluno, messages: req.flash() });
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao carregar aluno');
    res.redirect('/alunos');
  }
});

router.post('/aluno/:id/editar', async (req, res) => {
  try {
    const aluno = await db.Aluno.findByPk(req.params.id);
    if (!aluno) {
      req.flash('error', 'Aluno não encontrado');
      return res.redirect('/alunos');
    }

    await aluno.update({
      nome: req.body.nome,
      email: req.body.email,
      telefone: req.body.telefone,
      tipo_aluno: req.body.tipo_aluno,
      matricula_app: req.body.matricula_app,
      modalidade: req.body.modalidade,
      graduacao: req.body.graduacao,
      plano: req.body.plano,
      valor: parseFloat(req.body.valor) || 0,
      status: req.body.status || 'ativo',
      data_nascimento: req.body.data_nascimento || null,
      validade_plano_app: req.body.validade_plano_app || null,
      vencimento: req.body.vencimento || null
    });

    req.flash('success', 'Aluno atualizado com sucesso!');
    res.redirect('/alunos');
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao atualizar aluno');
    res.redirect(`/aluno/${req.params.id}/editar`);
  }
});

router.post('/aluno/:id/excluir', async (req, res) => {
  try {
    const aluno = await db.Aluno.findByPk(req.params.id);
    if (!aluno) {
      req.flash('error', 'Aluno não encontrado');
      return res.redirect('/alunos');
    }

    if (aluno.calendar_event_id) {
      await googleCalendar.deletarEventoAniversario(aluno.calendar_event_id);
    }

    await aluno.destroy();
    req.flash('success', 'Aluno excluído com sucesso!');
    res.redirect('/alunos');
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao excluir aluno');
    res.redirect('/alunos');
  }
});

module.exports = router;
