from tqdm import tqdm
import backoff
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.parse
import os
import json
from modal import Image
import pandas as pd
import modal
import requests
from unstructured.partition.auto import partition
from unstructured.cleaners.core import group_broken_paragraphs
from pydantic import BaseModel, Field, ValidationError, conint, SkipValidation
from typing import List
from anthropic import Anthropic
from openai import OpenAI
import instructor

# load dotenv
from dotenv import load_dotenv

opus = "claude-3-opus-20240229" #200k context window
sonnet = "claude-3-sonnet-20240229" #200k context window
haiku = "claude-3-haiku-20240307" #200k context window
gpt4turbo = "gpt-4-turbo-2024-04-09" #128k context window
gpt35turbo = "gpt-3.5-turbo-0125" #16k context window

def pull_unstructured():
    import nltk
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')


bright_data_search_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install("libmagic-dev")
    .pip_install('unstructured[all-docs]')
    .pip_install("pandas", "numpy", "urllib3", "requests", "tqdm", "python-dotenv"
                 #"boto3", "pydantic", "typing", "openai", "anthropic", "instructor")
                )
    .apt_install("libgl1-mesa-glx", "libglib2.0-0", "python3-opencv")
    .run_commands("apt-get install -y poppler-utils tesseract-ocr")
    .pip_install("nltk")
    # .run_function(pull_unstructured)
)

stub = modal.Stub("bright_data_search", image=bright_data_search_image)

@stub.function(concurrency_limit=10)
def partition_content(search_results):
    headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '3600',
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'
    }
    def truncate_content(content, max_chars=10000):
        """
        This function takes in a string and truncates it to the first 10000 characters.
        """
        if len(content) > max_chars:
            trunc_content = content[:max_chars] + "... Remaining content truncated. Full length: " + str(len(content)) + " characters."
            return trunc_content
        return content

    current_results = search_results
    organic_results = current_results.get('organic', [])
    if organic_results == []:
        return {
            "full_text": "No organic results found.",
            "individual_results": []
        }

    end_result = []

    for index, search_result in enumerate(organic_results):
        current_result = {}
        try:
            # print(search_result['link'])
            current_result['link'] = search_result['link']
            r = requests.get(search_result['link'], headers, timeout=30)
            content_type = r.headers.get('content-type')
            if 'text/html' in content_type:
                text = requests.get(f"https://r.jina.ai/" + search_result['link'], timeout=30).text
                # elements = partition_html(url=search_result['link'], headers=headers, html_assemble_articles=True, timeout=30)
            else:
                elements = partition(url=search_result['link'], headers=headers, timeout=30)
                text = "\n".join(element.text for element in elements)
            current_result['content'] = group_broken_paragraphs(truncate_content(text)) # might not want to truncate here
        except requests.exceptions.Timeout:
            current_result['content'] = 'Timed out'
        except:
            current_result['content'] = 'Could not access content'
        current_result['article_letter'] = chr(65 + index)
        current_result['link'] = search_result.get("link", "")
        current_result['title'] = search_result.get("title", "")
        current_result['description'] = search_result.get("description", "")
        end_result.append(current_result)
    
    return {
        "full_text": "\n".join([
            f"<doc>\nArticle Letter: {r['article_letter']}\n{r['title']}\n{r['description']}\n{r['content']}\n</doc>"
            for r in end_result
        ]),
        "individual_results": end_result
    }

@backoff.on_exception(backoff.expo, Exception, max_time=120)
def get_search_results(search_query: str):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(
            {'http': os.environ['BRIGHTDATA_SERP_KEY'],
            'https': os.environ['BRIGHTDATA_SERP_KEY']}))
    search_query = urllib.parse.quote_plus(search_query)

    results = json.loads(opener.open(f'http://www.google.com/search?q={search_query}&brd_json=1').read())
    return results

class ArticleScoreandJustification(BaseModel):
    article_letter: str = Field(..., description="The letter of the article (A, B, C, etc.)")
    grade: int = Field(..., description="The score of the article (1-5). If you are NOT CONFIDENT that the content is relevant to the specific project, do not score above 3.")
    justification: str = Field(..., description="The justification for the grade. Use no more than 8 words.")

