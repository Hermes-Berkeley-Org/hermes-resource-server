import psycopg2.extras as extras

class SQLClient:

    def __init__(self, conn):
        self.conn = conn
        self.setup_tables()

    def setup_tables(self):
        cur = self.conn.cursor()
        cur.execute(open('utils/schemas.sql', 'r').read())
        self.conn.commit()
        cur.close()

    def post_question(self, user_email, course_ok_id, lecture_url_name, video_index,
                      piazza_question_id, seconds, identity):
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE post_question (%s, %s, %s, %s, %s, %s, %s)',
            (user_email, course_ok_id, lecture_url_name, video_index,piazza_question_id,
            seconds, identity)
        )
        self.conn.commit()
        cur.close()

    def retrieve_questions_for_timestamp(self, start_second, end_second, course_ok_id, lecture_url_name, video_index):
        cur = self.conn.cursor(cursor_factory=extras.DictCursor)
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
        cur = self.conn.cursor()
        print("here")

        cur.execute(
            'EXECUTE answer_vitamin (%s, %s, %s, %s, %s, %s)',
            (user_email, course_ok_id, answer,lecture_url_name,video_index,vitamin_index)
        )
        self.conn.commit()
        cur.close()


    def watch_video(self,user_email, course_ok_id,lecture_url_name, video_index):
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE watch_video (%s, %s, %s, %s)',
            (user_email, course_ok_id,lecture_url_name, video_index)
        )
        self.conn.commit()
        cur.close()

    def get_lecture_attendence(self, user_email, course_ok_id, lecture_url_name):
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE lecture_attendence(%s, %s,%s,%s)'
        )
