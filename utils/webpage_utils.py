from wtforms import Form, BooleanField, StringField, SubmitField, validators
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired

class CreateLectureForm(Form):
    title = StringField('Title')
    date = DateField('Date of Lecture')
    link = StringField('Link to the Lecture')
    submit = SubmitField('Create')
