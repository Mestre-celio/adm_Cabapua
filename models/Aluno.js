module.exports = (sequelize, DataTypes) => {
  const Aluno = sequelize.define('Aluno', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },
    id_externo: {
      type: DataTypes.STRING(50),
      unique: true
    },
    nome: {
      type: DataTypes.STRING(150),
      allowNull: false
    },
    email: {
      type: DataTypes.STRING(120)
    },
    telefone: {
      type: DataTypes.STRING(20)
    },
    data_nascimento: {
      type: DataTypes.DATEONLY
    },
    data_matricula: {
      type: DataTypes.DATEONLY,
      defaultValue: DataTypes.NOW
    },
    tipo_aluno: {
      type: DataTypes.STRING(30),
      defaultValue: 'particular'
    },
    matricula_app: {
      type: DataTypes.STRING(50)
    },
    validade_plano_app: {
      type: DataTypes.DATEONLY
    },
    ultimo_checkin: {
      type: DataTypes.DATE
    },
    modalidade: {
      type: DataTypes.STRING(50)
    },
    graduacao: {
      type: DataTypes.STRING(50)
    },
    plano: {
      type: DataTypes.STRING(50)
    },
    valor: {
      type: DataTypes.FLOAT
    },
    vencimento: {
      type: DataTypes.DATEONLY
    },
    status: {
      type: DataTypes.STRING(20),
      defaultValue: 'ativo'
    },
    calendar_event_id: {
      type: DataTypes.STRING(100)
    }
  }, {
    tableName: 'alunos'
  });

  return Aluno;
};
