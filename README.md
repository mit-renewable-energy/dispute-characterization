# dispute-characterization
 
 ### All required python (pip install) dependencies:
- dotenv 
- urllib.request
- urllib.parse
- requests
- re
- pandas as pd
- numpy as np
- json
- os
- from tqdm import tqdm
- boto3
- from pydantic import BaseModel, Field
- from typing import List
- from openai import OpenAI
- import instructor
- from unstructured.partition.auto import partition
- from unstructured.partition.html import partition_html
- dotenv.load_dotenv()

### Apt-get/brew install dependencies

### Required secrets/environment variables
- OPENAI_API_KEY
- OPENAI_ORG
- ANTHROPIC_API_KEY
- BRIGHTDATA_SERP_KEY
- AWS_DEFAULT_REGION
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

### possibly needed
- GOOGLE_API_KEY
- PERPLEXITY_API_KEY