"""
Transaction-Attachment Matching System for NOCFO Homework Assignment

This file implements matching logic for the bank transactions and their matching documents (receipts/invoices) for accounting purposes.
"""

import re
from datetime import datetime
from typing import List

Attachment = dict[str, dict]
Transaction = dict[str, dict]

# Helper functions

def _normalize_reference(reference: str) -> str:
    """
    Normalizes reference numbers for exact matching.
    
    Handles cases like:
    - "9876 543 2103" → "98765432103" 
    - "0000 0000 5550 0011 14" → "5550001114"
    - "RF661234000001" → "RF661234000001"
    """
    if not reference or not reference.strip():
        return ""
    
    # Remove whitespace and convert to uppercase
    normalized = re.sub(r'\s+', '', reference.upper())
    
    # Handle Finnish/IBAN references
    if normalized.startswith('RF'):
        prefix = 'RF'
        number_part = normalized[2:]
        number_part = re.sub(r'^0+', '', number_part) or '0'
        normalized = prefix + number_part
    else:
        normalized = re.sub(r'^0+', '', normalized) or '0'
    
    return normalized


def _normalize_name(name: str) -> str:
    """
    Normalize names by removing extra whitespace and making it lowercase.
    Examples:
        "  Jane   Smith  " → "jane smith"
        "Best Supplies EMEA" → "best supplies emea"
    """
    
    if not name:
        return ""
    return ' '.join(name.lower().split())


def _names_match(name1: str, name2: str) -> bool:
    """Check if two names match allowing for variations."""
    if not name1 or not name2:
        return False
    
    norm1 = _normalize_name(name1)
    norm2 = _normalize_name(name2)
    
    # Exact match
    if norm1 == norm2:
        return True
    
    if norm1 in norm2 or norm2 in norm1:
        return True
    
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if len(words1) == 0 or len(words2) == 0:
        return False
        
    common_words = words1.intersection(words2)
    total_words = min(len(words1), len(words2))
    
    if len(common_words) >= 2:
        overlap_ratio = len(common_words) / total_words
        return overlap_ratio >= 0.5
        
    elif len(common_words) == 1 and total_words <= 2:
        non_common1 = words1 - common_words
        non_common2 = words2 - common_words
        
        # Exact subset match - "Matti" vs "Matti Meikäläinen"
        if len(non_common1) == 0 or len(non_common2) == 0:
            return True
            
        if len(non_common1) == 1 and len(non_common2) == 1:
            word1 = list(non_common1)[0]
            word2 = list(non_common2)[0]
            suffixes = {'oy', 'ltd', 'corp', 'inc', 'tmi', 'ab', 'as', 'gmbh', 'company', 'co'}
            if word1.lower() in suffixes or word2.lower() in suffixes:
                return True
    
    return False


def _get_attachment_counterparty_names(attachment: Attachment) -> List[str]:
    """
    Extracts all potential names from an attachment.
    
    Checks for multiple fields:
    - issuer (for sales invoices)
    - recipient (for purchase invoices) 
    - supplier (for receipts and purchase invoices)
    
    Filters out "Example Company Oy" references.
    """
    data = attachment.get('data', {})
    names = []
    

    for field in ['issuer', 'recipient', 'supplier']:
        if field in data and data[field]:
            names.append(data[field])
    
    # Filter out self-references to the company
    return [name for name in names if name and 'example company' not in name.lower()]


def _calculate_name_specificity(name1: str, name2: str) -> int:
    """
    Calculates how specific/exact a name match is, how much overlap there is.
    
    Scoring criteria/ Returns:
        5: One name is subset of other 
        4: Exact match
        3: Very close substring match (>75% overlap)
        2: Good substring match (one contained in other)
        1: Word overlap match
        0: No match
    """
    if not name1 or not name2:
        return 0
    
    norm1 = _normalize_name(name1)
    norm2 = _normalize_name(name2)
    
    # Exact match gets 4
    if norm1 == norm2:
        return 4
    
    # More complete information is preferred- if one name is subset of other
    if norm1 in norm2 or norm2 in norm1:
        # Give higher score to the scenario where we have more complete info
        longer_name = norm2 if len(norm2) > len(norm1) else norm1
        shorter_name = norm1 if len(norm1) < len(norm2) else norm2
        
        # If the shorter name is completely contained in longer name
        if shorter_name in longer_name:
            return 5  # Prefer the more complete match
        
        # Calculate substring match specificity
        overlap_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
        if overlap_ratio > 0.75: 
            return 3  
        else:
            return 2 
    
    return 0


