# import ollama

# queries, responses = [], []

# # client = genai.Client(api_key="AIzaSyDNU74cC94jpEWUKqgoIAzWWMaHbEjWMI4")

# query = "What is the time complexity of the Dijkstra-Del Campo Space Partitioning Multi-level Feedback Queue FCFS algorithm?"
# print("Query:", query)

# queries.append(query)

# # response = client.models.generate_content(
# #     model="gemini-2.0-flash",
# #     contents=query,
# # )
# response = ollama.chat(model='llama3.1:8b-instruct-q4_K_M', messages=[
#   {'role': 'user', 'content': query},
# ])
# print("\nResponse:", response['message']['content'])

# responses.append(response)
