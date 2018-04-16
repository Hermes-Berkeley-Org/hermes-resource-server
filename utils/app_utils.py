from datetime import datetime

def get_curr_semester():
    today = datetime.today()
    month, year = today.month, today.year
    def get_season(month):
        if month < 6:
            return 'SP'
        elif month < 8:
            return 'SU'
        else:
            return 'FA'
    return '{0}{1}'.format(get_season(month), str(year)[-2:])

def partition(cursor, questions_interval):
    def convert_seconds_to_timestamp(ts):
        return '%d:%02d' % (ts // 60, ts % 60)
    partitions = []
    curr_time = 0
    curr_partition = []

    top_questions = list(cursor.clone().limit(5))
    if top_questions:
        partitions.append((top_questions, ('0:00', '0:00')))

    i = 0
    questions = list(cursor)
    while i < len(questions):
        question = questions[i]
        if curr_time <= question['seconds'] < curr_time + questions_interval:
            curr_partition.append(question)
            i += 1
        else:
            if curr_partition:
                partitions.append(
                    (
                        curr_partition,
                        (
                            convert_seconds_to_timestamp(curr_time),
                            convert_seconds_to_timestamp(curr_time + questions_interval)
                        )
                    )
                )
            curr_time += questions_interval
            curr_partition = []
    if curr_partition:
        partitions.append(
            (
                curr_partition,
                (
                    convert_seconds_to_timestamp(curr_time),
                    convert_seconds_to_timestamp(curr_time + questions_interval)
                )
            )
        )
    print(partitions)
    return partitions
