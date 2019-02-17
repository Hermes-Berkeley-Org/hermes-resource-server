import os

import psycopg2
from psycopg2 import extras

class SQLClient:

    def __init__(self):
        if not self.initialize_connection():
            raise SQLClientError
        self.setup_tables()

    def initialize_connection(self):
        try:
            self.conn = psycopg2.connect(os.environ.get('SQL_DATABASE_URL'))
            return True
        except psycopg2.Error as e:
            return False

    def get_cursor(self, **cursor_kwargs):
        try:
            return self.conn.cursor(**cursor_kwargs)
        except psycopg2.Error as e:
            if self.initialize_connection():
                return self.conn.cursor(**cursor_kwargs)
            else:
                raise SQLClientError

    def setup_tables(self):
        cur = self.get_cursor()
        cur.execute(open('utils/schemas.sql', 'r').read())
        self.conn.commit()
        cur.close()

    def post_question(self, user_email, course_ok_id, lecture_url_name, video_index,
                      piazza_question_id, seconds, identity):
        cur = self.get_cursor()
        cur.execute(
            'EXECUTE post_question (%s, %s, %s, %s, %s, %s, %s)',
            (user_email, course_ok_id, lecture_url_name, video_index,piazza_question_id,
            seconds, identity)
        )
        self.conn.commit()
        cur.close()

    def retrieve_questions_for_timestamp(self, start_second, end_second, course_ok_id, lecture_url_name, video_index):
        cur = self.get_cursor(cursor_factory=extras.DictCursor)
        query = cur.execute(
            'EXECUTE retrieve_questions_for_timestamp (%s, %s, %s, %s, %s)',
            (start_second, end_second, course_ok_id, lecture_url_name, video_index)
        )
        self.conn.commit()
        rows = cur.fetchall()
        cur.close()
        return rows

    def answer_vitamin(self,user_email,course_ok_id,answer,
                        lecture_url_name, video_index, vitamin_index):
        cur = self.get_cursor()

        cur.execute(
            'EXECUTE answer_vitamin (%s, %s, %s, %s, %s, %s)',
            (user_email, course_ok_id, answer,lecture_url_name,video_index,vitamin_index)
        )
        self.conn.commit()
        cur.close()


    def watch_video(self,user_email, course_ok_id,lecture_url_name, video_index):
        cur = self.get_cursor()
        cur.execute(
            'EXECUTE watch_video (%s, %s, %s, %s)',
            (user_email, course_ok_id,lecture_url_name, video_index)
        )
        self.conn.commit()
        cur.close()

    def get_lecture_attendence(self, user_email, course_ok_id, lecture_url_name):
        cur = self.get_cursor()
        cur.execute(
            'EXECUTE lecture_attendence(%s, %s,%s,%s)'
        )

    def get_answered_vitamins(self, user_email, course_ok_id, lecture_url_name, video_index):
        cur = self.get_cursor(cursor_factory=extras.DictCursor)
        cur.execute(
            'EXECUTE get_answered_vitamins(%s, %s, %s, %s)',
            (user_email, course_ok_id, lecture_url_name, video_index)
        )
        self.conn.commit()
        rows = cur.fetchall()
        cur.close()
        return rows
