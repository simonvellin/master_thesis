# Base image with Ollama installed
FROM ubuntu:22.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && \
    apt-get install -y curl sudo git python3 python3-pip && \
    apt-get clean

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip3 install --upgrade pip && pip3 install -r /app/requirements.txt

# Copy app and scripts
COPY . /app
WORKDIR /app

# Add startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose Streamlit port
EXPOSE 8501

# Run Ollama + Streamlit from script
CMD ["/app/start.sh"]