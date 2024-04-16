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
from pydantic import BaseModel, Field
from typing import List
from anthropic import Anthropic
import instructor


def pull_unstructured():
    pass
# downlaod punkt stuff here


bright_data_search_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install("libmagic-dev")
    .pip_install('unstructured[all-docs]')
    .pip_install("pandas", "numpy", "urllib3", "requests", "tqdm", "python-dotenv"
                 #"boto3", "pydantic", "typing", "openai", "anthropic", "instructor")
                )
    .apt_install("libgl1-mesa-glx", "libglib2.0-0", "python3-opencv")
    .run_function(pull_unstructured)
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

    end_result = []

    for search_result in tqdm(organic_results):
        current_result = {}
        try:
            # print(search_result['link'])
            current_result['link'] = search_result['link']
            r = requests.get(search_result['link'], headers, timeout=30)
            content_type = r.headers.get('content-type')
            if 'text/html' in content_type:
                text = requests.get(f"https://r.jina.ai/" + search_result['link']).text
                # elements = partition_html(url=search_result['link'], headers=headers, html_assemble_articles=True, timeout=30)
            else:
                elements = partition(url=search_result['link'], headers=headers, timeout=30)
                text = "\n".join(element.text for element in elements)
            # add text to new 'content' in ['organic'] such that it updates in sample_25
            current_result['content'] = group_broken_paragraphs(truncate_content(text))
        except requests.exceptions.Timeout:
            current_result['content'] = 'Timed out'
        except:
            current_result['content'] = 'Could not access content'
        current_result['title'] = search_result.get("title", "")
        current_result['description'] = search_result.get("description", "")
        end_result.append(current_result)
    
    return {
        "full_text": "\n\n========================\n\n".join([
            f"{r['title']}\n{r['description']}\n{r['content']}"
            for r in end_result
        ]),
        "individual_results": end_result
    }

@backoff.on_exception(backoff.expo, Exception, max_time=120)
def get_search_results(search_query: str):
    # if row['search_query'] != 'initial' or pd.isnull(row['result']):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(
            {'http': os.environ['BRIGHTDATA_SERP_KEY'],
            'https': os.environ['BRIGHTDATA_SERP_KEY']}))
    search_query = urllib.parse.quote_plus(search_query)

    results = json.loads(opener.open(f'http://www.google.com/search?q={search_query}&brd_json=1').read())
    return results

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
    mention_support: int = Field(..., description="1 if any mention of support (e.g., an individual or organization mentioned in support of the project), 0 if not")
    mention_opp: int = Field(..., description="1 if any mention of opposition (e.g., an individual or organization mentioned in opposition of the project), 0 if not")
    # binaries for expressions of opposition
    physical_opp: int = Field(..., description="1 if evidence of physical opposition involving at least one person (e.g., protests, marches, picketing, mass presence at governmental meetings), 0 if not")
    policy_opp: int = Field(..., description="1 if evidence of the use or attempted use of legislation (like ordinances or moratoria) or permitting to block projects, 0 if not")
    legal_opp: int = Field(..., description="1 if evidence of legal challenges and the use of courts to block projects, 0 if not")
    opinion_opp: int = Field(..., description="1 if any opinion-editorials or other media explicitly opposing a project exist, 0 if not")
    # binaries for underlying sources of opposition (e.g., environmental, economic, social, etc.)
    environmental_opp: int = Field(..., description="1 if evidence of environmental concerns, like water, soil, wildlife, and ecological impacts, 0 if not")
    participation_opp: int = Field(..., description="1 if evidence of opposition stemming from a perceived or real lack of participation of fairness in the project, 0 if not")
    tribal_opp: int = Field(..., description="1 if evidence of Tribal opposition, 0 if not")
    health_opp: int = Field(..., description="1 if evidence of opposition from real or perceived health and safety risks from the project, 0 if not")
    intergov_opp: int = Field(..., description="1 if any evidence of disagreement between local, regional, and federal government about the project, 0 if not")
    property_opp: int = Field(..., description="1 if evidence of opposition from real or perceived property value impacts, 0 if not")
    # binaries for additional compensation (CBAs) and delays
    compensation: int = Field(..., description="1 if evidence of support or opposition from real or perceived lack of additional non-required compensation or benefits from the project, 0 if not")
    delay: int = Field(..., description="1 if evidence of a substantial delay (months or years) in project development because of opposition, 0 if not")
    co_land_use: int = Field(..., description="1 if evidence of project co-existing with other land uses, such as agriculture, recreation, and grazing, 0 if not")
    narrative: str = Field(..., description="A one-paragraph narrative summary of the public perceptions of the specified renewable energy project, including the project name, location, and developer, when it was proposed, the public response, and details on any evidence of opposition or support.")


class ProjectSummary(BaseModel):
    scores: List[ProjectPerceptionsDetailed]

@backoff.on_exception(backoff.expo, Exception, max_time=120)
def get_project_summary(plant_info, content):
    client = instructor.from_anthropic(Anthropic())
    project_perceptions = client.messages.create(
        model="claude-3-haiku-20240307",
        response_model=ProjectSummary,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": f'Our aim is to understand the public opinion and perceptions of a particular renewable energy project based solely on online media evidence from a search engine query on the project. Based on the full text content of all search results, we would like to answer several binary questions about whether or not there is evidence of opposition or support for the project. Use only the text content provided to answer these questions with a “1” if evidence is found and “0” if not, and finally to create a one-paragraph summary of public perceptions of the project. Note that none of the info in the content may be relevant to the project in question, and if so, all integers should be 0 and narrative should be "No relevant info found.".'},
            {"role": "user", "content": f"Here is the name and location of the project in question ({plant_info}) from which the following search result content is generated: {content}"}
        ],
    )
    assert isinstance(project_perceptions, ProjectSummary)
    return project_perceptions


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

    for plant_code, partitioned_result in zip(plant_codes, partitioned_results):
        with open(f'results/content/{plant_code}.json', 'w') as f:
            json.dump(partitioned_result, f)

#     df = pd.read_csv('ready_to_search.csv')
#     # run the function remotely on modal
#     # result = search_engine_results.remote(df)
#     print(df.head())
    


if __name__ == "__main__":
    
    df = pd.read_csv('ready_to_search.csv')
    queries = list(df['search_query'])
    plant_codes = list(df['plant_code'])
    
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

    plant_codes = [
        pc for pc in plant_codes
        if not os.path.exists(f'results/scores/{pc}.json')
    ]

    plant_infos = [info for code, info in zip(df['plant_code'], df['plant_info']) if code in plant_codes]
    all_content = []
    for plant_code in plant_codes[:1]:
        with open(f'results/content/{plant_code}.json', 'r') as f:
            content = json.load(f)
            all_content.append(content['full_text'])

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_plant_code = {
            executor.submit(get_project_summary, plant_info, content): plant_code
            for plant_code, plant_info, content in zip(plant_codes, plant_infos, all_content)
            if not os.path.exists(f'results/scores/{plant_code}.json')
        }
        for future in as_completed(future_to_plant_code):
            plant_code = future_to_plant_code[future]
            summary = future.result()
            with open(f'results/scores/{plant_code}.json', 'w') as f:
                json.dump(summary.model_dump_json(), f)
    

    
