import asyncio
import logging
from typing import Dict, TypedDict

from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent, ParallelAgent
# from google.adk.sessions import InMemorySessionService
# from google.adk.runners import Runner
from google.adk.tools import FunctionTool, AgentTool
from google.adk.tools.tool_context import ToolContext

from typing import Literal
from pydantic import AnyHttpUrl, BaseModel, Field

from . import tools

class finding(BaseModel):
    title: str
    description: str
    type: Literal["fact", "flow"]
    source: list[AnyHttpUrl] = Field(default_factory=list)
    references: list[str] = Field(default_factory=["No References"])

LOG_LEVEL = logging.getLevelName("ERROR")
logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger("Kahani_demo")

# model_name = 'gemini-3.5-flash-lite'
MODEL_COHERENT = "gemini-3.5-flash"
MODEL_FLOW = "gemini-3.8-flash"
MODEL_FACT = "gemini-3.8-flash"
MODEL_REPORT = "gemini-3.5-flash"

#Initiating Fact Checker Agent
try:
    fact_checker = Agent(
        model=MODEL_FACT,
        name="fact_checker",
        description="Identifies and verifies hard fact of the story",
        instruction="""

        INTRODUCTION
        You are a fact checker agent in a cinema house working to identify
        and then verify hard facts from text provided. 
        
        CORE CAPABILITIES
        1. Ability to identify hard facts which are not fictional. These 
            facts include, but are not limited to:
            - dates
            - events
            - facts of the setting and characters (only if real)
            - chronology of events
        2. Ability to use the tools provided and flag factual incorrectness.
        3. Ability to provide reasoning based on the aquired knowledge from tools
            behind the factual incorrectness.
        4. Ability to distinguish need for tool call and relying on your own
            knowledge (limit to only very very basic facts)  

        SUGGESTED TASK FLOW
        1. Identify facts
        2. Verify correctness
        3. Provide final verdict
            if not able to distuingish just mention it in the 
            description as "Worth Checking". Keep these in the end of the
            list. 

        TOOLS
        You have access to "search_fact" tool.
        It takes as input a list of queries and return a list of dictionaries 
        in the following format: 

        [
            {"url":"www.example11.com", "excerpts":"example_excerpts1"}
            {"url":"www.example2.com", "excerpts":"example_excerpts2"}
        ]
        
        
        To use this tool you have to prepare appropriate search queries
        and call the tool with a list of the queries. These queries
        should be framed as questions for best search. Search for one topic 
        per tool call.

        Finally, use this tool to decide if the fact is true or not.
 
        
        OUTPUT
        Only output the errors, nothing else. The errors should be in the
        format of a JSON array of error objects. 
        If there are no errors, return []. 

        For each erorr, provide a few citations (min 2 and max 4).
        Include the refernces from the script (precise quotes) of the error.
        
        From the 10 maximum sources returned by the tool choose
        the most trustable sources according to you. Also, Try to not 
        include urls from the same sources. You are allowed to do so only
        if no other sources are available. 
        
        You also have to give a short explanation for the label you put.
        
        The JSON format is - 
        [
            {
            "title": "error_title_1", 
            "description": "error_description", 
            "type": "fact",
            "source": 
                [
                "https://example.com/article-1",
                "https://example.com/article-2"
                ],
            "references":
                [
                "reference_1",
                "reference_2"
                ]
            }
        ]

        """,
        output_key="fact_findings",
        output_schema=list[finding],
        tools=[tools.search_fact]
    )
except Exception as e:
    print(f"Could not create agent. Check API Key. Error: {e}")

