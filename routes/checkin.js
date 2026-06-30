const express = require('express');
const router = express.Router();
const db = require('../models');

router.get('/checkin', (req, res) => {
  res.render('checkin', { messages: req.flash() });
});

router.post('/checkin', async (req, res) => {
  try {
    const { matricula_app, origem, codigo } = req.body;

    const aluno = await db.Aluno.findOne({
      where: { matricula_app, tipo_aluno: origem }
    });

    if (!aluno) {
      req.flash('error', 'Aluno não encontrado!');
      return res.redirect('/checkin');
    }

    if (aluno.validade_plano_app && new Date(aluno.validade_plano_app) < new Date()) {
      req.flash('warning', 'Plano do aluno está vencido!');
    }

    await db.CheckIn.create({
      alunoId: aluno.id,
      origem: origem,
      codigo_verificacao: codigo || ''
    });

    aluno.ultimo_checkin = new Date();
    await aluno.save();

    req.flash('success', `Check-in registrado: ${aluno.nome}`);
    res.redirect('/checkin');
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao registrar check-in');
    res.redirect('/checkin');
  }
});

router.post('/api/checkin', async (req, res) => {
  try {
    const { app, matricula, codigo_verificacao } = req.body;

    if (!app || !matricula) {
      return res.status(400).json({ error: 'Dados incompletos' });
    }

    const aluno = await db.Aluno.findOne({
      where: { matricula_app: matricula, tipo_aluno: app }
    });

    if (!aluno) {
      return res.status(404).json({ error: 'Aluno não encontrado' });
    }

    const checkin = await db.CheckIn.create({
      alunoId: aluno.id,
      origem: app,
      codigo_verificacao: codigo_verificacao || ''
    });

    aluno.ultimo_checkin = new Date();
    await aluno.save();

    res.json({
      success: true,
      aluno: aluno.nome,
      data_checkin: checkin.data_checkin
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Erro ao processar check-in' });
  }
});

module.exports = router;
