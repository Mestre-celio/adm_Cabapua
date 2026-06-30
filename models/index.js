const { Sequelize } = require('sequelize');
require('dotenv').config();

const sequelize = new Sequelize(process.env.DATABASE_URL || 'sqlite:./ctm_cabapua.db', {
  dialect: process.env.DATABASE_URL && process.env.DATABASE_URL.startsWith('postgres') ? 'postgres' : 'sqlite',
  storage: process.env.DATABASE_URL && process.env.DATABASE_URL.startsWith('postgres') ? undefined : './ctm_cabapua.db',
  logging: process.env.NODE_ENV === 'development' ? console.log : false,
  define: {
    timestamps: true,
    underscored: false
  }
});

const db = {};

db.Sequelize = Sequelize;
db.sequelize = sequelize;

// Importar modelos
db.Usuario = require('./Usuario')(sequelize, Sequelize);
db.Aluno = require('./Aluno')(sequelize, Sequelize);
db.CheckIn = require('./CheckIn')(sequelize, Sequelize);

// Definir relacionamentos
db.Aluno.hasMany(db.CheckIn, { foreignKey: 'alunoId', as: 'checkins', onDelete: 'CASCADE' });
db.CheckIn.belongsTo(db.Aluno, { foreignKey: 'alunoId', as: 'aluno' });

module.exports = db;
