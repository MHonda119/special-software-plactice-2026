from common import new_client
client = new_client()

user_q = "雨でも楽しめて、混雑が少ない穴場は？"

messages  = [
    {"role":"system","content":"You are a friendly assistant that answers concisely."},
    {"role":"user","content":"今日は東京で何をすると良い？屋内で。"},
    {"role":"assistant","content":"美術館や科学館、ショッピングモールなどはいかがでしょう。"}
]

messages.append({"role":"user","content":"雨でも楽しめて、混雑が少ない穴場は？"})

# resp = client.responses.create(model="gpt-5-chat-latest", input=history)
resp = client.chat.completions.create(
    model="gpt-5-chat-latest",
    messages=messages,
)

reply = resp.choices[0].message.content
messages.append({"role": "assistant", "content": reply})

usage = getattr(resp, "usage", None)
pt = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", None))
ct = getattr(usage, "completion_tokens", getattr(usage, "output_tokens", None))
tt = getattr(usage, "total_tokens", None)

print("User:", user_q)
print("Assistant:", reply)
print(f"[usage] prompt={pt} completion={ct} total={tt}")
