from common import new_client
client = new_client()

resp = client.responses.create(
    model="gpt-5-chat-latest",
    input=[{"role":"user","content":"Say hello in one short sentence."}]
)
print(resp.output_text)  # 生成テキスト
print(resp.usage)        # トークン使用量（後述3でも使います）
