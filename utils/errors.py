class CreateLectureFormValidationError(ValueError):
    pass

class InvalidLectureLinkError(CreateLectureFormValidationError):
    pass

class VideoParseError(CreateLectureFormValidationError):
    pass

class LectureAlreadyExists(CreateLectureFormValidationError):
    pass

class YoutubeError(ValueError):
    pass

class NoCourseFoundError(ValueError):
    pass

class TranscriptIndexOutOfBoundsError(ValueError):
    pass
