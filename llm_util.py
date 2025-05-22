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

# Better structured prompt with examples
prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are an HR evaluator. Based only on the candidate's interview feedback, return a simple and easy-to-understand evaluation in JSON format.\n\n"
     "Use this format:\n"
     "{{\n"
     "  \"decision\": \"Good Fit\" | \"Not Suitable\" | \"Uncertain\",\n"
     "  \"description\": \"2–4 short, clear, non-technical HR-friendly sentences.\"\n"
     "}}\n\n"
     "Rules:\n"
     "- If feedback clearly shows skill alignment → 'Good Fit'\n"
     "- If feedback clearly shows gaps or weak performance → 'Not Suitable'\n"
     "- If feedback is unclear, too short, or contradictory → 'Uncertain'\n"
     "- If the feedback is meaningless (e.g., 'hello world') → 'Not Suitable'\n"
     "- You must only base your evaluation on the feedback, not assume anything.\n"
     "- Do NOT include any explanations outside the JSON.\n\n"
     "Examples:\n\n"
     "Technology: Python\n"
     "Feedback: Excellent understanding of Python concepts, solved all coding problems correctly, good logic.\n"
     "Output:\n"
     "{{\n"
     "  \"decision\": \"Good Fit\",\n"  
     "  \"description\": \"The candidate showed strong understanding of Python and performed well in problem-solving. They are ready for this role.\"\n"
     "}}\n\n"
     "Technology: Python\n"
     "Feedback: Could not answer basic questions. No understanding of programming. Communication was also weak.\n"
     "Output:\n"
     "{{\n"
     "  \"decision\": \"Not Suitable\",\n"
     "  \"description\": \"The candidate lacks the basic skills and communication required for the role. They are not suitable at this time.\"\n"
     "}}\n\n"
     "Now evaluate:\n"
     "Technology: {technology}\n"
     "Feedback: {review}")
])

def evaluate_candidate(technology, review):
    chain = prompt | llm
    for _ in range(2):  # Retry once
        response = chain.invoke({
            "technology": technology,
            "review": review
        })

        raw_content = response.content.strip()
        cleaned_content = re.sub(r"^```json|```$", "", raw_content, flags=re.MULTILINE).strip()

        try:
            result = json.loads(cleaned_content)
            return result['decision'], result['description']
        except Exception:
            continue  # Retry once

    print("⚠️ Failed to parse LLM response:")
    print(raw_content)
    return "Uncertain", "Could not parse LLM response. Please re-evaluate manually."

# Example usage
if __name__ == "__main__":
    technology = ".net"
    review = "not as per requirement,SQL side not good,.net core average,front end no skill"
    decision, description = evaluate_candidate(technology, review)
    print(f"Decision: {decision}\nDescription: {description}")
