FROM flink:1.20.1

# Get JARs
RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-kafka/3.4.0-1.20/flink-connector-kafka-3.4.0-1.20.jar && \ 
    wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/kafka/kafka-clients/3.4.0/kafka-clients-3.4.0.jar

# Install python3 and pip3
RUN apt-get update -y && \
    apt-get install -y python3 python3-pip python3-dev && rm -rf /var/lib/apt/lists/*
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install Java
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk build-essential git maven && \
    apt-get clean

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Install Pemja
#RUN git clone https://github.com/alibaba/pemja.git /opt/pemja && \
#    cd /opt/pemja && \
#    pip3 install .

# Install PyFlink

RUN pip3 install apache-flink==1.20.1
RUN pip3 install ujson opencv-python ollama requests
