#!/bin/sh
# Compile both representations against the same backend and dependency versions.
set -eu
cd "$(dirname "$0")/.."
chmod +x lib/open-wbo
mvn -B -ntp -s scripts/maven-settings.xml test org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath \
  -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime
javac -cp lib/AlloyMax-1.0.3.jar -d target/classes scripts/Rq2Translate.java
