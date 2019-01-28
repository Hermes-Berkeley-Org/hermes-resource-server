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
    video_index             integer NOT NULL,
    piazza_question_id      varchar NOT NULL,
    seconds                 integer NOT NULL,
    identity                varchar NOT NULL
);

PREPARE post_question AS
  INSERT INTO piazza_questions VALUES ($1, $2, $3, $4, $5, $6, $7);

PREPARE retrieve_questions_for_timestamp as
  SELECT * FROM piazza_questions WHERE seconds >= $1 AND seconds <= $2 AND course_ok_id=($3) AND lecture_url_name=($4) AND video_index=($5);
