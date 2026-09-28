#!/bin/sh
set -e

# サーバーをバックグラウンドで起動
echo "Starting Ollama server in background..."
ollama serve &
OLLAMA_PID=$!

# サーバーの起動待ち
for i in $(seq 1 20); do
	if ollama list >/dev/null 2>&1; then
		break
	fi
	echo "Waiting for Ollama server to be ready... ($i)"
	sleep 1
done

# モデルをpull
echo "Pulling gemma3:270m..."
ollama pull gemma3:270m

# バックグラウンドのサーバーを停止
kill $OLLAMA_PID
sleep 2

# フォアグラウンドでサーバー起動
echo "Starting Ollama server (foreground)"
exec ollama serve