def _are_dates_compatible(tx_date: str, att_data: dict, tolerance_days: int = 15) -> bool:
    """
    Checks if transaction date is in range of 15 days with attachment dates.
    
    Allows for different payment timing cases:
    - Early payment (before due date)
    - Late payment (after due date) 
    - Processing delays
    """
    try:
        tx_dt = datetime.strptime(tx_date, '%Y-%m-%d')
        
        # Check against all available date fields
        date_fields = ['due_date', 'invoicing_date', 'receiving_date']
        
        for field in date_fields:
            if field in att_data and att_data[field]:
                try:
                    att_dt = datetime.strptime(att_data[field], '%Y-%m-%d')
                    diff_days = abs((tx_dt - att_dt).days)
                    
                    if diff_days <= tolerance_days:
                        return True
                        
                except ValueError:
                    continue
        
        return False
    except ValueError:
        return False

# =============================================================================
# Scoring and matching logic
# =============================================================================

def _calculate_match_score(transaction: Transaction, attachment: Attachment) -> tuple[int, bool]:
    """
    This calculates confidence score for transaction and attachment.
    
    Returns:
        tuple: (score, has_counterparty_compatibility)
        
    Scoring system:
        - Amount match: +3 (REQUIRED)
        - Date compatibility: +2
        - Name match: +2  
        - Unknown counterparty: +1
        
    Minimum score for confidence: 5
    """
    tx_amount = transaction.get('amount')
    tx_date = transaction.get('date') 
    tx_contact = transaction.get('contact')
    
    att_data = attachment.get('data', {})
    att_amount = att_data.get('total_amount')
    att_counterparties = _get_attachment_counterparty_names(attachment)
    
    score = 0
    has_counterparty_match = False

    # 1. AMOUNT MATCH (Required) - converts to absolute values since bank transactions show direction (negative for outgoing payments) while invoices usually show positive amounts
    if att_amount is None or tx_amount is None:
        return 0, False
    
    # Advanced decimal precision handling with context-aware tolerance as there can be ATM fees or Banking charges
    att_abs = abs(float(att_amount))
    tx_abs = abs(float(tx_amount))
    amount_diff = abs(att_abs - tx_abs)
    
    # Detect precision mismatches vs legitimate banking differences
    def is_precision_mismatch():
        # Check decimal places difference
        tx_str = str(tx_abs)
        att_str = str(att_abs)
        tx_decimals = len(tx_str.split('.')[-1]) if '.' in tx_str else 0
        att_decimals = len(att_str.split('.')[-1]) if '.' in att_str else 0
        
        # Case 1: Extreme precision difference (e.g., 123.456789 vs 123.46)
        if abs(tx_decimals - att_decimals) > 3 and max(tx_decimals, att_decimals) > 4:
            return True
            
        # Case 2: Exact cents differences in round numbers
        # But exclude common banking scenarios like 99.99 vs 100.00 (there can be a small charge difference)
        # Use tolerance to handle floating-point precision
        if abs(amount_diff - 0.01) < 0.001:  # Essentially 0.01 difference
            # Check if both amounts are "round" 
            tx_is_round = abs((tx_abs * 100) % 1) < 0.001  
            att_is_round = abs((att_abs * 100) % 1) < 0.001  
            if tx_is_round and att_is_round:

                is_banking_pattern = (
                    (abs(tx_abs % 1 - 0.99) < 0.001 and abs(att_abs % 1) < 0.001) or
                    (abs(att_abs % 1 - 0.99) < 0.001 and abs(tx_abs % 1) < 0.001)
                )
                
                if not is_banking_pattern and (abs(tx_abs % 1) < 0.001 or abs(att_abs % 1) < 0.001):
                    return True
        
        return False
    
    # Apply tolerance based on context
    if is_precision_mismatch():
        tolerance = 0.002 
    else:
        tolerance = 0.011 
    
    if amount_diff > tolerance:
        return 0, False
    
    score += 3  # High confidence score for amount match
    
    # 2. DATE COMPATIBILITY 15 days tolerance
    if tx_date and _are_dates_compatible(tx_date, att_data):
        score += 2
    
    # 3. COUNTERPARTY MATCHING with specificity scoring
    if tx_contact:
        # Transaction has contact - must match attachment name
        best_match_score = 0
        
        for att_counterparty in att_counterparties:
            if _names_match(tx_contact, att_counterparty):
                # Calculate match specificity for better disambiguation
                specificity_score = _calculate_name_specificity(tx_contact, att_counterparty)
                if specificity_score > best_match_score:
                    best_match_score = specificity_score
                    has_counterparty_match = True
        
        if has_counterparty_match:
            # Award points based on match quality (enhanced scoring)
            if best_match_score >= 5:  # More complete information preferred
                score += 5
            elif best_match_score >= 4:  # Exact match
                score += 4
            elif best_match_score >= 3:  # Very close substring match
                score += 3
            elif best_match_score >= 2:  # Good substring match
                score += 2
            else:  
                score += 1
    elif att_counterparties:
        # Transaction has no contact but attachment has counterparty - acceptable
        score += 1
        has_counterparty_match = True
    else:
        # Both have no counterparty info - acceptable
        score += 1
        has_counterparty_match = True
    
    return score, has_counterparty_match

