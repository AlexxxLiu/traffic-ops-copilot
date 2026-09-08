"""Verify LLM connectivity before wiring the graph."""
from dotenv import load_dotenv
load_dotenv()

from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=200)
resp = llm.invoke("Reply with exactly: TOOLS-READY")
print(resp.content)