class ArticleRelevanceScores(BaseModel):
    scores_and_justifications: List[ArticleScoreandJustification]

class RelevanceScoreandJustification(BaseModel):
    score: int = Field(..., description="The score, between 1-5, for whether or not ALL of the content is relevant to the project. If you are not sure, always score 1! there should only be one score generated for a project based on all of the given search results")
    justification: str = Field(..., description="Less than 8 word justification for the score with specific evidence")

class ContentRelevance(BaseModel):
    score_and_justification: List[RelevanceScoreandJustification]

# @backoff.on_exception(backoff.expo, Exception, max_time=30)
def get_relevance_scores(search_query, search_results, plant_info):
    try:
        client = instructor.from_anthropic(Anthropic())
        relevance_scores = client.messages.create(
            model="claude-3-haiku-20240307",
            response_model=ArticleRelevanceScores,
            max_tokens=4096,
            temperature=0,
            messages=[
                {"role": "system", "content": f"You are an expert on public perceptions on large renewable energy projects. "
                f"Your aim is to take a set of search results from Google corresponding "
                f"to the following search query: {search_query} and determine whether or not the search results are "
                f"relevant to our research question. Here are the search results: {search_results}"},
                {"role": "user", "content": f"Based on the title, display link, and description of each URL, we would "
                f"like to identify which search results are most relevant to this research question: 'What is the narrative "
                f"surrounding the development of this renewable energy project in this location, and what evidence of opposition "
                f"or support for the project can be identified?' Score each search result based on the article letter with a number between 1-5, "
                f"with 1 meaning that the article is least relevant and 5 being the most relevant to the research question. "
                f"Here are examples of what might receive the following scores:"
                f"\n1 - an article that does not mention renewable energy or the project in question ({plant_info}), but may have info about a different project or ordinance"
                f"\n2 - an article that might be related to renewable energy near the location in question but does not mention the specific project ({plant_info})"
                f"\n3 - an article that mentions the specific project and location in question ({plant_info}), but only provides basic information about the project and no information on opposition or support"
                f"\n4 - an article that you are EXTREMELY CONFIDENT mentons the exact project and location in question ({plant_info})"
                f"\n5 - an article that you are EXTREMELY CONFIDENT describes the narrative of the specific project development ({plant_info}), including mentions of opposition and support."
                },
            ],
        )
        assert isinstance(relevance_scores, ArticleRelevanceScores)
        return relevance_scores
    except Exception as e:
        print("Error occurred: ", str(e))
        breakpoint()

@backoff.on_exception(backoff.expo, Exception, max_time=30)
def get_content_relevance(search_query, search_results, plant_info):
    client = instructor.from_anthropic((Anthropic))
    relevance_scores = client.messages.create(
        model="claude-3-sonnet-20240229",
        response_model=ContentRelevance,
        max_tokens=4096,
        temperature=0.1,
        messages=[
            {"role": "system", "content": f"You are an expert on public perceptions on large renewable energy projects. "
             f"Your aim is to take a set of search results from Google corresponding "
             f"to the following search query: {search_query} and determine whether or not the search results are "
             f"relevant to our research question. Here are the search results: {search_results}"},
            {"role": "user", "content": f"Based on the description of each URL and other metadata, we would "
             f"like to identify which search results are most relevant to this research question: 'What is the narrative "
             f"surrounding the development of this renewable energy project in this location, and what evidence of opposition "
             f"or support for the project can be identified?' Score all of the search results as a whole with a number between 1-5, "
             f"with 1 meaning that the content is least relevant and 5 being the most relevant to the research question. "
             f"Here are examples of what might receive the following scores:"
             f"\n1 - NONE of the articles mention the specific project {plant_info} or renewable energy near the location, but they might refer to a different project or ordinance"
             f"\n2 - SOME of the articles might be related to renewable energy near the location in question but does not mention the specific project {plant_info}"
             f"\n3 - AT LEAST ONE article mentions the specific project: {plant_info} "
             f"\n4 - MOST of the articles mention the specific project: {plant_info}"
             f"\n5 - MOST of the articles mention the specific project {plant_info}, AND there are also mentions of opposition or support"},
        ],
    )
    assert isinstance(relevance_scores, ContentRelevance)
    return relevance_scores

    
