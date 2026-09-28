FROM ollama/ollama:latest

COPY entrypoint.sh /usr/local/bin/ollama-entrypoint.sh
# Normalize line endings and ensure executable inside image
RUN sed -i 's/\r$//' /usr/local/bin/ollama-entrypoint.sh \
	&& chmod +x /usr/local/bin/ollama-entrypoint.sh

# Explicitly run through sh to avoid "no such file or directory" caused by CRLF/shebang
ENTRYPOINT ["sh", "/usr/local/bin/ollama-entrypoint.sh"]
