from langgraph.prebuilt import create_react_agent
from core.llm import get_llm
from .prompts import KAREN_PROMPT
from .tools import create_word_document, create_excel_spreadsheet, create_powerpoint

karen_agent = create_react_agent(
    model=get_llm(),
    tools=[create_word_document, create_excel_spreadsheet, create_powerpoint],
    prompt=KAREN_PROMPT,
)
