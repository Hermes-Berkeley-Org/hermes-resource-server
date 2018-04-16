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

def convert_seconds_to_timestamp(seconds):
    return '%d:%02d' % (seconds // 60, seconds % 60)

def convert_timestamp_to_seconds(ts):
    data = ts.split(':')
    hours = data[0]
    minutes = data[1]
    seconds = data[2]
    return (int(hours) * 360 + int(minutes) * 60 + int(seconds))

def partition(cursor, questions_interval, duration):
    duration = convert_timestamp_to_seconds(duration)
    partitions = []
    curr_time = 0
    curr_partition = []

    questions = list(cursor)

    top_questions = questions[:5]
    if top_questions:
        partitions.append((top_questions, ('0:00', '0:00')))

    i = 0
    low_questions = questions[5:]
    while i < len(low_questions):
        question = low_questions[i]
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
                    convert_seconds_to_timestamp(min(curr_time + questions_interval, duration))
                )
            )
        )
    return partitions


def generate_partition_titles(duration, interval):
    duration = convert_timestamp_to_seconds(duration)
    curr = 0
    while curr + interval < duration:
        yield (convert_seconds_to_timestamp(curr), convert_seconds_to_timestamp(curr + interval))
        curr = curr + interval
    yield (convert_seconds_to_timestamp(curr), convert_seconds_to_timestamp(duration))
