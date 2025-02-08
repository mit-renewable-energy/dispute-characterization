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
    .run_function(pull_unstructured)
)

stub = modal.Stub("bright_data_search", image=bright_data_search_image)

@stub.function(concurrency_limit=1000, timeout=1800)
async def partition_content(search_results):
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
        import time
        start_time = time.time()
        timeout_secs = 15
        try:
            # print(search_result['link'])
            current_result['link'] = search_result['link']
            if time.time() - start_time > timeout_secs:
                raise TimeoutError
            r = requests.get(search_result['link'], headers, timeout=10)
            if time.time() - start_time > timeout_secs:
                raise TimeoutError
            content_type = r.headers.get('content-type')
            # print("Content type: ", content_type, "Time elapsed: ", time.time() - start_time)
            if time.time() - start_time > timeout_secs:
                raise TimeoutError
            if 'text/html' in content_type:
                if time.time() - start_time > timeout_secs:
                    raise TimeoutError
                text = requests.get(f"https://r.jina.ai/" + search_result['link'], timeout=10).text
                if time.time() - start_time > timeout_secs:
                    raise TimeoutError
            else:
                if time.time() - start_time > timeout_secs:
                    raise TimeoutError
                # print(f"Not HTML content, current time: {time.time() - start_time}")
                elements = partition(url=search_result['link'], headers=headers, timeout=10, strategy='fast')
                text = "\n".join(element.text for element in elements)
            current_result['content'] = group_broken_paragraphs(truncate_content(text))
        except TimeoutError:
            # print(f"Timed out, current time is {time.time() - start_time}")
            current_result['content'] = 'Timed out'
        except:
            # print(f"Could not access content, current time is {time.time() - start_time}")
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


@stub.local_entrypoint()
async def main():
    print("This code is running locally!")
    plant_codes = pd.read_csv('ready_to_search.csv')['plant_code']

    plant_codes = [
        pc for pc in plant_codes
        if not os.path.exists(f'results/content/{pc}.json')
    ]

    search_results = []
    for plant_code in plant_codes:
        with open(f'results/search/{plant_code}.json', 'r') as f:
            search_result = json.load(f)
            search_results.append(search_result)
    
    # partitioned_results = partition_content.map(search_results)

    # for plant_code, partitioned_result in zip(plant_codes, partitioned_results):
    #     with open(f'results/content/{plant_code}.json', 'w') as f:
    #         json.dump(partitioned_result, f)
    import asyncio
    async def process_partitioned_content(plant_code, search_result):
        partitioned_result = await partition_content.remote.aio(search_result)
        with open(f'results/content/{plant_code}.json', 'w') as f:
            json.dump(partitioned_result, f)

    await asyncio.gather(*[process_partitioned_content(plant_code, search_result) for plant_code, search_result in zip(plant_codes, search_results)])


#     df = pd.read_csv('ready_to_search.csv')
#     # run the function remotely on modal
#     # result = search_engine_results.remote(df)
#     print(df.head())
    


if __name__ == "__main__":
    pass
    
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

    # code for running the get_relenvance_scores function in parallel
    # plant_codes = [
    #     pc for pc in plant_codes
    #     if not os.path.exists(f'results/relevance/{pc}.json')
    # ]

    # def process_plant_code(plant_code, search_query):
    #     search_file_path = f'results/search/{plant_code}.json'
    #     with open(search_file_path, 'r') as f:
    #         search_data = json.load(f)
    #         organic_results = search_data.get('organic', [])
    #         if organic_results == []:
    #             return []
    #         formatted_results = []
    #         for index, article in enumerate(organic_results):
    #             formatted_article = f"Article Letter: {article['article_letter']}, Title: {article['title']}, Display URL: {article['display_link']}, Description: {article['description']}"
    #             formatted_results.append(formatted_article)
    #         search_result_string = "<article>" + "</article>\n<article>".join(formatted_results) + "</article>"
    #         return get_relevance_scores(search_query, search_result_string)

    # with ThreadPoolExecutor(max_workers=5) as executor:
    #     future_to_plant_code = {
    #         executor.submit(process_plant_code, plant_code, df[df['plant_code'] == plant_code]['search_query'].iloc[0]): plant_code
    #         for plant_code in plant_codes
    #         if not os.path.exists(f'results/relevance/{plant_code}.json')
    #     }
    #     for future in tqdm(as_completed(future_to_plant_code), total=len(future_to_plant_code)):
    #         plant_code = future_to_plant_code[future]
    #         relevance_score = future.result()
    #         if relevance_score == []:
    #             with open(f'results/relevance/{plant_code}.json', 'w') as f:
    #                 json.dump(relevance_score, f)
    #         else:
    #             with open(f'results/relevance/{plant_code}.json', 'w') as f:
    #                 json.dump(relevance_score.model_dump(), f)

    # plant_codes = [
    #     pc for pc in plant_codes
    #     if not os.path.exists(f'results/scores/{pc}.json')
    # ]

    # plant_infos = [info for code, info in zip(df['plant_code'], df['plant_info']) if code in plant_codes]
    # all_content = []
    # for plant_code in plant_codes[:1]:
    #     with open(f'results/content/{plant_code}.json', 'r') as f:
    #         content = json.load(f)
    #         all_content.append(content['full_text'])
    # print("Finished appending all content.")
    # with ThreadPoolExecutor(max_workers=10) as executor:
    #     future_to_plant_code = {
    #         executor.submit(get_project_summary, plant_info, content): plant_code
    #         for plant_code, plant_info, content in zip(plant_codes, plant_infos, all_content)
    #         if not os.path.exists(f'results/scores/{plant_code}.json')
    #     }
    #     for future in tqdm(as_completed(future_to_plant_code), total=len(future_to_plant_code)):
    #         plant_code = future_to_plant_code[future]
    #         summary = future.result()
    #         with open(f'results/scores/{plant_code}.json', 'w') as f:
    #             json.dump(summary.model_dump(), f)
    

    
