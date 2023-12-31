import os

from pathlib import Path
from dotenv import load_dotenv

from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate
from langchain.pydantic_v1 import BaseModel
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langchain.utilities import SQLDatabase
from langchain.llms import OpenAI

load_dotenv()

# Add the LLM downloaded from Ollama
os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
llm = OpenAI(verbose=False, temperature=0)


db_path = Path(__file__).parent / "retail.db"
rel = db_path.relative_to(Path.cwd())
db_string = f"sqlite:///{rel}"
db = SQLDatabase.from_uri(db_string, sample_rows_in_table_info=2)


def get_schema(_):
    return db.get_table_info()


def run_query(query):
    return db.run(query)


# Prompt

template = """Based on the table schema below, write a SQL query that would answer the user's question:
{schema}

Question: {question}
SQL Query:"""  # noqa: E501
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Given an input question, convert it to a SQL query. No pre-amble."),
        ("human", template),
    ]
)

memory = ConversationBufferMemory(return_messages=True)

# Chain to query with memory

sql_chain = (
    RunnablePassthrough.assign(
        schema=get_schema,
    )
    | prompt
    | llm.bind(stop=["\nSQLResult:"])
    | StrOutputParser()
    | (lambda x: x.split("\n\n")[0])
)


# Chain to answer
template = """Based on the table schema below, question, sql query, and sql response, write a natural language response:
{schema}

Question: {question}
SQL Query: {query}
SQL Response: {response}"""  # noqa: E501
prompt_response = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Given an input question and SQL response, convert it to a natural "
            "language answer. No pre-amble.",
        ),
        ("human", template),
    ]
)


# Supply the input types to the prompt
class InputType(BaseModel):
    question: str


sql_answer_chain = (
    RunnablePassthrough.assign(query=sql_chain).with_types(input_type=InputType)
    | RunnablePassthrough.assign(
        schema=get_schema,
        response=lambda x: db.run(x["query"]),
    )
    | RunnablePassthrough.assign(
        answer=prompt_response | ChatOpenAI() | StrOutputParser()
    )
    | (lambda x: f"Question: {x['question']}\n\nAnswer: {x['answer']}")
)
