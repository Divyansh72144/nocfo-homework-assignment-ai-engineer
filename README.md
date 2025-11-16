# NOCFO Transaction-Attachment Matching System

A Python implementation for matching bank transactions with their supporting documents (receipts/invoices) for accounting purposes.

## How to Run the Application

1. **Prerequisites**: Python 3.8+

2. **Clone and navigate to the repository**:
   ```bash
   git clone https://github.com/Divyansh72144/nocfo-homework-assignment-ai-engineer.git
   cd nocfo-homework-assignment-ai-engineer
   ```

3. **Run the matching system**:
   ```bash
   python run.py
   ```

This runs the matching logic and displays:
- Transactions that match the attachments
- Attachments that match the transactions
- Pass/fail for each test

## Architecture Overview

### Main Files

**`src/match.py`** - Core matching logic:
- `find_attachment()` -Finds best attachment for a transaction
- `find_transaction()` - Finds best transaction for an attachment

**`src/data/`** - Test data:
- `transactions.json` -Bank transactions
- `attachments.json` - Invoices/receipts

**`python edge_case_tests.py`** - To execute the edge cases

### Matching Strategy

The matcher uses 2 approaches:

#### 1. Reference Number Match
If both have the same reference number, they match. It also handles different formats such as:
- `"9876 543 2103"` → `"98765432103"` (removes spaces)
- `"0000 5550 0011 14"` → `"5550001114"` (removes leading zeros)
- Finnish IBAN: `"RF00 1234"` → `"RF1234"`

#### 2. Smart Scoring (if no reference match)
Scores based on:

- **Amount match** (+3): Must match, handles +/- and rounding
- **Name compatibility**: Both party names are compared for compatibility using fuzzy matching.
- **Date match** (+2): Range of 15 days is acceptable
- **Name quality** (+1 to +4): Higher matches gets more points

A minimum confidence score of 5 points is required.

### Technical Details

**Name Matching**: Handles variations like:
- `"Matti"` matches `"Matti Meikäläinen Tmi"`
- `"Best Supplies EMEA"` matches `"Best Supplies Europe"`
- `"Company Oy"` matches `"Company Ltd"`

**Amount Tolerance**: Different tolerances for banking vs precision issues

**Multiple Name Fields**: Checks supplier, recipient, issuer fields. Ignores self-references.

**Best Match**: Selects the highest-scoring candidate when multiple matches exist.

### Edge Cases

It handles missing/null fields, amount precision/banking-charge differences, and name ambiguity.

### Results

Passes all **21/21 test cases** - 12 transaction matches and 9 attachment matches. Additionally, it passes the extra tests in edge cases file.
