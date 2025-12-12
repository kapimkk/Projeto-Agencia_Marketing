from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])

class LeadForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    telefone = StringField('Telefone', validators=[DataRequired()])
    projeto = TextAreaField('Projeto')

class ReviewForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    empresa = StringField('Empresa')
    email = StringField('Email', validators=[Email()])
    avaliacao = TextAreaField('Avaliação', validators=[DataRequired(), Length(max=500)])
    estrelas = SelectField('Estrelas', choices=[('1','1'), ('2','2'), ('3','3'), ('4','4'), ('5','5')])