class PerceptionsScoreandSources(BaseModel):
    score: int = Field(..., description="The binary score for the specified question, 1 if evidence is found somewhere in the content and 0 if not")
    sources: str = Field(..., description="Specific article letters that have evidence supporting the score (example: A, B, D), or a brief justification for the score. Use no more than 8 words.")

class ProjectPerceptions(BaseModel):
    mention_support: int = Field(..., description="1 if any mention of support (e.g., an individual or organization mentioned in support of the project), 0 if not")
    mention_opp: int = Field(..., description="1 if any mention of opposition (e.g., an individual or organization mentioned in opposition of the project), 0 if not")
    physical_opp: int = Field(..., description="1 if evidence of physical opposition involving at least one person (e.g., protests, marches, picketing, mass presence at governmental meetings), 0 if not")
    policy_opp: int = Field(..., description="1 if evidence of the use or attempted use of legislation or permitting to block projects, 0 if not")
    legal_opp: int = Field(..., description="1 if evidence of legal challenges and the use of courts to block projects, 0 if not")
    opinion_opp: int = Field(..., description="1 if any opinion-editorials or other media explicitly opposing a project exist, 0 if not")
    # Add binaries for mentions of underlying sources of opposition (e.g., environmental, economic, social, etc.)
    narrative: str = Field(..., description="A one-paragraph narrative summary of the public perceptions of the specified renewable energy project, including the project name, location, and developer, when it was proposed, the public response, and details on any evidence of opposition or support.")

# for content relevance, do an int from 1-5 based on how relevant the content is to the project
# for mention_opp, include a justification for the score
# for everything else, do a binary int score. remove intergov_opp

class ProjectPerceptionsDetailed(BaseModel):
    mention_support: List[PerceptionsScoreandSources] = Field(..., description="A single binary score indicating any mention of support (e.g., an individual or organization mentioned in support of the project), with 1 if mentioned and 0 if not, along with sources.")
    mention_opp: List[PerceptionsScoreandSources] = Field(..., description="A single binary score indicating any mention of opposition (e.g., an individual or organization mentioned in opposition of the project), with 1 if mentioned and 0 if not, along with sources.")
    physical_opp: int = Field(..., description="1 if evidence of physical opposition involving at least one person (e.g., protests, marches, picketing, mass presence at governmental meetings), 0 if not.")
    policy_opp: int = Field(..., description="1 if evidence of the use or attempted use of legislation (like ordinances or moratoria) or permitting to block projects, 0 if not")
    legal_opp: int = Field(..., description="1 if evidence of legal challenges and the use of courts to block projects, 0 if not")
    opinion_opp: int = Field(..., description="1 if any opinion-editorials or other media explicitly opposing a project exist, 0 if not")
    environmental_opp: int = Field(..., description="1 if evidence of environmental concerns, like water, soil, wildlife, and ecological impacts, 0 if not")
    participation_opp: int = Field(..., description="1 if evidence of opposition stemming from a perceived or real lack of participation of fairness in the project, 0 if not")
    tribal_opp: int = Field(..., description="1 if evidence of Tribal opposition, 0 if not")
    health_opp: int = Field(..., description="1 if evidence of opposition from real or perceived health and safety risks from the project, 0 if not")
    intergov_opp: int = Field(..., description="1 if any evidence of disagreement between local, regional, and federal government about the project, 0 if not")
    property_opp: int = Field(..., description="1 if evidence of opposition from real or perceived property value impacts, 0 if not")
    compensation: int = Field(..., description="1 if evidence of support or opposition from real or perceived lack of additional non-required compensation or benefits from the project, 0 if not")
    delay: int = Field(..., description="1 if evidence of a substantial delay (months or years) in project development because of opposition, 0 if not")
    co_land_use: int = Field(..., description="1 if evidence of project co-existing with other land uses, such as agriculture, recreation, and grazing, 0 if not")
    narrative: str = Field(..., description="A 3-4 sentence narrative summary of the public perceptions of the specific renewable energy project, including the project name, location, and developer, when it was proposed, the public response, and details on any evidence of opposition or support. If NO RELEVANT INFO is found, the narrative should be 'No relevant info found.'")

