# Use the official Java 8 base image from the Docker Hub
FROM openjdk:8

# Set the working directory inside the container
WORKDIR /app

# Copy your Java application JAR from the bin directory
COPY ./bin/LTL-Learning.jar /app/

# Copy additional file(s) from the lib directory
COPY ./lib/AlloyMax-1.0.3.jar /app/lib/
COPY ./lib/open-wbo /app/lib/

# Specify the command to run your Java application
CMD ["/bin/bash"]
