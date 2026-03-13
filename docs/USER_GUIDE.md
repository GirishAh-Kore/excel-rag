# Google Drive Excel RAG System - User Guide

A comprehensive guide for using the Google Drive Excel RAG System to query your Excel files using natural language.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Web Interface](#web-interface)
3. [Connecting Data Sources](#connecting-data-sources)
4. [Querying Your Data](#querying-your-data)
5. [Smart Query Features](#smart-query-features)
6. [Understanding Results](#understanding-results)
7. [Debugging with Chunk Visibility](#debugging-with-chunk-visibility)
8. [Enterprise Features](#enterprise-features)
9. [CLI Usage](#cli-usage)
10. [Tips and Best Practices](#tips-and-best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What is this system?

The Google Drive Excel RAG System allows you to ask questions about your Excel files in plain English (or Thai). Instead of manually searching through spreadsheets, you can simply ask:

- "What was the total revenue in Q1 2024?"
- "Compare expenses between January and February"
- "Which product had the highest sales?"

The system will find the relevant data and provide answers with source citations.

### Prerequisites

1. **Access credentials** - Username and password provided by your administrator
2. **Excel files** - Either uploaded directly or stored in Google Drive
3. **Modern web browser** - Chrome, Firefox, Safari, or Edge

---

## Web Interface

### Logging In

1. Open your browser and navigate to the application URL
2. Enter your username and password
3. Click "Login"

Your session will remain active for 24 hours.

### Navigation

| Area | Purpose |
|------|---------|
| **Chat** | Ask questions about your data |
| **Configuration** | Connect Google Drive and manage files |
| **Conversations** | View and manage chat history |

---

## Connecting Data Sources

### Option 1: Upload Excel Files

1. Go to the **Configuration** page
2. Click the **"Upload Files"** tab
3. Drag and drop Excel files or click "Browse"
4. Wait for upload and indexing to complete

**Supported formats:** `.xlsx`, `.xls`, `.xlsm`
**File size limit:** 100 MB per file

### Option 2: Connect Google Drive

1. Go to the **Configuration** page
2. Click **"Connect Google Drive"**
3. Sign in with your Google account
4. Grant permission to access your Drive files

### Managing Indexed Files

On the **Configuration** page, you can:
- **View** all indexed files with their status
- **Search** for specific files by name
- **Reindex** a file if it was updated
- **Delete** files you no longer need
- **View quality scores** for each file

---

## Querying Your Data

### Asking Questions

1. Go to the **Chat** page
2. Type your question in the input box
3. Press Enter or click the send button

### Types of Questions You Can Ask

**Aggregations:**
- "What was the total expense last quarter?"
- "Calculate the average sales per month"
- "How many products sold more than 100 units?"

**Lookups:**
- "What is the revenue for January?"
- "Show me the expenses for Product A"
- "Find the value in cell B10"

**Summaries:**
- "Summarize the sales data"
- "Give me an overview of Q1 performance"
- "Describe the expense trends"

**Comparisons:**
- "Compare Q1 and Q2 revenue"
- "How did January expenses differ from February?"
- "Show the growth between 2023 and 2024"

### Follow-up Questions

The system remembers your conversation context:

1. "What was the total revenue in 2024?" → Answer provided
2. "Break that down by quarter" → Uses context from previous question
3. "Which quarter had the highest?" → Continues the conversation

### Clarification Requests

Sometimes the system needs more information:

- "Which file did you mean?" (if multiple files match)
- "Which time period?" (if dates are ambiguous)

Simply click on the suggested option or type your clarification.

---

## Smart Query Features (NEW)

### Automatic File Selection

The system automatically selects the most relevant file(s) for your query based on:
- **Semantic similarity** - How well the file content matches your question
- **Metadata matching** - File names, dates, and structure
- **Your preferences** - Files you've selected before

### Automatic Sheet Selection

Within a file, the system identifies the most relevant sheet(s) based on:
- Sheet name matching
- Column header matching
- Data type alignment

### Query Classification

The system automatically detects what type of answer you need:

| Query Type | Example | What Happens |
|------------|---------|--------------|
| Aggregation | "Total revenue?" | Calculates SUM, AVG, etc. |
| Lookup | "Show Q1 data" | Finds specific values |
| Summarization | "Summarize sales" | Generates natural language summary |
| Comparison | "Compare Q1 vs Q2" | Calculates differences and trends |

### Confidence Scores

Each answer includes confidence scores:
- **File confidence** - How sure the system is about file selection
- **Sheet confidence** - How sure about sheet selection
- **Data confidence** - How sure about the data interpretation
- **Overall confidence** - Combined confidence score

---

## Understanding Results

### Answer Components

Each response includes:

1. **Answer** - The main response to your question
2. **Confidence Score** - How confident the system is (0-100%)
3. **Sources** - Where the data came from (file, sheet, cell range)
4. **Trace ID** - Unique identifier for debugging

### Confidence Scores

| Score | Meaning |
|-------|---------|
| 90-100% | High confidence - data clearly matches |
| 70-89% | Good confidence - likely correct |
| 50-69% | Moderate confidence - may need verification |
| Below 50% | Low confidence - consider rephrasing |

### Source Citations

Each answer includes citations showing:
- **File name** - Which Excel file
- **Sheet name** - Which worksheet
- **Cell range** - Specific cells referenced
- **Lineage ID** - Link to full data lineage

Click on a citation to see more details about the data source.

---

## Debugging with Chunk Visibility (NEW)

### What are Chunks?

When Excel files are indexed, they are split into "chunks" - smaller segments of data that can be searched efficiently. Chunk visibility lets you inspect these chunks for debugging.

### Viewing Chunks

1. Go to **Configuration** → **Files**
2. Click on a file to see its chunks
3. View chunk details including:
   - Chunk text and raw source data
   - Row range and boundaries
   - Extraction strategy used
   - Quality scores

### Searching Chunks

You can search chunks to find specific data:
1. Use the chunk search feature
2. Enter your search query
3. Filter by file, sheet, or extraction strategy
4. View similarity scores for each result

### Quality Reports

View quality scores for all indexed files:
- Files with quality < 50% are flagged as problematic
- Common issues: missing headers, low structure clarity
- Recommendations for improving extraction

### Chunk Feedback

If you find issues with chunks:
1. Click "Submit Feedback" on a chunk
2. Select feedback type (incorrect data, missing data, etc.)
3. Add optional comments
4. Your feedback helps improve the system

---

## Enterprise Features (NEW)

### Query Tracing

Every query is recorded with a complete audit trail:
- File selection decisions and reasoning
- Sheet selection decisions
- Query classification
- Answer generation details
- Performance timing

Access traces via the trace ID in your query response.

### Data Lineage

Track exactly where your answer came from:
- Source file, sheet, and cell range
- Processing path through the system
- Timestamps for when data was indexed
- Staleness detection if source data changed

### Batch Queries

Process multiple queries at once:
1. Submit up to 100 queries in a batch
2. Track progress via batch ID
3. Get results for all queries when complete
4. Individual status for each query (success/failure)

### Query Templates

Save and reuse common queries:
1. Create a template with parameters: "What was the total {{metric}} in {{quarter}}?"
2. Execute with different parameter values
3. Share templates with your team

### Export Results

Export query results in multiple formats:
- **CSV** - For spreadsheet analysis
- **Excel (.xlsx)** - Preserves formatting
- **JSON** - For programmatic use

### Webhooks

Get notified when events occur:
- Indexing complete
- Query failed
- Low confidence answer
- Batch complete

---

## CLI Usage

For advanced users, a command-line interface is available.

### Authentication

```bash
python -m src.cli auth login
python -m src.cli auth status
python -m src.cli auth logout
```

### Indexing

```bash
python -m src.cli index full
python -m src.cli index incremental
python -m src.cli index status
```

### Querying

```bash
python -m src.cli query "What was the total revenue in Q1?"
python -m src.cli query history
```

---

## Tips and Best Practices

### Writing Effective Queries

**Be specific:**
- ❌ "Show me the data"
- ✅ "Show me the sales data for January 2024"

**Use clear terminology:**
- ❌ "What's the number?"
- ✅ "What is the total revenue?"

**Specify time periods:**
- ❌ "What were the expenses?"
- ✅ "What were the expenses in Q1 2024?"

### Organizing Your Excel Files

For best results:
1. **Use descriptive file names** - Include dates (e.g., `Sales_Q1_2024.xlsx`)
2. **Use clear sheet names** - Name sheets descriptively
3. **Include headers** - Always have column headers
4. **Keep data consistent** - Use consistent formats
5. **Avoid merged cells** - They complicate extraction

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "No results found" | Rephrase question, check if file is indexed |
| "Low confidence score" | Be more specific, verify terminology |
| "File not indexed" | Wait for indexing, check file format |
| "Access denied" | Contact administrator for permissions |

### Getting Help

1. Check the trace ID in your response for debugging
2. View chunk details for the relevant file
3. Submit feedback on problematic chunks
4. Contact your system administrator

---

## Privacy and Security

- Your data remains in your Google Drive or uploaded storage
- Queries are processed securely with full audit logging
- OAuth tokens are encrypted
- Sessions expire after 24 hours
- Role-based access control protects sensitive data
