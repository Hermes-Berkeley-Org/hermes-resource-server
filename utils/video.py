class Video():
    # user = models.ForeignKey('users.User', default=get_current_user)
    #
    # title = models.CharField(max_length=200, null=True, blank=True)
    # description = models.CharField(max_length=500, null=True, blank=True)
    # youtube_url = models.CharField(max_length=255, null=True, blank=True)
    # keywords = models.CharField(max_length=200, null=True, blank=True)
    # file_on_server = models.FileField(max_length=100, null=True, blank=True)

    @property
    def auth_host_name(self):
        return 'localhost'

    @property
    def noauth_local_webserver(self):
        return False

    @property
    def auth_host_port(self):
        return 3000

    @property
    def logging_level(self):
        return 'ERROR'

    @property
    def file(self):
        return self.file_on_server

    @property
    def category(self):
        return 23

    @property
    def privacyStatus(self):
        return 'public'
