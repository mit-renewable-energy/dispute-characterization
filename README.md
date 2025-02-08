# Renewable Energy Project Dispute Characterization

This codebase analyzes public perceptions of renewable energy projects (solar and wind) by generating search results, scraping content, scoring relevance, and summarizing findings using LLMs and various APIs.

## Table of Contents
- [Dependencies](#dependencies)
- [Environment Setup](#environment-setup)
- [Data Sources](#data-sources)
- [Process Steps](#process-steps)
- [File Structure](#file-structure)
- [Visualization](#visualization)

## Dependencies

### Python Packages

### System Dependencies

```bash
# For Ubuntu/Debian
apt-get install libmagic-dev libgl1-mesa-glx libglib2.0-0 python3-opencv poppler-utils tesseract-ocr

# For MacOS
brew install libmagic poppler tesseract
```

## Environment Setup

Create a `.env` file with the following API keys:

```
OPENAI_API_KEY=<your-key>
OPENAI_ORG=<your-org>
ANTHROPIC_API_KEY=<your-key>
BRIGHTDATA_SERP_KEY=<your-key>
AWS_DEFAULT_REGION=<region>
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-key>
```

## Data Sources

- EIA 2022 dataset containing renewable energy project information
- Input files needed:
  - `ready_to_search.csv`: Contains plant codes, search queries, and plant info
  - `post_content_plants.csv`: Used for relevance scoring
  - `post_relevance_plants.csv`: Used for final analysis

## Process Steps

### 1. Generate Search Results
**File**: `search.py`
**Function**: `get_search_results()`

This step uses BrightData to generate Google search results for each project.

```python
# Uncomment in search.py main():
df = pd.read_csv('ready_to_search.csv')
queries = list(df['search_query'])
plant_codes = list(df['plant_code'])

with ThreadPoolExecutor(max_workers=100) as executor:
    future_to_plant_code = {executor.submit(get_search_results, query): plant_code
                       for plant_code, query in zip(plant_codes, queries)
                       if not os.path.exists(f'results/search/{plant_code}.json')}
```

**Output**: `results/search/{plant_code}.json`

### 2. Content Scraping
**File**: `local_parallel.py`
**Function**: `partition_content()`

Uses unstructured library to parse HTML/PDF content from search results.

```python
# Run in local_parallel.py:
plant_codes = pd.read_csv('ready_to_search.csv')['plant_code']
plant_codes = [pc for pc in plant_codes
    if not os.path.exists(f'results/content/{pc}.json')]
```

**Output**: `results/content/{plant_code}.json`

### 3. Initial Relevance Scoring
**File**: `local_parallel.py`
**Functions**: `get_relevance_scores()`, `process_plant_code()`

Scores each article's relevance on a 1-5 scale using Claude API.

Scoring criteria defined in `ProjectPerceptionsDetailed` class in `util_archive.py`:
- Relevance to specific project
- Mentions of support/opposition
- Types of opposition (physical, legal, etc.)
- Environmental/tribal concerns
- Property value impacts
- Project delays

**Output**: `results/article_relevance/{plant_code}.json`

### 4. Content Relevance Analysis
**File**: `local_parallel.py`
**Function**: `get_content_relevance()`

Analyzes overall content relevance for each project.

**Output**: `results/content_relevance/{plant_code}.json`

### 5. Project Summary Generation
**File**: `local_parallel.py`
**Function**: `get_project_summary()`

Generates detailed project summaries and binary scores for various opposition/support metrics.

**Output**: `results/scores/{plant_code}.json`

### 6. Visualization
**Viz Generation Notebook**: `plots.ipynb`

Creates visualizations of the analysis results:
- Distribution of relevance scores
- Correlation between capacity and relevance
- Other project metrics

**Output Files**: `visualizations/`


## File Structure

```
.
├── results/
│   ├── search/            # Raw search results
│   ├── content/           # Scraped content
│   ├── article_relevance/ # Article-level scores
│   ├── content_relevance/ # Project-level relevance
│   └── scores/           # Final project summaries
├── visualizations/
│   └── [file].png        # Visualization output files
├── search.py             # Search result generation
├── local_parallel.py     # Main processing code
└── util_archive.py       # Helper classes/functions
└── plots.ipynb           # Python notebook to generate visualizations from final results
```

## Running the Analysis

1. Ensure all dependencies are installed and environment variables are set
2. Create necessary directories in `results/`
3. Run each step in sequence, commenting/uncommenting relevant sections in main() functions
4. Monitor output files to ensure each step completes successfully
5. Generate visualizations using plot.py

## Notes

- The codebase uses both OpenAI and Anthropic APIs for different analysis steps
- BrightData is used for reliable search result generation
- Parallel processing is implemented for efficiency
- Results are cached in JSON files to allow for partial runs
```