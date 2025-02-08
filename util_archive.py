from pydantic import BaseModel, Field
from typing import List
from anthropic import Anthropic
from openai import OpenAI
import instructor

class PerceptionsScore(BaseModel):
    score: int = Field(..., description="The score for the specified binary question, 1 if evidence is found and 0 if not")
    justification: str = Field(..., description="Less than 8 word justification for the score, including any article letters (example: A, C, D) with specific evidence that support the score")

class ProjectPerceptions(BaseModel):
    mention_support: int = Field(..., description="1 if any mention of support (e.g., an individual or organization mentioned in support of the project), 0 if not")
    mention_opp: int = Field(..., description="1 if any mention of opposition (e.g., an individual or organization mentioned in opposition of the project), 0 if not")
    physical_opp: int = Field(..., description="1 if evidence of physical opposition involving at least one person (e.g., protests, marches, picketing, mass presence at governmental meetings), 0 if not")
    policy_opp: int = Field(..., description="1 if evidence of the use or attempted use of legislation or permitting to block projects, 0 if not")
    legal_opp: int = Field(..., description="1 if evidence of legal challenges and the use of courts to block projects, 0 if not")
    opinion_opp: int = Field(..., description="1 if any opinion-editorials or other media explicitly opposing a project exist, 0 if not")
    # Add binaries for mentions of underlying sources of opposition (e.g., environmental, economic, social, etc.)
    narrative: str = Field(..., description="A one-paragraph narrative summary of the public perceptions of the specified renewable energy project, including the project name, location, and developer, when it was proposed, the public response, and details on any evidence of opposition or support.")

class ProjectPerceptionsDetailed(BaseModel):
    content_relevance: List[PerceptionsScore] = Field(..., description="A score indicating if any of the content is relevant to the renewable energy project in question, with 1 if relevant and 0 if not, along with justifications.")
    mention_support: List[PerceptionsScore] = Field(..., description="A score indicating any mention of support (e.g., an individual or organization mentioned in support of the project), with 1 if mentioned and 0 if not, along with justifications.")
    mention_opp: List[PerceptionsScore] = Field(..., description="A score indicating any mention of opposition (e.g., an individual or organization mentioned in opposition of the project), with 1 if mentioned and 0 if not, along with justifications.")
    physical_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of physical opposition involving at least one person (e.g., protests, marches, picketing, mass presence at governmental meetings), with 1 if evidence is found and 0 if not, along with justifications.")
    policy_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of the use or attempted use of legislation (like ordinances or moratoria) or permitting to block projects, with 1 if evidence is found and 0 if not, along with justifications.")
    legal_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of legal challenges and the use of courts to block projects, with 1 if evidence is found and 0 if not, along with justifications.")
    opinion_opp: List[PerceptionsScore] = Field(..., description="A score indicating any opinion-editorials or other media explicitly opposing a project, with 1 if evidence is found and 0 if not, along with justifications.")
    environmental_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of environmental concerns, like water, soil, wildlife, and ecological impacts, with 1 if evidence is found and 0 if not, along with justifications.")
    participation_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of opposition stemming from a perceived or real lack of participation or fairness in the project, with 1 if evidence is found and 0 if not, along with justifications.")
    tribal_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of Tribal opposition, with 1 if evidence is found and 0 if not, along with justifications.")
    health_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of opposition from real or perceived health and safety risks from the project, with 1 if evidence is found and 0 if not, along with justifications.")
    intergov_opp: List[PerceptionsScore] = Field(..., description="A score indicating any evidence of disagreement between local, regional, and federal government about the project, with 1 if evidence is found and 0 if not, along with justifications.")
    property_opp: List[PerceptionsScore] = Field(..., description="A score indicating evidence of opposition from real or perceived property value impacts, with 1 if evidence is found and 0 if not, along with justifications.")
    compensation: List[PerceptionsScore] = Field(..., description="A score indicating evidence of support or opposition from real or perceived lack of additional non-required compensation or benefits from the project, with 1 if evidence is found and 0 if not, along with justifications.")
    delay: List[PerceptionsScore] = Field(..., description="A score indicating evidence of a substantial delay (months or years) in project development because of opposition, with 1 if evidence is found and 0 if not, along with justifications.")
    co_land_use: List[PerceptionsScore] = Field(..., description="A score indicating evidence of project co-existing with other land uses, such as agriculture, recreation, and grazing, with 1 if evidence is found and 0 if not, along with justifications.")
    narrative: str = Field(..., description="A 3-4 sentence narrative summary of the public perceptions of the specified renewable energy project, including the project name, location, and developer, when it was proposed, the public response, and details on any evidence of opposition or support.")

class ProjectSummary(BaseModel):
    scores: List[ProjectPerceptions]


class ArticleScore(BaseModel):
    article_letter: str = Field(..., description="The letter of the article (A, B, C, etc.)")
    grade: int = Field(..., description="The grade of the article (1-5)")
    justification: str = Field(..., description="The justification for the grade. Use no more than 8 words.")

class RelevanceScores(BaseModel):
    scores: List[ArticleScore]
