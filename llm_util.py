from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import json
import os
import re

# Load environment variables
load_dotenv()

# Initialize LLM
llm = ChatGroq(api_key=os.getenv('GROQ_API_KEY'), model_name="llama3-8b-8192")

# HR-friendly prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are an HR evaluator. Based on the interview feedback, give a simple and easy-to-understand evaluation.\n"
     "Return ONLY valid JSON in this format:\n"
     "- `decision`: one of ['Good Fit', 'Not Suitable', 'Uncertain']\n"
     "- `description`: your reasoning in 2–4 clear and simple sentences. Avoid technical terms. "
     "Use language that a non-technical HR person can easily understand.\n\n"
     "Respond only in raw JSON. Do not include any explanations, markdown, or formatting outside the JSON.")
])

def evaluate_candidate(technology, review):
    chain = prompt | llm
    response = chain.invoke({
        "technology": technology,
        "review": review
    })

    raw_content = response.content.strip()
    cleaned_content = re.sub(r"^```json|```$", "", raw_content, flags=re.MULTILINE).strip()

    try:
        result = json.loads(cleaned_content)
        return result['decision'], result['description']
    except Exception as e:
        print("⚠️ Failed to parse LLM response:")
        print(raw_content)
        return "Uncertain", "Could not parse LLM response. Please re-evaluate manually."

# Example usage
if __name__ == "__main__":
    technology = "AIML"
    review = "Python programming poor understanding , no aiml knowledge no technical skills ."
    decision, description = evaluate_candidate(technology, review)
    print(f"Decision: {decision}\nDescription: {description}")
