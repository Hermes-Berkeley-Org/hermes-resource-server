from wtforms import Form, BooleanField, StringField, SubmitField, validators
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired
from datetime import datetime

class CreateLectureForm(Form):
    title = StringField('Title', validators=[DataRequired()])
    date = DateField('Date of Lecture', default=datetime.today(), validators=[DataRequired()])
    link = StringField('Link to the Lecture', validators=[DataRequired()])
    submit = SubmitField('Create')

class QuestionForm(Form):
    question = StringField('Question', validators=[DataRequired()])
    timestamp = StringField('Timestamp', validators=[DataRequired()])
    submit = SubmitField('Ask')

class AnswerForm(Form):
    answer = StringField('Answer', validators=[DataRequired()])
    timestamp = StringField('Timestamp', validators=[DataRequired()])
    submit = SubmitField('Ask')

class CreateClassForm(Form):
    class_name = StringField('Class name', validators=[DataRequired()])
    submit = SubmitField('Create class')