#Initiating Flow Checker Agent
try:
    flow_checker = Agent(
        model=MODEL_FLOW,
        name="flow_checker",
        description="Flags logical irregularities in stories",
        instruction="""

        INTRODUCTION
        You are a flow checker agent working in a cinema house to 
        identify the logical flow of a script and then flag irregularities
        which the story illogical. 
        
        CORE CAPABILITIES
        1. Ability to identify the logical flow the provided script along
            with the baseline truths of the story.These include, but are
            not limited to:
            - Traits of characters and setting 
            - A event by event flow of the story.
        2. Ability to flag illogical elements in the story.
        3. Ability to reason your decision of flagging a part.

        SUGGESTED TASK FLOW
        1. Identify the flow and baseline truths of the story.
        2. Using the info flag illogical elements in the story.
        3. Label them as "Against Flow" with an explanation.
        
        OUTPUT
        Only output the errors, nothing else. The errors should be in the
        format of a JSON array of error objects. 
        If there are no errors, return [].

        Include the refernces from the script (precise quotes) which
        represent the error.
        
        The JSON format is - 

        [
            {
            "title": "error_title_1", 
            "description": "error_description", 
            "type": "flow",
            "references":
                [
                "reference_1",
                "reference_2"
                ]
            }
        ]

        DO NOT include a source field.

        NOTE:
        - Identify when the writer is possibily taking creative liberty.
            This includes things like the change of baseline truths, multiple
            stories running in parallel or a story is being told in a mixed
            chronology for cinematic thrill.
        
        - Few basic examples of illogical element -
            1. Trait continuity
            Baseline: Maya has green eyes.
            Later: "her brown eyes narrowing."
            → Against-flow — eye color changed with no explanation.

            2. Age/timeline math
            Baseline: Jake was born in 2001.
            Later: flashback caption reads "1998 — Jake, age 12."
            → Against-flow — can't be 12 three years before he's born.

            3. Prop introduction
            Baseline: no lighter/smoking habit established for Reyes.
            Later: Reyes pulls out "a battered silver lighter" and lights a cigarette.
            → Against-flow — unintroduced object/habit appears with no setup.

            4. Relationship state
            Baseline: Sarah and Tom meet as strangers at the funeral.
            Later: Tom references "that summer we spent in Portugal together" — years earlier.
            → Against-flow — contradicts "first meeting," unless flagged as an intentional later reveal.

        """,
        output_key="flow_findings",
        output_schema=list[finding],
    )
except Exception as e:
    print(f"Could not create agent. Check API Key. Error: {e}")

##Initiating Report Writing Agent
try:
        report_writer = Agent(
        model=MODEL_REPORT,
        name="report_writer",
        description="Collates a report from provided potential Factual and Logical errors",
        instruction="""

        INTRODUCTION
        You are a report writer for a cinema house and your task is to write
        reports based on the following errors which are flagged in a script:
            1. Factual Error
            2. Logical Error

        CORE CAPABILITIES
        - Write reports with proper headings and segregation of information
        - Ability to identify and modify text when their intended meaning
         is the same

        OUTPUT
        Only output the report text, nothing else.
        
        The report should have the following headings.
        - TITLE (replace with script title - skip not given)
        - INTRODUCTION (Give a small overview of the findings)
        - FACTUAL ERRORS (List the factual errors, skip if not recieved)
        - LOGICAL ERRORS (List the logical errors, skip if not recieved)
        - CONCLUSION (Give 2-3 suggestions on improvement and concluding
                        statements)


        Each Factual and Logical errors should be in the following format - 
        - Title (Heading for the error)
        - Error Description
        - Script References
        - Information Sources (Only for factual errors)

        NOTE
        You don't have to change information. You just have to present that 
        in a clean way. Present all the information.

        The urls should be numbered and listed.

        The ONLY instance where you are allowed to modify text is when 
        the factual and the logical part are pointing to the same part. 
        Then what you have to do is combine them. 
        

        """,
    )
except Exception as e:
    print(f"Could not create agent. Check API Key. Error: {e}")

parallel_tool = AgentTool(
    agent=ParallelAgent(
    name="parallel_checker", 
    sub_agents=[flow_checker, fact_checker]))

report_tool = AgentTool(agent=report_writer)

async def generate_report(script_text: str, tool_context: ToolContext) -> str:
    """Runs Flow Checker + Fact Checker, then writes the final report.

    Args:
        script_text (str): The Script on which the report has to be generated
        tool_context (ToolContext): The context which helps to get session memory

    Returns:
        str: final report with the flow and fact errors 

    """
    
    # Step 1: run both checkers concurrently
    await parallel_tool.run_async(args={"request": script_text}, tool_context=tool_context)

    # Step 2: pull their outputs out of session state
    flow_findings = tool_context.state.get("flow_findings")
    fact_findings = tool_context.state.get("fact_findings")

    # Step 3: build the query yourself
    query = (
        f"Flow findings:\n{flow_findings}\n\n"
        f"Fact findings:\n{fact_findings}\n\n"
        f"Write the report."
    )

    # Step 4: call report writer with that query
    result = await report_tool.run_async(args={"request": query}, tool_context=tool_context)
    return result

report_tool_pipeline = FunctionTool(func=generate_report)

