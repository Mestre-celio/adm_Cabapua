const bcrypt = require('bcryptjs');

module.exports = (sequelize, DataTypes) => {
  const Usuario = sequelize.define('Usuario', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },
    username: {
      type: DataTypes.STRING(80),
      unique: true,
      allowNull: false
    },
    password_hash: {
      type: DataTypes.STRING(255),
      allowNull: false
    },
    nome: {
      type: DataTypes.STRING(120),
      allowNull: false
    },
    nivel: {
      type: DataTypes.STRING(20),
      defaultValue: 'recepcao'
    },
    email: {
      type: DataTypes.STRING(120)
    }
  }, {
    tableName: 'usuarios',
    hooks: {
      beforeCreate: async (usuario) => {
        if (usuario.password_hash) {
          const salt = await bcrypt.genSalt(10);
          usuario.password_hash = await bcrypt.hash(usuario.password_hash, salt);
        }
      },
      beforeUpdate: async (usuario) => {
        if (usuario.changed('password_hash')) {
          const salt = await bcrypt.genSalt(10);
          usuario.password_hash = await bcrypt.hash(usuario.password_hash, salt);
        }
      }
    }
  });

  Usuario.prototype.validarSenha = async function(senha) {
    return await bcrypt.compare(senha, this.password_hash);
  };

  Usuario.prototype.setSenha = async function(senha) {
    const salt = await bcrypt.genSalt(10);
    this.password_hash = await bcrypt.hash(senha, salt);
  };

  return Usuario;
};
