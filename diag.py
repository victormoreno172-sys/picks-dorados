import json, directo
print(json.dumps(directo.draft5("FURIA","BetBoom"),ensure_ascii=False))
print(json.dumps(directo.draft5("BetBoom","FURIA"),ensure_ascii=False))