class ProjectPerceptionVariables(BaseModel):
    mention_support: List[SkipValidation[PerceptionsScoreandSources]] = Field(..., description="A single binary score indicating any mention of support (e.g., an individual or organization mentioned in support of the project), with 1 if mentioned and 0 if not, along with sources.")
    mention_opp: List[SkipValidation[PerceptionsScoreandSources]] = Field(..., description="A single binary score indicating any mention of opposition (e.g., an individual or organization mentioned in opposition of the project), with 1 if mentioned and 0 if not, along with sources.")
    physical_opp: int = Field(..., description="1 if evidence of physical opposition involving at least one person (e.g., protests, marches, picketing, mass presence at governmental meetings), 0 if not.")
    policy_opp: int = Field(..., description="1 if evidence of the use or attempted use of legislation (like ordinances or moratoria) or permitting to block projects, 0 if not")
    legal_opp: int = Field(..., description="1 if evidence of legal challenges and the use of courts to block projects, 0 if not")
    opinion_opp: int = Field(..., description="1 if any opinion-editorials or other media explicitly opposing a project exist, 0 if not")
    environmental_opp: int = Field(..., description="1 if evidence of environmental concerns, like water, soil, wildlife, and ecological impacts, 0 if not")
    participation_opp: int = Field(..., description="1 if evidence of opposition stemming from a perceived or real lack of participation of fairness in the project, 0 if not")
    tribal_opp: int = Field(..., description="1 if evidence of tribal opposition from an indigenous community or nation, 0 if not")
    health_opp: int = Field(..., description="1 if evidence of opposition from real or perceived health and safety risks from the project, 0 if not")
    intergov_opp: int = Field(..., description="1 if any evidence of disagreement between local, regional, and federal government about the project, 0 if not")
    property_opp: int = Field(..., description="1 if evidence of opposition from real or perceived property value impacts, 0 if not")
    compensation: int = Field(..., description="1 if evidence of support or opposition from real or perceived lack of additional non-required compensation or benefits from the project (like through a contract or community benefits agreement/CBA), 0 if not")
    delay: int = Field(..., description="1 if evidence of a substantial delay (months or years) in project development because of opposition, 0 if not")
    co_land_use: int = Field(..., description="1 if evidence of project co-existing with other land uses, such as agriculture, recreation, and grazing, 0 if not")
    narrative: str = Field(..., description="A 3-4 sentence narrative summary of the public perceptions of the specific renewable energy project, including the project name, location, and developer, when it was proposed, the public response, and details on any evidence of opposition or support including evidence. If you are confident that NO RELEVANT INFO is found, the narrative should be 'No relevant info found.'")

class ProjectSummary(BaseModel):
    all_scores_and_sources: List[ProjectPerceptionVariables]

#@backoff.on_exception(backoff.expo, Exception, max_time=120)
def get_project_summary(plant_info, content):
    try:
        client = instructor.from_anthropic(Anthropic())
        project_perceptions = client.messages.create(
            model=opus,
            response_model=ProjectSummary,
            max_tokens=4096,
            temperature=0.1,
            messages=[
                {"role": "system", "content": f'You are an expert on public perceptions on large renewable energy projects. Here is the name and location of the project in question ({plant_info}) from which the following search result content is generated: {content}.'},
                {"role": "user", "content": f'Our aim is to understand the public opinion and perceptions of a particular renewable energy project ({plant_info}) based solely on online media evidence from a search engine query on the project. Based on the full text content of all relevant search results, we would like to answer several binary questions about whether or not there is evidence of opposition or support for the project. Use only the text content provided to answer these questions with a “1” if evidence is found and “0” if not, and finally to create a one-paragraph summary of public perceptions of the project. Note that none of the info in the content may be relevant to the project in question, and if so, all integers should be 0 and narrative should be "No relevant info found." Remember: ONLY SCORE 1 if you are EXTREMELY CONFIDENT that there is evidence to support the score for the specific project and location ({plant_info}).'},
            ],
        )
        #if not isinstance(project_perceptions, ProjectSummary):
            # print("Project perceptions is not an instance of ProjectSummary.")
        return project_perceptions
    except Exception as e:
        print("Error occurred: ", str(e))
        breakpoint()
    # except ValidationError as e:
    #     print("Validation error occurred: ", str(e))
    #     breakpoint()
    # except Exception as e:
    #     print("Other error occurred: ", str(e))
    #     breakpoint()


