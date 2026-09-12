import os
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_openai import ChatOpenAI

from langchain_mcp_adapters.client import (
    MultiServerMCPClient
)

from langgraph.graph import (
    StateGraph,
    MessagesState,
    START,
    END
)

from langgraph.prebuilt import (
    ToolNode,
    tools_condition
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent


MCP_SERVER = (
    BASE_DIR / "mcp_server.py"
)




# ============================================================
# LIFESPAN
#
# Replaces the deprecated @app.on_event("startup") hook.
#
# MultiServerMCPClient opens a session per call, so there is
# no long-lived subprocess to tear down here.
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):


    global mcp_client
    global tools
    global graph


    print()
    print("=" * 60)
    print("Starting Agent Development Workshop")
    print("=" * 60)


    # --------------------------------------------------------
    # MCP CLIENT
    # --------------------------------------------------------

    mcp_client = MultiServerMCPClient({

        "google_tools": {

            "transport": "stdio",

            "command": sys.executable,

            "args": [
                str(MCP_SERVER)
            ],

            # The MCP stdio client forwards only HOME and PATH by
            # default, so GOOGLE_CREDENTIALS_FILE / GOOGLE_TOKEN_FILE
            # would never reach the server. Pass the environment on
            # explicitly.
            "env": dict(os.environ)

        }

    })


    # --------------------------------------------------------
    # LOAD MCP TOOLS
    # --------------------------------------------------------

    tools = await mcp_client.get_tools()


    print()
    print("MCP Tools Loaded:")


    for tool in tools:

        print(
            f"- {tool.name}"
        )


    # --------------------------------------------------------
    # LANGGRAPH
    # --------------------------------------------------------

    workflow = StateGraph(
        MessagesState
    )


    workflow.add_node(
        "agent",
        agent_node
    )


    workflow.add_node(
        "tools",
        ToolNode(tools)
    )


    workflow.add_edge(
        START,
        "agent"
    )


    workflow.add_conditional_edges(

        "agent",

        tools_condition

    )


    workflow.add_edge(
        "tools",
        "agent"
    )


    graph = workflow.compile()


    print()
    print("LangGraph initialized.")

    print()
    print("Server ready.")

    print("=" * 60)
    print()

    yield

    print("Shutting down.")


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Agent Development Workshop",
    lifespan=lifespan
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],                # 5173 4200

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)


# ============================================================
# REQUEST MODEL
# ============================================================

class QueryRequest(BaseModel):

    query: str


# ============================================================
# GLOBALS
# ============================================================

mcp_client = None

tools = []

graph = None


# ============================================================
# LLM
# ============================================================

llm = ChatOpenAI(

    model="gpt-5.5",

    temperature=0

)


# ============================================================
# SHARED FRAGMENTS
# ============================================================

MAIL_WORDS = r"(?:e-?mails?|mails?|messages?|msgs?|inbox|gmail)"

DRIVE_WORDS = r"(?:google\s+drive|g-?drive|drive)"

VERBS = r"(?:search|find|look\s+for|locate|get|show|list|fetch|check|open)"

# A captured value containing any of these is almost certainly a
# mis-capture of the question itself, not a real sender/filename.
JUNK_WORDS = {
    "what", "which", "who", "whom", "whose", "where", "when", "why",
    "how", "do", "does", "did", "i", "me", "my", "mine", "have",
    "has", "had", "is", "are", "was", "were", "any", "all", "there",
    "please", "thanks", "file", "files", "document", "documents",
    "doc", "docs", "email", "emails", "mail", "mails", "message",
    "messages", "anything", "something",
    "search", "find", "show", "list", "get", "open", "fetch",
    "check", "locate", "look", "for",
}

POLITE = re.compile(
    r"[\s,.!?]+(?:please|thanks|thank\s+you|pls)[\s,.!?]*$",
    re.IGNORECASE
)


def clean_value(value):

    """Tidy a captured value and reject obvious mis-captures."""

    if not value:
        return None


    value = POLITE.sub("", value).strip()

    value = value.strip("\"'")

    value = value.rstrip(".,;:!?").strip()

    if not value:
        return None


    words = value.split()

    # A real sender or filename is short. Anything long is a
    # mis-capture of the surrounding sentence.
    if len(words) > 5:
        return None


    # If every word is a stop word, there is no actual target.
    if all(w.lower() in JUNK_WORDS for w in words):
        return None


    return value


# ============================================================
# EXTRACT SENDER
#
# re.search (not re.match): the sender clause need not start the
# sentence, so "show me emails from x" works as well as
# "search emails from x".
# ============================================================

