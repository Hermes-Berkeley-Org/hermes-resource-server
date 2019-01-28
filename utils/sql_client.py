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
        cursor = cur.fetchall()
        cur.close()
        return cursor

    def answer_vitamin(self,user_ok_id,course_ok_id, time_answered,answer,
                        video_index, vitamin_index,lecture_url_name):
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE answer_vitamin (%s, %s, %s, %s, %s, %s, %s)',
            (user_ok_id, course_ok_id, time_answered, answer,video_index,
            vitamin_index, lecture_url_name)
        )

    def watch_video(self,user_ok_id, course_ok_id,time_watched,video_index, lecture_url_name):
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE watch_video (%s, %s, %s, %s, %s)',
            (user_ok_id, course_ok_id,time_watched,video_index, lecture_url_name)
        )
