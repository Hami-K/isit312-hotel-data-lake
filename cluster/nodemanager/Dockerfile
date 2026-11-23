FROM bde2020/hadoop-nodemanager:2.0.0-hadoop3.2.1-java8
# Adds Python 3 so Hadoop Streaming jobs written in Python can run on this NodeManager.
# Debian 9 (stretch) package lists have moved to the archive server.
RUN echo "deb http://archive.debian.org/debian stretch main" > /etc/apt/sources.list \
 && echo "deb http://archive.debian.org/debian-security stretch/updates main" >> /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends python3 \
 && apt-get clean
