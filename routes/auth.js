const express = require('express');
const router = express.Router();
const db = require('../models');

router.get('/login', (req, res) => {
  res.render('login', { messages: req.flash() });
});

router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;
    const usuario = await db.Usuario.findOne({ where: { username } });

    if (usuario && await usuario.validarSenha(password)) {
      req.session.usuario = {
        id: usuario.id,
        username: usuario.username,
        nome: usuario.nome,
        nivel: usuario.nivel
      };
      req.flash('success', 'Login realizado com sucesso!');
      res.redirect('/dashboard');
    } else {
      req.flash('error', 'Usuário ou senha incorretos');
      res.redirect('/login');
    }
  } catch (error) {
    console.error(error);
    req.flash('error', 'Erro ao fazer login');
    res.redirect('/login');
  }
});

router.get('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

module.exports = router;