SENDER_PATTERNS = [

    # "... emails from|by <sender>"
    re.compile(
        MAIL_WORDS + r"\b.*?\b(?:from|by|sent\s+by)\s+(.+)",
        re.IGNORECASE
    ),

    # "search gmail|inbox for <sender>"
    re.compile(
        r"\b" + VERBS + r"\s+(?:my\s+|the\s+)?" + MAIL_WORDS +
        r"\s+for\s+(.+)",
        re.IGNORECASE
    ),

    # "<sender>'s emails" / "<sender> emails"
    re.compile(
        r"^(.+?)(?:'s)?\s+" + MAIL_WORDS + r"\s*$",
        re.IGNORECASE
    ),
]

SENDER_TRAILING = re.compile(
    r"\s+(?:in|on|from|within|inside|using)\s+"
    r"(?:my\s+)?(?:google\s+)?(?:gmail|mail|inbox|account)\b.*$",
    re.IGNORECASE
)


def extract_sender(query: str):

    text = query.strip()

    for pattern in SENDER_PATTERNS:

        match = pattern.search(text)

        if not match:
            continue


        sender = SENDER_TRAILING.sub(
            "",
            match.group(1).strip()
        ).strip()

        sender = clean_value(sender)

        if sender:
            return sender


    return None


# ============================================================
# EXTRACT DRIVE QUERY
# ============================================================

DRIVE_PATTERNS = [

    # "... <term> in|on|from (my) drive"
    re.compile(
        r"\b" + VERBS +
        r"\s+(?:for\s+)?(?:me\s+)?(?:all\s+)?(?:my\s+)?"
        r"(.+?)\s+(?:in|on|from)\s+(?:my\s+)?" + DRIVE_WORDS,
        re.IGNORECASE
    ),

    # "... drive for|containing|named|called <term>"
    re.compile(
        r"\b(?:my\s+)?" + DRIVE_WORDS +
        r"\s+(?:for|containing|named|called)\s+(.+)",
        re.IGNORECASE
    ),

    # bare "<term> in drive"
    re.compile(
        r"^(.+?)\s+(?:in|on)\s+(?:my\s+)?" + DRIVE_WORDS,
        re.IGNORECASE
    ),

    # "(search) (my) drive <term>"  e.g. "google drive resume"
    re.compile(
        r"\b(?:" + VERBS + r"\s+)?(?:my\s+)?" + DRIVE_WORDS +
        r"\s+(.+)",
        re.IGNORECASE
    ),
]

# Does the query mention Drive at all?
DRIVE_MENTION = re.compile(
    r"\b" + DRIVE_WORDS + r"\b",
    re.IGNORECASE
)

DRIVE_FILLER = re.compile(
    r"^(?:a|an|the|any|all|some|my|file|files|document|documents"
    r"|doc|docs)\s+",
    re.IGNORECASE
)

# Words that can appear in front of the actual file name once the
# Drive phrase has been stripped, e.g.
#
#   "in google drive search file with name BoardingPass.pdf"
#
# captures "search file with name BoardingPass.pdf". Peel these off
# the front, one token at a time, until a real name is left.
LEADING_NOISE = {
    "search", "searches", "find", "finds", "look", "looking",
    "locate", "get", "show", "list", "fetch", "check", "open",
    "for", "me", "all", "my", "the", "a", "an", "any", "some",
    "in", "on", "from", "with", "having", "whose",
    "file", "files", "document", "documents", "doc", "docs",
    "name", "named", "names", "called", "titled", "title", "is",
    "that", "which",
}


def strip_leading_noise(value):

    """Peel leading filler tokens off a captured file name."""

    tokens = value.split()

    while tokens and tokens[0].lower().strip(":,") in LEADING_NOISE:

        tokens.pop(0)


    return " ".join(tokens)

DRIVE_TRAILING_NOUN = re.compile(
    r"\s+(?:file|files|document|documents|doc|docs)$",
    re.IGNORECASE
)


def extract_drive_query(query: str):

    text = query.strip()

    for pattern in DRIVE_PATTERNS:

        match = pattern.search(text)

        if not match:
            continue


        value = match.group(1).strip()

        # Drop leading filler: "the resume file" -> "resume file".
        while True:

            stripped = DRIVE_FILLER.sub("", value)

            if stripped == value:
                break

            value = stripped


        value = strip_leading_noise(value).strip()

        value = DRIVE_TRAILING_NOUN.sub("", value).strip()

        value = clean_value(value)

        if value:
            return value


    return None


