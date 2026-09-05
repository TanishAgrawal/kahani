from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.tools.agent_tool import AgentTool

from typing import Literal
from pydantic import AnyHttpUrl, BaseModel, Field

from . import tools

class finding(BaseModel):
    title: str
    description: str
    type: Literal["fact", "flow"]
    source: list[AnyHttpUrl] = Field(default_factory=list)

model_name = 'gemini-3.5-flash-lite'

fact_checker = None

try:
    fact_checker = Agent(
        model=model_name,
        name="fact_checker",
        description="Identifies and verifies hard fact of the story",
        instruction="""

        You are a fact checker agent working to identify and then verify
        hard facts from a text which will be given to you. 
        
        Your main task flow is as follows:
            1. Identify the hard facts which are not fictional. These 
                facts include, but are not limited to:
                - dates
                - events
                - facts of the setting and characters (if real)
                - chronology of events

            2. Use the tools provided and verify that those facts are correct.
            3. If not, label them into three different parts:
                - True
                - False
                - Unknown
        
            For each label, provide a few citations (min 2 and max 4). 
            You also have to give a short explanation for the label you put.

        TOOLS
        You have access to "search_fact" tool.
        It takes as input a list of queries and return a list of dictionaries 
        in the following format: 

        [
            {"url":"www.example11.com", "excerpts":"example_excerpts1"}
            {"url":"www.example2.com", "excerpts":"example_excerpts2"}
        ]
        
        
        To use this tool you have to prepare appropriate those search queries
        and call the tool with a list of the queries. These queries
        should be framed as questions for best search. Search for one topic 
        per tool call.

        Finally, use this tool to decide if the fact is true or not.
 
        
        OUTPUT

        Only output the errors, nothing else.Respond with only a JSON 
        array of error objects. If there are no errors, return []. with 
        the following format - 

        [
            {
            "title": "error_title_1", 
            "description": "error_description", 
            "type": "fact",
            "source": 
                [
                "https://example.com/article-1",
                "https://example.com/article-2"
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

try:
    flow_checker = Agent(
        model=model_name,
        name="flow_checker",
        description="Flags logical irregularities in stories",
        instruction="""

        You are a flow checker agent working to identify the logical flow 
        and then flag irregularities in the story which makes it illogical. 
        
        Your main task flow is as follows:
            1. Identify the flow and baseline truths of the story. These 
                include, but are not limited to:
                - Permanent Traits of characters and setting
                - A event by event flow of the story.

            2. Use this information to flag illogical elements in the story.
                Specifically, label them as "Against Flow" with a brief 
                explanation of why you think so.
        
        OUTPUT
        
        Only output the errors, nothing else. Respond with only a JSON 
        array of error objects. If there are no errors, return []. with 
        the following format - 

        [
            {
            "title": "error_title_1", 
            "description": "error_description", 
            "type": "flow",
            }
        ]

        DO NOT include a source field.

        NOTE:
        - Take into account if baseline truths change
        - Take into account if multiple parallel stories are being developed
            in that case segregate them.
        
        - Few examples of illogical element -
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

try:
        report_writer = Agent(
        model=model_name,
        name="report_writer",
        description="Collates a report from provided potential Factual and Logical errors",
        instruction="""

        You are a report writer, and your task is to write a report from 
        the provided information. That information is divided into two parts:
            1. The factual - {fact_findings}
            2. The logical - {flow_findings}
        
        You don't have to change information. You just have to present that 
        in a clean way. Present all the information

        The ONLY instance where you are allowed to modify text is when 
        the factual and the logical part are pointing to the same part. 
        Then what you have to do is combine them. 
        

        """,
    )
except Exception as e:
    print(f"Could not create agent. Check API Key. Error: {e}")

checkers = ParallelAgent(
    name="Checkers",
    sub_agents=[flow_checker, fact_checker],
)

report_pipeline = SequentialAgent(
    name="ReportPipeline",
    sub_agents=[checkers, report_writer],
)

report_tool = AgentTool(agent=report_pipeline)

root_agent = Agent(
    name='coherent',
    model=model_name,
    description='Orchestrates agents, plans and execute.',
    instruction=""" 
    You are the main agent named Coherent for a cinema house who overlooks 
    scriptwriters. Your task is to help the writers write stories which
    are correct both factually as well as logically.

    The way you would do it is by reviewing scences, acts and stories in
    the form of text.

    You only have to answer things related to the uploaded script.

    Yuor main two functions are - 
    1. Create a report after the user uploads/updates a scene and asks for review
    2. Answer the question relating to the story. This includes things like
        the logical flow, facts and reasons for something in the report.

    Here are the tools/agents you have - 
        - 'report_tool' - Outputs the report of the logical and factual errors

    For answering the questions don't re-run the entire report pipeline.
    Instead just use the stored context.

    NOTE-
    - DO NOT answer any question which is out of scope of your function.
        If the user asks such question. Make is clear that it is OUT OF
    """,
    tools=[report_tool],
)