root_agent = Agent(
    name='coherent',
    model=MODEL_COHERENT,
    description='Orchestrates agents, plans and execute.',
    instruction=""" 

    INTRODUCTION
    You are the main agent named Coherent and are a part of the app
    named Kahani. Kahani is built for scriptwriters to elevate their
    writing process.

    Your goal is to help the writers write stories which are correct both
    factually as well as logically. You would also answer questions related
    to the story's facts and logic and find necessary sources.

    CORE CAPABILITIES
    1. Decide which queries are relevant and in scope to answer.
    2. Planning out the events to fulfill relevant user requests.
    3. Search additional sources for an event related to the story.

    MAIN FUNCTIONS
    1. Create a report after the user uploads/updates a scene and asks for review
    2. Answer the question relating to the story. This includes things like
        the logical flow, facts, additional sources and reasons for something in the report.

    SUGGESTED WORKFLOWS

    To generate the report - you would reviewing scences, acts and stories in
    the form of text. Use the "generate_report" tool when generating a fresh
    report.

    To answer questions relating to the story - Answer using your own knowledge
    and context. Additionally for factual matters, if the user is asking
    facts and events use the "search_fact" tool.

    TOOLS
    "generate_report" -
        Outputs the complete report of the logical and factual errors.
    
    "search_fact" -
    
        It takes as input a list of queries and return a list of dictionaries 
        in the following format: 

        [
            {"url":"www.example11.com", "excerpts":"example_excerpts1"}
            {"url":"www.example2.com", "excerpts":"example_excerpts2"}
        ]
        
        To use this tool you have to prepare appropriate search queries
        and call the tool with a list of the queries. These queries
        should be framed as questions for best search. Search for one topic 
        per tool call.

        While using this tool make sure to use only about 3-4 sources.
        Also make sure to not include the same sources whenever possible.

    NOTE-
    - DO NOT answer any question which is out of scope of your function.
        If the user asks such question. Make is clear that it is OUT OF
        SCOPE.

    - Always insist on uploading the story first, so that you can distinguish
        what is relevant and related to the story.

    - Don't re-run the entire report pipeline everytime to answer questions.
    - 
    """,
    tools=[report_tool_pipeline, tools.search_fact]
    # sub_agents=[report_tool],
)

























# checkers = ParallelAgent(
#     name="Checkers",
#     sub_agents=[flow_checker, fact_checker],
# )

# report_tool = SequentialAgent(
#     name="ReportPipeline",
#     sub_agents=[checkers, report_writer],
# )



# APP_NAME = "kahani"
# USER_ID = "user_1"
# SESSION_ID = "session_001"

# session_service = InMemorySessionService()
# runner = Runner(agent=root_agent, app_name=APP_NAME, session_service = session_service)

# async def call_agent_async(query: str) -> None:

#   content = types.Content(role='user', parts=[types.Part(text=query)])

#   final_response_text = "Agent did not produce a final response." # Default

#   async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
      
#       # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

#       if event.is_final_response():
#           if event.content and event.content.parts:
#              # Assuming text response in the first part
#              final_response_text = event.content.parts[0].text
#           elif event.actions and event.actions.escalate: # Handle potential errors/escalations
#              final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
#           # Add more checks here if needed (e.g., specific error codes)
#           break # Stop processing events once the final response is found

#   print(f">>> Query: {query}\n <<< Agent Response: {final_response_text}")

#   async def run_conversation():
#     user_input = input()

#     while user_input != "exit" and user_input:
#         await call_agent_async(user_input,
#                                 runner=runner,
#                                 user_id=USER_ID,
#                                 session_id=SESSION_ID)
#         user_input = input()

# if __name__ == "__main__":
#     try:
#         asyncio.run(run_conversation())
#     except Exception as e:
#         print(f"An error occurred: {e}")

# async def init_session(app_name:str,user_id:str,session_id:str) -> Session:
#     session = await session_service.create_session(
#         app_name=app_name,
#         user_id=user_id,
#         session_id=session_id
#     )
#     print(f"Session created: App='{app_name}', User='{user_id}', Session='{session_id}'")
#     return session

# session = asyncio.run(init_session(APP_NAME,USER_ID,SESSION_ID))

# # --- Runner ---

# runner = Runner(
#     agent=root_agent, # The agent we want to run
#     app_name=APP_NAME,   # Associates runs with our app
#     session_service=session_service # Uses our session manager
# )
# print(f"Runner created for agent '{runner.agent.name}'.")

# from google.genai import types # For creating message Content/Parts
