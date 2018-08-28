FROM ubuntu:latest
MAINTAINER Ajay Raj "araj@berkeley.edu"
RUN apt-get update -y
RUN apt-get install -y python3 python3-dev python3-pip nginx
COPY . /app
WORKDIR /app
RUN pip3 install -r requirements.txt
RUN python3 -m nltk.downloader stopwords
ENTRYPOINT ["python3"]
CMD ["app.py"]
