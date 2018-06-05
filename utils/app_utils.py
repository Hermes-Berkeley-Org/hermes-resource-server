from datetime import datetime
from operator import itemgetter

def edit_distance(s1, s2):
    def diff(i, j):
        return 0 if i == j else 1
    def get_char(s, i):
        return s[i - 1]

    m, n = len(s1), len(s2)

    E = [[0 for _ in range(n+1)] for _ in range(m+1)]

    for i in range(m + 1):
        E[i][0] = i

    for j in range(n + 1):
        E[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            E[i][j] = min(
                E[i - 1][j] + 1,
                E[i][j - 1] + 1,
                E[i - 1][j - 1] + diff(get_char(s1, i), get_char(s2, j))
            )

    return E[m][n]


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

def sort_suggestions(suggestions):
    return map(itemgetter(0), sorted(suggestions, key=itemgetter(1)))

def partition(cursor, questions_interval, duration):
    duration = convert_timestamp_to_seconds(duration)
    partitions = []
    curr_time = 0
    curr_partition = []


    by_time = list(cursor.sort([('seconds', 1)]))
    # by_time = time_cursor.sort([('seconds', 1)])

    top_questions = sorted(by_time, key=lambda document: -len(document['upvotes']))[:5]
    if top_questions:
        partitions.append((top_questions, ('0:00', '0:00')))

    i = 0
    low_questions = [question for question in by_time if question not in top_questions]
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
