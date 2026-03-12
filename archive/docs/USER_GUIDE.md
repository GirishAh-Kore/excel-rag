# Google Drive Excel RAG System - User Guide

A comprehensive guide for using the Google Drive Excel RAG System to query your Excel files using natural language.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Web Interface](#web-interface)
3. [Connecting Data Sources](#connecting-data-sources)
4. [Querying Your Data](#querying-your-data)
5. [Understanding Results](#understanding-results)
6. [CLI Usage](#cli-usage)
7. [Tips and Best Practices](#tips-and-best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What is this system?

The Google Drive Excel RAG System allows you to ask questions about your Excel files in plain English (or Thai). Instead of manually searching through spreadsheets, you can simply ask:

- "What was the total revenue in Q1 2024?"
- "Compare expenses between January and February"
- "Which product had the highest sales?"

The system will find the relevant data and provide answers with source citations.

### Prerequisites

Before using the system, ensure you have:

1. **Access credentials** - Username and password provided by your administrator
2. **Excel files** - Either uploaded directly or stored in Google Drive
3. **Modern web browser** - Chrome, Firefox, Safari, or Edge (latest versions)

---

## Web Interface

### Logging In

1. Open your browser and navigate to the application URL (e.g., `http://localhost:8000`)
2. Enter your username and password
3. Click "Login"

Your session will remain active for 24 hours. After that, you'll need to log in again.

### Navigation

The application has three main areas:

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
3. Either:
   - Drag and drop Excel files onto the upload area
   - Click "Browse" to select files from your computer
4. Wait for the upload and indexing to complete

**Supported formats:**
- `.xlsx` - Modern Excel format
- `.xls` - Legacy Excel format
- `.xlsm` - Excel with macros

**File size limit:** 100 MB per file

### Option 2: Connect Google Drive

1. Go to the **Configuration** page
2. Click the **"Google Drive"** tab
3. Click **"Connect Google Drive"**
4. You'll be redirected to Google's authorization page
5. Sign in with your Google account
6. Grant permission to access your Drive files
7. You'll be redirected back to the application

Once connected, the system will automatically discover and index Excel files from your Google Drive.

### Managing Indexed Files

On the **Configuration** page, you can:

- **View** all indexed files with their status
- **Search** for specific files by name
- **Filter** by status (indexed, pending, failed)
- **Reindex** a file if it was updated
- **Delete** files you no longer need

---

## Querying Your Data

### Asking Questions

1. Go to the **Chat** page
2. Type your question in the input box
3. Press Enter or click the send button

### Types of Questions You Can Ask

**Simple lookups:**
- "What is the total in cell B10 of the Sales sheet?"
- "Show me the revenue for January"

**Aggregations:**
- "What was the total expense last quarter?"
- "Calculate the average sales per month"

**Comparisons:**
- "Compare Q1 and Q2 revenue"
- "How did January expenses differ from February?"

**Filtering:**
- "Show all products with sales over $10,000"
- "Which departments exceeded their budget?"

**Temporal queries:**
- "What were the sales in the last 3 months?"
- "Show me year-over-year growth"

### Follow-up Questions

The system remembers your conversation context. You can ask follow-up questions like:

1. "What was the total revenue in 2024?" → Answer provided
2. "Break that down by quarter" → Uses context from previous question
3. "Which quarter had the highest?" → Continues the conversation

### Clarification Requests

Sometimes the system needs more information. It might ask:

- "Which file did you mean?" (if multiple files match)
- "Which time period?" (if dates are ambiguous)
- "Did you mean X or Y?" (if terms are unclear)

Simply click on the suggested option or type your clarification.

---

## Understanding Results

### Answer Components

Each response includes:

1. **Answer** - The main response to your question
2. **Confidence Score** - How confident the system is (0-100%)
3. **Sources** - Where the data came from

### Confidence Scores

| Score | Meaning |
|-------|---------|
| 90-100% | High confidence - data clearly matches your question |
| 70-89% | Good confidence - likely correct but verify if critical |
| 50-69% | Moderate confidence - may need clarification |
| Below 50% | Low confidence - consider rephrasing your question |

### Source Citations

Each answer includes citations showing:
- **File name** - Which Excel file
- **Sheet name** - Which worksheet
- **Cell range** - Specific cells referenced

Click on a citation to see more details.

---

## CLI Usage

For advanced users, a command-line interface is available.

### Authentication

```bash
# Login to Google Drive
python -m src.cli auth login

# Check authentication status
python -m src.cli auth status

# Logout
python -m src.cli auth logout
```

### Indexing

```bash
# Full index of all files
python -m src.cli index full

# Incremental index (only changed files)
python -m src.cli index incremental

# Check indexing status
python -m src.cli index status

# View detailed report
python -m src.cli index report
```

### Querying

```bash
# Ask a question
python -m src.cli query "What was the total revenue in Q1?"

# View query history
python -m src.cli query history

# Clear query history
python -m src.cli query clear
```

### Configuration

```bash
# Show current configuration
python -m src.cli config show

# Validate configuration
python -m src.cli config validate
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

**Reference specific files when needed:**
- ❌ "What's in the report?"
- ✅ "What's the summary in the Q1_Report.xlsx file?"

### Organizing Your Excel Files

For best results:

1. **Use descriptive file names** - Include dates or periods (e.g., `Sales_Q1_2024.xlsx`)
2. **Use clear sheet names** - Name sheets descriptively (e.g., `Revenue`, `Expenses`)
3. **Include headers** - Always have column headers in your data
4. **Keep data consistent** - Use consistent date formats and number formats
5. **Avoid merged cells** - They can complicate data extraction

### Managing Conversations

- **Start new conversations** for unrelated topics
- **Use follow-ups** for related questions
- **Delete old conversations** to keep things organized

---

## Troubleshooting

### Common Issues

**"No results found"**
- Try rephrasing your question
- Check if the relevant file is indexed
- Verify the data exists in your files

**"Low confidence score"**
- Be more specific in your question
- Check if multiple files might match
- Verify terminology matches your data

**"File not indexed"**
- Wait for indexing to complete
- Check if the file format is supported
- Try re-uploading the file

**"Google Drive not connected"**
- Re-authorize the connection
- Check if your Google account has access to the files
- Verify OAuth credentials are configured

### Getting Help

If you encounter issues:

1. Check the **Health** endpoint: `/health`
2. Review application logs (if you have access)
3. Contact your system administrator

### Error Messages

| Error | Solution |
|-------|----------|
| "Invalid credentials" | Check username/password |
| "Token expired" | Log in again |
| "File too large" | Split file or reduce size |
| "Unsupported format" | Convert to .xlsx format |
| "Rate limit exceeded" | Wait a few minutes and retry |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send query |
| `Shift + Enter` | New line in query |
| `Escape` | Clear input |

---

## Privacy and Security

- Your data remains in your Google Drive or uploaded storage
- Queries are processed securely
- OAuth tokens are encrypted
- Sessions expire after 24 hours
- No data is shared with third parties

---

## Support

For additional help:
- **API Documentation**: `/docs` endpoint
- **Technical Documentation**: See `SOLUTION_ARCHITECTURE.md`
- **Docker Deployment**: See `DOCKER.md`

