
import requests

url = "http://localhost:11434/api/generate"

exit_commands = ["exit", "quit", "bye", "stop"]

print("StudyRAG v1")
print("Type 'exit' to quit.\n")

while True:
    user = input("You: ").strip()
    print("===")
    print("===")
    if user.lower() in exit_commands:
        print("StudyRAG: Goodbye!")
        break

    if not user:
        continue

    data = {
        "model": "qwen3:1.7b",
        "prompt": user,
        "stream": False
    }

    response = requests.post(url, json=data)

    result = response.json()

   


    print("AI:", result["response"])
    print("+==========================================================================+")
