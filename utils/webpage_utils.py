from wtforms import Form, BooleanField, StringField, SubmitField, validators
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired

class CreateLectureForm(Form):
    title = StringField('Title', validators=[DataRequired()])
    date = DateField('Date of Lecture', validators=[DataRequired()])
    link = StringField('Link to the Lecture', validators=[DataRequired()])
    submit = SubmitField('Create')
