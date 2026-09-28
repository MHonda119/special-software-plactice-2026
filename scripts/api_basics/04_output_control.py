from common import new_client
client = new_client()

# 4-1 構造化出力（Strict JSON Schema） — Chat Completions API
schema = {
    "name": "place_reco",
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "category": {"type": "string", "enum": ["museum", "shopping", "food", "other"]},
            "nearest_station": {"type": "string"},
            "reason": {"type": "string"}
        },
        "required": ["title", "category", "nearest_station", "reason"],
        "additionalProperties": False
    },
    "strict": True
}
messages =[
        {"role": "system", "content": "You are a helpful assistant that outputs in strict JSON format.\
         JSONにはtitle、category（museum, shopping, food, otherのいずれか）、reason、nearest_stationを含めてください。"},
        {"role": "user", "content": "東京の屋内で、混雑が少ない穴場スポットを出力して**１**つ出力してください"},
    ]
resp_struct = client.chat.completions.create(
    model="gpt-5-chat-latest",
    messages=messages,
    response_format={"type": "json_schema", "json_schema": schema}
)
print("Structured Response:", resp_struct.choices[0].message.content)  # JSON文字列

# 4-2 温度（多様性）と最大出力トークン — Chat Completions API
for i in range(3):
    resp_low_temp = client.chat.completions.create(
        model="gpt-5-chat-latest",
        messages=messages,
        temperature=0,                # 一貫性を高める（低いほど保守的）
        max_tokens=200                  # 出力の上限（応答が長すぎるのを防ぐ）
    )
    print(f"LOW TEMP:{i}", resp_low_temp.choices[0].message.content)

for i in range(3):
    resp_high_temp = client.chat.completions.create(
        model="gpt-5-chat-latest",
        messages=messages,
        temperature=1,
    max_tokens=200
)
    print(f"HIGH TEMP:{i}", resp_high_temp.choices[0].message.content)

for i in range(3):
    resp_high_temp = client.chat.completions.create(
        model="gpt-5-chat-latest",
        messages=messages,
        temperature=2,
    max_tokens=200
)
    print(f"TOO HIGH TEMP:{i}", resp_high_temp.choices[0].message.content)


## Response API での構造化出力はtext.formatでの制御が必要（新しい＝NotStandardな制御方式）
## See reference https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses
