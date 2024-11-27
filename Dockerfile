FROM ubuntu:22.04

LABEL author="Tarek ATBI" \
      name="Dockerfile for rest backend containerization" \
      version="v1.0-BETA"

#ADD user
RUN useradd -ms /bin/bash prestodatafetch

#Install image dependencies
RUN apt -y -qq update \
    && apt -y -qq upgrade \
    && apt -y -qq install make gcc g++ \
    && apt-get install -y python3-pip python3-dev python-is-python3 \
    build-essential libssl-dev libffi-dev   libpq-dev curl  default-libmysqlclient-dev pkg-config\
    nano


RUN mkdir /home/prestodatafetch/project/
WORKDIR /home/prestodatafetch/project/
#COPY lib /home/prestodatafetch/project/lib/
COPY conf /home/prestodatafetch/project/conf/



# Install python project requirements file to container

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install -r /home/prestodatafetch/project/conf/requirements.txt 
    
COPY src /home/prestodatafetch/project/src/
RUN mkdir -p /data/apps/temp/
RUN chown -R prestodatafetch:prestodatafetch /home/prestodatafetch/project/
RUN chown -R prestodatafetch:prestodatafetch /home/prestodatafetch/
RUN chown -R prestodatafetch:prestodatafetch /data/apps/temp/

ENV PYTHONPATH="/home/prestodatafetch/project/src:${PYTHONPATH}"
WORKDIR /home/prestodatafetch/project/
USER prestodatafetch
ENTRYPOINT python src/main_rest_entrypoint.py