# =============================================================================
# Main matching functions
# =============================================================================

def find_attachment(
    transaction: Transaction,
    attachments: list[Attachment],
) -> Attachment | None:
    """
    Finds the best matching attachment for a given transaction.
    
    Algorithm:
    1. Try exact reference number match (highest priority and guaranteed)
    2. Use confidence scoring with amount + date + counterparty
    
    Arguments:
        transaction: Single bank transaction to match
        attachments: List of all available attachments
        
    Returns:
        Best matching attachment or None if confidence score < 5
    """
    tx_ref = transaction.get('reference')
    
    # PRIORITY 1: Exact reference match (guaranteed 1:1)
    if tx_ref:
        tx_ref_norm = _normalize_reference(tx_ref)
        
        for attachment in attachments:
            att_ref = attachment.get('data', {}).get('reference')
            if att_ref and _normalize_reference(att_ref) == tx_ref_norm:
                return attachment
    
    # PRIORITY 2: Multi-factor confidence scoring algorithm
    candidates = []
    
    for attachment in attachments:
        score, has_counterparty_match = _calculate_match_score(transaction, attachment)
        
        # Require minimum confidence and counterparty compatibility
        if score >= 5 and has_counterparty_match:
            candidates.append((attachment, score))
    
    # Returns the highest scoring candidate
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True) 
        return candidates[0][0]
    
    return None


def find_transaction(
    attachment: Attachment,
    transactions: list[Transaction],
) -> Transaction | None:
    """
    Finds the best matching transaction for a given attachment.
    
    Algorithm:
    1. Try exact reference number match (highest priority)  
    2. Use confidence scoring with amount + date + counterparty
    
    Arguments:
        attachment: Single attachment (invoice/receipt) to match
        transactions: List of all available transactions
        
    Returns:
         Best matching transaction or None if confidence score < 5
    """
    att_data = attachment.get('data', {})
    att_ref = att_data.get('reference')
    
    # PRIORITY 1: Exact reference match (guaranteed 1:1)
    if att_ref:
        att_ref_norm = _normalize_reference(att_ref)
        
        for transaction in transactions:
            tx_ref = transaction.get('reference')
            if tx_ref and _normalize_reference(tx_ref) == att_ref_norm:
                return transaction
    
    # PRIORITY 2: Multi-factor confidence scoring with best match selection
    candidates = []
    
    for transaction in transactions:
        score, has_counterparty_match = _calculate_match_score(transaction, attachment)
        
        # Requires minimum confidence and counterparty compatibility
        if score >= 5 and has_counterparty_match:
            candidates.append((transaction, score))
    
    # Returns the highest scoring candidate
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)  
        return candidates[0][0]
    
    return None