@stub.local_entrypoint()
def main():
    print("This code is running locally!")
    plant_codes = pd.read_csv('ready_to_search.csv')['plant_code']

    plant_codes = [
        pc for pc in plant_codes
        if not os.path.exists(f'results/content/{pc}.json')
    ]

    search_results = []
    for plant_code in plant_codes[:1]:
        with open(f'results/search/{plant_code}.json', 'r') as f:
            search_result = json.load(f)
            search_results.append(search_result)
    
    partitioned_results = partition_content.map(search_results)

    for plant_code, partitioned_result in tqdm(zip(plant_codes, partitioned_results), desc="Processing plant codes"):
        with open(f'results/content/{plant_code}.json', 'w') as f:
            json.dump(partitioned_result, f)

#     df = pd.read_csv('ready_to_search.csv')
#     # run the function remotely on modal
#     # result = search_engine_results.remote(df)
#     print(df.head())
    


if __name__ == "__main__":
    load_dotenv()
    ### CODE BELOW IS FOR RUNNING THE get_search_results FUNCTION IN PARALLEL ###
    # df = pd.read_csv('ready_to_search.csv')
    # queries = list(df['search_query'])
    # plant_codes = list(df['plant_code'])
    
    # code for running the search engine results function in parallel
    # with ThreadPoolExecutor(max_workers=100) as executor:
    #     future_to_plant_code = {executor.submit(get_search_results, query): plant_code
    #                        for plant_code, query in zip(plant_codes, queries)
    #                        if not os.path.exists(f'results/search/{plant_code}.json')}
    #     for future in tqdm(as_completed(future_to_plant_code), total=len(future_to_plant_code)):
    #         plant_code = future_to_plant_code[future]
    #         result = future.result()
    #         with open(f'results/search/{plant_code}.json', 'w') as f:
    #             json.dump(result, f)

    ### CODE BELOW IS FOR RUNNING THE get_relevance_scores FUNCTION IN PARALLEL ###
    # df = pd.read_csv('post_content_plants.csv')
    # plant_codes = list(df['plant_code'])
    # plant_codes = [
    #     pc for pc in plant_codes
    #     if not os.path.exists(f'results/article_relevance/{pc}.json')
    # ]
    # search_queries = [query for code, query in zip(df['plant_code'], df['search_query']) if code in plant_codes]
    # plant_infos = [info for code, info in zip(df['plant_code'], df['plant_info']) if code in plant_codes]

    # def process_plant_code(plant_code, search_query, plant_info):
    #     search_file_path = f'results/search/{plant_code}.json'
    #     with open(search_file_path, 'r') as f:
    #         search_data = json.load(f)
    #         organic_results = search_data.get('organic', [])
    #         if organic_results == []:
    #             return []
    #         formatted_results = []
    #         for index, article in enumerate(organic_results):
    #             formatted_article = f"Article Letter: {article.get('article_letter', 'No article letter')}, Title: {article.get('title', 'No article title')}, Display URL: {article.get('display_link', 'No article display link.')}, Description: {article.get('description', 'No article description.')}"
    #             formatted_results.append(formatted_article)
    #         search_result_string = "<article>" + "</article>\n<article>".join(formatted_results) + "</article>"
    #         return get_relevance_scores(search_query, search_result_string, plant_info)

    # with ThreadPoolExecutor(max_workers=1) as executor:
    #     future_to_plant_code = {
    #         executor.submit(process_plant_code, plant_code, search_query, plant_info): plant_code
    #         for plant_code, search_query, plant_info in zip(plant_codes, search_queries, plant_infos)
    #         if not os.path.exists(f'results/article_relevance/{plant_code}.json')
    #     }
    #     for future in tqdm(as_completed(future_to_plant_code), total=len(future_to_plant_code)):
    #         plant_code = future_to_plant_code[future]
    #         relevance_score = future.result()
    #         if relevance_score == []:
    #             print("Plant code: ", plant_code, " has no organic results.")
    #             with open(f'results/article_relevance/{plant_code}.json', 'w') as f:
    #                 json.dump(relevance_score, f)
    #         else:
    #             # print("Plant code: ", plant_code, " has organic results.")
    #             with open(f'results/article_relevance/{plant_code}.json', 'w') as f:
    #                 json.dump(relevance_score.model_dump(), f)
    

    ### CODE BELOW IS FOR RUNNING THE get_content_relevance FUNCTION IN PARALLEL ###
    # df = pd.read_csv('post_content_plants.csv')
    # plant_codes = list(df['plant_code'])

    # plant_codes = [
    #     pc for pc in plant_codes
    #     if not os.path.exists(f'results/content_relevance/{pc}.json')
    # ]
    # # find the search queries and plant infos for each plant code based on the new list plant_codes
    # search_queries = [query for code, query in zip(df['plant_code'], df['search_query']) if code in plant_codes]
    # plant_infos = [info for code, info in zip(df['plant_code'], df['plant_info']) if code in plant_codes]

    # def process_content_relevance(plant_code, search_query, plant_info):
    #     search_file_path = f'results/search/{plant_code}.json'
    #     # print plant code, search query, and plant info to make sure everything matches up
    #     print(plant_code, search_query, plant_info)
    #     with open(search_file_path, 'r') as f:
    #         search_data = json.load(f)
    #         # print(search_data)
    #         organic_results = search_data.get('organic', [])
    #         if organic_results == []:
    #             print("No organic results found.")
    #             return []
    #         formatted_results = []
    #         for index, article in enumerate(organic_results):
    #             formatted_article = f"Article Letter: {article['article_letter']}, Title: {article['title']}, Display URL: {article['display_link']}, Description: {article['description']}"
    #             formatted_results.append(formatted_article)
    #         search_result_string = "<article>" + "</article>\n<article>".join(formatted_results) + "</article>"
    #         return get_content_relevance(search_query, search_result_string, plant_info)

    # with ThreadPoolExecutor(max_workers=5) as executor:
    #     future_to_plant_code = {
    #         executor.submit(process_content_relevance, plant_code, search_query, plant_info): plant_code
    #         for plant_code, search_query, plant_info in zip(plant_codes[:1], search_queries[:1], plant_infos[:1])
    #         if not os.path.exists(f'results/content_relevance/{plant_code}.json')
    #     }
    #     for future in tqdm(as_completed(future_to_plant_code), total=len(future_to_plant_code)):
    #         plant_code = future_to_plant_code[future]
    #         content_relevance = future.result()
    #         with open(f'results/content_relevance/{plant_code}.json', 'w') as f:
    #             json.dump(content_relevance.model_dump(), f)
    
    
    
    ### CODE BELOW IS FOR RUNNING THE get_project_summary FUNCTION IN PARALLEL ###
    df = pd.read_csv('post_relevance_plants.csv')
    queries = list(df['search_query'])
    plant_codes = list(df['plant_code'])

    plant_codes = [
        pc for pc in plant_codes
        if not os.path.exists(f'results/scores/{pc}.json')
    ]

    plant_infos = [info for code, info in zip(df['plant_code'], df['plant_info']) if code in plant_codes]
    all_content = []
    for plant_code in plant_codes:
        with open(f'results/relevant_content/{plant_code}.json', 'r') as f:
            content = json.load(f)
            all_content.append(content['relevant_content_text'])
    print("Finished appending all content.")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_plant_code = {
            executor.submit(get_project_summary, plant_info, content): plant_code
            for plant_code, plant_info, content in zip(plant_codes, plant_infos, all_content)
            if not os.path.exists(f'results/scores/{plant_code}.json')
        }
        for future in tqdm(as_completed(future_to_plant_code), total=len(future_to_plant_code)):
            plant_code = future_to_plant_code[future]
            summary = future.result()
            with open(f'results/scores/{plant_code}.json', 'w') as f:
                json.dump(summary.model_dump(), f)
    

    
