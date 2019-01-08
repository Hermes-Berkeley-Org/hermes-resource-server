DEALLOCATE ALL;

CREATE TABLE IF NOT EXISTS attendance  (
    user_email          varchar NOT NULL,
    course_ok_id        varchar NOT NULL,
    lecture_url_name    varchar NOT NULL
);

CREATE TABLE IF NOT EXISTS piazza_questions  (
    user_email              varchar NOT NULL,
    course_ok_id            varchar NOT NULL,
    lecture_url_name        varchar NOT NULL,
    piazza_question_id      integer NOT NULL,
    seconds                 integer NOT NULL
);

PREPARE post_question AS
  INSERT INTO piazza_questions VALUES ($1, $2, $3, $4, $5);
