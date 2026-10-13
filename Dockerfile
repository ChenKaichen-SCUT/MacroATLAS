FROM ubuntu:22.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive TZ=UTC LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-8-jdk-headless maven python3 python3-pip ca-certificates \
    libgomp1 zlib1g util-linux && rm -rf /var/lib/apt/lists/*
WORKDIR /artifact
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
FROM runtime AS artifact
COPY . .
RUN chmod +x lib/open-wbo scripts/build.sh && sh scripts/build.sh
CMD ["python3", "scripts/check_results.py"]
