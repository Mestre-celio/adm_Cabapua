module.exports = (sequelize, DataTypes) => {
  const CheckIn = sequelize.define('CheckIn', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },
    alunoId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: 'alunos',
        key: 'id'
      }
    },
    data_checkin: {
      type: DataTypes.DATE,
      defaultValue: DataTypes.NOW
    },
    origem: {
      type: DataTypes.STRING(30)
    },
    codigo_verificacao: {
      type: DataTypes.STRING(50)
    }
  }, {
    tableName: 'checkins'
  });

  return CheckIn;
};
