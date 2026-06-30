function isAuthenticated(req, res, next) {
  if (req.session && req.session.usuario) {
    return next();
  }
  req.flash('error', 'Você precisa fazer login para acessar esta página');
  res.redirect('/login');
}

function isAdmin(req, res, next) {
  if (req.session && req.session.usuario && req.session.usuario.nivel === 'admin') {
    return next();
  }
  req.flash('error', 'Acesso restrito a administradores');
  res.redirect('/dashboard');
}

module.exports = { isAuthenticated, isAdmin };
