
class SQLClient:

    def __init__(self, conn):
        self.conn = conn
        self.setup_tables()

    def setup_tables(self):
        cur = self.conn.cursor()
        cur.execute(open('utils/schemas.sql', 'r').read())
        self.conn.commit()
        cur.close()

    def post_question(self, user_email, course_ok_id, lecture_url_name,
                      piazza_question_id, seconds):
        cur = self.conn.cursor()
        cur.execute(
            'EXECUTE post_question (%s, %s, %s, %s, %s)',
            (user_email, course_ok_id, lecture_url_name, piazza_question_id, seconds)
        )
        self.conn.commit()
        cur.close()