def mentions_drive(query: str):

    return bool(
        DRIVE_MENTION.search(query or "")
    )


# ============================================================
# VALIDATE CONTEXT
# ============================================================

def detect_context(query: str):

    # Drive is checked first: "search my drive for resume" also
    # matches some mail patterns, and the explicit Drive mention
    # is the stronger signal.
    drive_query = extract_drive_query(
        query
    )

    if drive_query:

        return "drive", drive_query


    sender = extract_sender(
        query
    )

    if sender:

        return "gmail", sender


    # Drive was clearly meant, but no file name came through.
    # Say so rather than calling the whole request off-topic.
    if mentions_drive(query):

        return "drive_no_term", None


    return "invalid", None


# ============================================================
# FORMAT TOOL RESULT
#
# MCP tools return a list of content blocks, so str() on the
# raw result leaks "[{'type': 'text', 'text': ...}]" to the
# client. Pull the text out instead.
# ============================================================

def format_tool_result(result):

    if isinstance(result, str):

        return result


    if isinstance(result, dict):

        return str(
            result.get("text", result)
        )


    if isinstance(result, (list, tuple)):

        parts = []

        for block in result:

            if isinstance(block, dict):

                text = block.get("text")

                if text:

                    parts.append(str(text))

                    continue


            text = getattr(block, "text", None)

            if text:

                parts.append(str(text))

            else:

                parts.append(str(block))


        return "\n".join(parts).strip() or str(result)


    text = getattr(result, "text", None)

    if text:

        return str(text)


    return str(result)


# ============================================================
# AGENT NODE
# ============================================================

def agent_node(state: MessagesState):

    response = llm.bind_tools(
        tools
    ).invoke(
        state["messages"]
    )

    return {
        "messages": response
    }


# ============================================================
# STARTUP
# ============================================================

# ============================================================
# QUERY API
# ============================================================

@app.post("/query")
async def query_agent(
    request: QueryRequest
):

    query = request.query.strip()


    if not query:

        return {

            "answer":
                "Invalid context. Please provide a query."

        }


    # ========================================================
    # HARD CONTEXT CHECK
    # ========================================================

    context, value = detect_context(
        query
    )


    # ========================================================
    # INVALID
    # ========================================================

    if context == "drive_no_term":

        print(
            "Drive query with no file name:",
            repr(query)
        )

        return {

            "answer": (
                "I need a file name to search Drive for.\n\n"
                "Try:\n"
                "  search drive for resume\n"
                "  find report in my drive"
            )

        }


    if context == "invalid":

        # Log it: the rejection message alone does not say which
        # query was rejected, which makes this hard to debug.
        print(
            "Unrecognized query:",
            repr(query)
        )

        return {

            "answer": (
                "I could not tell what to search.\n\n"
                "I can search Gmail by sender, or Drive by file name.\n\n"
                "Try:\n"
                "  emails from mohd\n"
                "  emails from someone@example.com\n"
                "  search drive for resume\n"
                "  find report in my drive"
            )

        }


    # ========================================================
    # GMAIL
    # ========================================================

    if context == "gmail":

        tool = next(

            (
                t
                for t in tools
                if t.name == "search_gmail"
            ),

            None

        )


        if tool is None:

            return {

                "answer":
                    "Gmail tool is not available."

            }


        # ----------------------------------------------------
        # DIRECT TOOL CALL
        #
        # This guarantees strict sender behavior.
        #
        # We do NOT ask the LLM to construct the sender.
        # ----------------------------------------------------

        try:

            result = await tool.ainvoke({

                "sender": value

            })


            return {

                "answer": format_tool_result(result)

            }


        except Exception as error:

            print(
                "Gmail error:",
                repr(error)
            )


            return {

                "answer":
                    f"Gmail search failed: {error}"

            }


    # ========================================================
    # GOOGLE DRIVE
    # ========================================================

    if context == "drive":

        tool = next(

            (
                t
                for t in tools
                if t.name == "search_google_drive"
            ),

            None

        )


        if tool is None:

            return {

                "answer":
                    "Google Drive tool is not available."

            }


        try:

            result = await tool.ainvoke({

                "query": value

            })


            return {

                "answer": format_tool_result(result)

            }


        except Exception as error:

            print(
                "Google Drive error:",
                repr(error)
            )


            return {

                "answer":
                    f"Google Drive search failed: {error}"

            }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def home():

    return {

        "message":
            "Agent Development Workshop API",

        "status":
            "online"

    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    import uvicorn


    uvicorn.run(

        app,

        host="0.0.0.0",

        port=8000

    )






