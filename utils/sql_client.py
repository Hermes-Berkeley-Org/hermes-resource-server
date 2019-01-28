
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
        print("here")
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE post_question (%s, %s, %s, %s, %s, %s, %s)',
            (user_email, course_ok_id, lecture_url_name, video_index,piazza_question_id,
            seconds, identity)
        )
        self.conn.commit()
        print("emitted")
        cur.close()

    def retrieve_questions_for_timestamp(self, start_second, end_second, course_ok_id, lecture_url_name, video_index):
        cur = self.conn.cursor()
        query = cur.execute(
            'EXECUTE retrieve_questions_for_timestamp (%s, %s, %s, %s, %s)',
            (start_second, end_second, course_ok_id, lecture_url_name, video_index)
        )
        self.conn.commit()
        cursor  = cur.fetchall()
        cur.close()
        return cursor
