"""
Document Summarizer Service (Feature 70)
Professional-grade SEC filing analysis with NLP processing.
Real data from SEC EDGAR API.
"""

import re
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
from collections import Counter
import math

# =============================================================================
# SEC EDGAR API INTEGRATION
# =============================================================================

SEC_EDGAR_BASE = "https://www.sec.gov"
import logging

logger = logging.getLogger(__name__)

SEC_DATA_BASE = "https://data.sec.gov"
SEC_FULL_TEXT = "https://www.sec.gov/cgi-bin/browse-edgar"

# SEC Filing Types with descriptions
FILING_TYPES = {
    "10-K": "Annual Report - comprehensive overview of the company's business and financial condition",
    "10-Q": "Quarterly Report - unaudited financial statements and operations update",
    "8-K": "Current Report - material events or corporate changes",
    "S-1": "Registration Statement - IPO filing",
    "424B": "Prospectus - securities offering document",
    "DEF 14A": "Proxy Statement - shareholder meeting and voting information",
    "13F": "Institutional Holdings - quarterly holdings of institutional investment managers"
}

# SEC Section Patterns for 10-K/10-Q
SEC_SECTION_PATTERNS = {
    "business": r"(?:ITEM\s*1\.?\s*[-–—]?\s*BUSINESS|PART\s*I.*ITEM\s*1)",
    "risk_factors": r"(?:ITEM\s*1A\.?\s*[-–—]?\s*RISK\s*FACTORS)",
    "properties": r"(?:ITEM\s*2\.?\s*[-–—]?\s*PROPERTIES)",
    "legal_proceedings": r"(?:ITEM\s*3\.?\s*[-–—]?\s*LEGAL\s*PROCEEDINGS)",
    "mda": r"(?:ITEM\s*7\.?\s*[-–—]?\s*MANAGEMENT[''']?S?\s*DISCUSSION)",
    "quantitative": r"(?:ITEM\s*7A\.?\s*[-–—]?\s*QUANTITATIVE)",
    "financial_statements": r"(?:ITEM\s*8\.?\s*[-–—]?\s*FINANCIAL\s*STATEMENTS)",
    "controls": r"(?:ITEM\s*9A\.?\s*[-–—]?\s*CONTROLS)",
    "executive_compensation": r"(?:ITEM\s*11\.?\s*[-–—]?\s*EXECUTIVE\s*COMPENSATION)",
    "security_ownership": r"(?:ITEM\s*12\.?\s*[-–—]?\s*SECURITY\s*OWNERSHIP)"
}

# Risk Categories and Keywords
RISK_CATEGORIES = {
    "financial": {
        "keywords": ["debt", "leverage", "liquidity", "credit", "interest rate", "currency", "exchange rate", 
                    "capital", "financing", "cash flow", "covenant", "default", "insolvency", "bankruptcy"],
        "weight": 1.0
    },
    "operational": {
        "keywords": ["supply chain", "production", "manufacturing", "operations", "execution", "capacity",
                    "technology", "systems", "infrastructure", "disruption", "outage", "failure"],
        "weight": 1.0
    },
    "regulatory": {
        "keywords": ["regulation", "regulatory", "compliance", "law", "legal", "government", "policy",
                    "legislation", "enforcement", "sanctions", "license", "permit", "EPA", "FDA", "SEC"],
        "weight": 1.0
    },
    "strategic": {
        "keywords": ["competition", "competitive", "market share", "strategy", "business model", 
                    "acquisition", "merger", "restructuring", "transformation", "innovation"],
        "weight": 1.0
    },
    "reputational": {
        "keywords": ["reputation", "brand", "customer", "trust", "media", "social", "public",
                    "scandal", "controversy", "ESG", "environmental", "sustainability", "ethics"],
        "weight": 1.0
    }
}

# Intensity modifiers for risk scoring
INTENSITY_MODIFIERS = {
    "high": ["material", "significant", "substantial", "severe", "critical", "major", "serious", "adverse"],
    "medium": ["may", "could", "might", "potential", "possible", "uncertain", "risk"],
    "low": ["unlikely", "minimal", "limited", "minor", "slight", "remote"]
}

# Forward-looking statement indicators
FORWARD_LOOKING_KEYWORDS = [
    "expect", "anticipate", "believe", "plan", "intend", "forecast", 
    "guidance", "outlook", "target", "estimate", "project", "will", 
    "should", "may", "could", "would"
]

# Financial metrics patterns
METRIC_PATTERNS = {
    "revenue": r"(?:revenue|net\s*sales|total\s*revenue)[:\s]*\$?([\d,\.]+)\s*(million|billion|M|B)?",
    "net_income": r"(?:net\s*income|net\s*earnings)[:\s]*\$?([\d,\.]+)\s*(million|billion|M|B)?",
    "eps": r"(?:earnings\s*per\s*share|EPS)[:\s]*\$?([\d,\.]+)",
    "total_debt": r"(?:total\s*debt|long-term\s*debt)[:\s]*\$?([\d,\.]+)\s*(million|billion|M|B)?",
    "cash": r"(?:cash\s*and\s*cash\s*equivalents|total\s*cash)[:\s]*\$?([\d,\.]+)\s*(million|billion|M|B)?",
    "assets": r"(?:total\s*assets)[:\s]*\$?([\d,\.]+)\s*(million|billion|M|B)?",
    "operating_income": r"(?:operating\s*income|income\s*from\s*operations)[:\s]*\$?([\d,\.]+)\s*(million|billion|M|B)?"
}


# =============================================================================
# SEC EDGAR DATA FETCHING
# =============================================================================

def get_company_cik(ticker: str) -> Optional[str]:
    """Get CIK number for a company ticker."""
    try:
        headers = {"User-Agent": "QuantResearch research@example.com"}
        
        # Primary method: search company tickers file from www.sec.gov
        tickers_url = f"{SEC_EDGAR_BASE}/files/company_tickers.json"
        resp = requests.get(tickers_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry.get("cik_str", "")).zfill(10)
                    return cik
        
        # Fallback: try data.sec.gov with padded zeros
        for padding in [10, 0]:
            try:
                padded = ticker.upper().zfill(padding) if padding else ticker.upper()
                url = f"{SEC_DATA_BASE}/submissions/CIK{padded}.json"
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("cik", "").zfill(10)
            except:
                continue
                
    except Exception as e:
        print(f"Error fetching CIK for {ticker}: {e}")
    return None


def fetch_company_filings(ticker: str, filing_type: str = "10-K", count: int = 5) -> List[Dict]:
    """Fetch recent SEC filings for a company."""
    cik = get_company_cik(ticker)
    if not cik:
        return []
    
    try:
        headers = {"User-Agent": "QuantResearch research@example.com"}
        url = f"{SEC_DATA_BASE}/submissions/CIK{cik}.json"
        
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        filings = []
        
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        
        for i, form in enumerate(forms):
            if form == filing_type and len(filings) < count:
                accession = accessions[i].replace("-", "")
                filings.append({
                    "form": form,
                    "date": dates[i],
                    "accession": accessions[i],
                    "document": docs[i],
                    "url": f"{SEC_EDGAR_BASE}/Archives/edgar/data/{cik}/{accession}/{docs[i]}",
                    "company": data.get("name", ticker),
                    "ticker": ticker.upper(),
                    "cik": cik
                })
        
        return filings
    except Exception as e:
        print(f"Error fetching filings for {ticker}: {e}")
        return []


def fetch_filing_text(filing_url: str) -> str:
    """Fetch the text content of a SEC filing."""
    try:
        headers = {"User-Agent": "QuantResearch research@example.com"}
        # Use stream=True to handle large files and check size
        resp = requests.get(filing_url, headers=headers, timeout=20, stream=True)
        if resp.status_code == 200:
            # Limit to 5MB for analysis to prevent timeouts/memory issues
            content = b""
            max_size = 5 * 1024 * 1024
            for chunk in resp.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    logger.warning(f"Filing at {filing_url} truncated at 5MB")
                    break
            
            text_content = content.decode('utf-8', errors='ignore')
            
            # Use BeautifulSoup for much better HTML stripping
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(text_content, 'html.parser')
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.extract()
                text = soup.get_text(separator=' ')
            except ImportError:
                # Fallback to regex if bs4/lxml not available
                text = re.sub(r'<[^>]+>', ' ', text_content)
                
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            # Remove special characters but keep punctuation
            text = re.sub(r'[^\w\s\.\,\;\:\-\$\%\(\)]', ' ', text)
            return text.strip()
    except Exception as e:
        logger.error(f"Error fetching filing text from {filing_url}: {e}")
    return ""


# =============================================================================
# DOCUMENT PROCESSING
# =============================================================================

def detect_sections(text: str) -> Dict[str, str]:
    """Detect and extract SEC filing sections."""
    sections = {}
    text_upper = text.upper()
    
    for section_name, pattern in SEC_SECTION_PATTERNS.items():
        matches = list(re.finditer(pattern, text_upper, re.IGNORECASE))
        if matches:
            start_idx = matches[0].end()
            
            # Find next section start
            end_idx = len(text)
            for other_name, other_pattern in SEC_SECTION_PATTERNS.items():
                if other_name != section_name:
                    other_matches = list(re.finditer(other_pattern, text_upper[start_idx:], re.IGNORECASE))
                    if other_matches:
                        potential_end = start_idx + other_matches[0].start()
                        if potential_end < end_idx and potential_end > start_idx:
                            end_idx = potential_end
            
            section_text = text[start_idx:end_idx].strip()
            if len(section_text) > 100:  # Minimum content threshold
                sections[section_name] = section_text[:50000]  # Limit size
    
    return sections


def calculate_tfidf_scores(sentences: List[str]) -> Dict[int, float]:
    """Calculate TF-IDF scores for sentence importance."""
    if not sentences:
        return {}
    
    # Word frequency per sentence
    sentence_words = []
    word_doc_count = Counter()
    
    for sent in sentences:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower())
        sentence_words.append(set(words))
        for word in set(words):
            word_doc_count[word] += 1
    
    # Calculate TF-IDF for each sentence
    scores = {}
    n_docs = len(sentences)
    
    for idx, sent in enumerate(sentences):
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower())
        if not words:
            scores[idx] = 0
            continue
        
        word_freq = Counter(words)
        score = 0
        for word, freq in word_freq.items():
            tf = freq / len(words)
            idf = math.log((n_docs + 1) / (word_doc_count.get(word, 0) + 1)) + 1
            score += tf * idf
        
        # Normalize by sentence length
        scores[idx] = score / len(words) if words else 0
    
    return scores


def extractive_summarize(text: str, num_sentences: int = 5) -> str:
    """Generate extractive summary using TF-IDF + position scoring."""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if len(sentences) <= num_sentences:
        return ' '.join(sentences)
    
    # Calculate TF-IDF scores
    tfidf_scores = calculate_tfidf_scores(sentences)
    
    # Position scoring (earlier sentences more important)
    position_scores = {i: 1.0 - (i / len(sentences)) * 0.5 for i in range(len(sentences))}
    
    # Length scoring (prefer medium-length sentences)
    length_scores = {}
    for i, s in enumerate(sentences):
        word_count = len(s.split())
        if 10 <= word_count <= 40:
            length_scores[i] = 1.0
        elif word_count < 10:
            length_scores[i] = 0.5
        else:
            length_scores[i] = 0.7
    
    # Combined scoring
    combined_scores = {}
    for i in range(len(sentences)):
        combined_scores[i] = (
            tfidf_scores.get(i, 0) * 0.5 +
            position_scores.get(i, 0) * 0.3 +
            length_scores.get(i, 0) * 0.2
        )
    
    # Select top sentences
    top_indices = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)[:num_sentences]
    top_indices = sorted(top_indices)  # Restore original order
    
    return ' '.join(sentences[i] for i in top_indices)


# =============================================================================
# RISK EXTRACTION AND SCORING
# =============================================================================

def extract_risks(text: str) -> List[Dict[str, Any]]:
    """Extract and categorize risks from text."""
    risks = []
    
    # Split into paragraphs
    paragraphs = re.split(r'\n\n+|\.\s{2,}', text)
    
    for idx, para in enumerate(paragraphs):
        if len(para) < 50:
            continue
        
        para_lower = para.lower()
        
        # Check if paragraph contains risk-related content
        has_risk_indicator = any(word in para_lower for word in 
                                 ["risk", "uncertainty", "could", "may", "adverse", "negative", "impact"])
        
        if not has_risk_indicator:
            continue
        
        # Categorize the risk
        category_scores = {}
        for category, info in RISK_CATEGORIES.items():
            score = sum(1 for kw in info["keywords"] if kw in para_lower)
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            continue
        
        primary_category = max(category_scores, key=category_scores.get)
        
        # Calculate severity score
        severity = 5  # Base score
        for level, modifiers in INTENSITY_MODIFIERS.items():
            modifier_count = sum(1 for m in modifiers if m in para_lower)
            if level == "high":
                severity += modifier_count * 1.5
            elif level == "medium":
                severity += modifier_count * 0.5
            elif level == "low":
                severity -= modifier_count * 0.5
        
        severity = max(1, min(10, severity))  # Clamp to 1-10
        
        # Extract key phrases
        keywords = []
        for category, info in RISK_CATEGORIES.items():
            keywords.extend([kw for kw in info["keywords"] if kw in para_lower])
        
        risks.append({
            "id": f"risk_{idx}",
            "category": primary_category,
            "text": para[:500],  # Limit text length
            "severity": round(severity, 1),
            "keywords": list(set(keywords))[:10],
            "status": "current"  # Will be updated in delta analysis
        })
    
    return risks[:50]  # Limit to 50 risks


def calculate_risk_scores(risks: List[Dict]) -> Dict[str, float]:
    """Calculate aggregate risk scores by category."""
    scores = {cat: 0 for cat in RISK_CATEGORIES}
    counts = {cat: 0 for cat in RISK_CATEGORIES}
    
    for risk in risks:
        category = risk.get("category")
        if category in scores:
            scores[category] += risk.get("severity", 5)
            counts[category] += 1
    
    # Normalize to 0-100 scale
    normalized = {}
    for cat in RISK_CATEGORIES:
        if counts[cat] > 0:
            avg_severity = scores[cat] / counts[cat]
            # Scale: avg severity 1-10 maps to 10-100
            normalized[cat] = min(100, int(avg_severity * 10))
        else:
            normalized[cat] = 0
    
    return normalized


# =============================================================================
# METRIC EXTRACTION
# =============================================================================

def extract_metrics(text: str) -> Dict[str, Dict[str, Any]]:
    """Extract financial metrics from text."""
    metrics = {}
    
    for metric_name, pattern in METRIC_PATTERNS.items():
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Take the first match
                match = matches[0]
                
                # Handle group extraction (some patterns have more groups)
                raw_val = match[0] if isinstance(match, (tuple, list)) else match
                raw_unit = match[1] if isinstance(match, (tuple, list)) and len(match) > 1 else ""
                
                # Sanitize value string
                sanitized_val = re.sub(r'[^\d.]', '', raw_val.replace(",", ""))
                if not sanitized_val or sanitized_val == ".":
                    continue
                    
                value = float(sanitized_val)
                unit = raw_unit if raw_unit else ""
                
                # Convert to absolute value
                if unit.lower() in ["billion", "b"]:
                    value *= 1e9
                elif unit.lower() in ["million", "m"]:
                    value *= 1e6
                
                metrics[metric_name] = {
                    "value": value,
                    "raw": raw_val,
                    "unit": "USD",
                    "context": ""
                }
        except Exception as e:
            logger.warning(f"Failed to extract metric {metric_name}: {e}")
            continue
    
    return metrics


def extract_forward_looking(text: str) -> List[Dict[str, Any]]:
    """Extract forward-looking statements."""
    statements = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sent in sentences:
        sent_lower = sent.lower()
        if any(kw in sent_lower for kw in FORWARD_LOOKING_KEYWORDS):
            # Determine tone
            positive_words = ["growth", "increase", "improve", "strong", "confident", "optimistic"]
            negative_words = ["decline", "decrease", "challenging", "uncertain", "cautious", "concern"]
            
            pos_count = sum(1 for w in positive_words if w in sent_lower)
            neg_count = sum(1 for w in negative_words if w in sent_lower)
            
            if pos_count > neg_count:
                tone = "positive"
            elif neg_count > pos_count:
                tone = "cautious"
            else:
                tone = "neutral"
            
            # Extract numbers if present
            numbers = re.findall(r'\$?[\d,]+\.?\d*%?', sent)
            
            statements.append({
                "text": sent[:300],
                "tone": tone,
                "numerical_guidance": numbers[:5] if numbers else [],
                "keywords": [kw for kw in FORWARD_LOOKING_KEYWORDS if kw in sent_lower]
            })
    
    return statements[:20]  # Limit to 20 statements


# =============================================================================
# CHANGE DETECTION (DELTA ANALYSIS)
# =============================================================================

def simple_sentence_similarity(sent1: str, sent2: str) -> float:
    """Calculate simple word-overlap similarity between sentences."""
    words1 = set(re.findall(r'\b[a-zA-Z]{3,}\b', sent1.lower()))
    words2 = set(re.findall(r'\b[a-zA-Z]{3,}\b', sent2.lower()))
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0


def detect_changes(current_text: str, previous_text: str) -> Dict[str, Any]:
    """Detect changes between two document versions."""
    current_sentences = re.split(r'(?<=[.!?])\s+', current_text)
    previous_sentences = re.split(r'(?<=[.!?])\s+', previous_text)
    
    current_sentences = [s.strip() for s in current_sentences if len(s.strip()) > 20]
    previous_sentences = [s.strip() for s in previous_sentences if len(s.strip()) > 20]
    
    # Find new, removed, and modified content
    new_content = []
    removed_content = []
    modified_content = []
    
    # Check current sentences
    for curr_sent in current_sentences:
        best_match = 0
        best_prev = None
        
        for prev_sent in previous_sentences:
            sim = simple_sentence_similarity(curr_sent, prev_sent)
            if sim > best_match:
                best_match = sim
                best_prev = prev_sent
        
        if best_match < 0.5:  # New content
            new_content.append(curr_sent[:200])
        elif best_match < 0.85:  # Modified content
            modified_content.append({
                "current": curr_sent[:200],
                "previous": best_prev[:200] if best_prev else "",
                "similarity": round(best_match, 2)
            })
    
    # Check for removed content
    for prev_sent in previous_sentences:
        has_match = False
        for curr_sent in current_sentences:
            if simple_sentence_similarity(prev_sent, curr_sent) > 0.5:
                has_match = True
                break
        if not has_match:
            removed_content.append(prev_sent[:200])
    
    # Calculate change percentage
    total_sentences = max(len(current_sentences), len(previous_sentences))
    changes = len(new_content) + len(removed_content)
    change_pct = (changes / total_sentences * 100) if total_sentences > 0 else 0
    
    return {
        "text_change_pct": round(change_pct, 1),
        "new_content": new_content[:20],
        "removed_content": removed_content[:20],
        "modified_content": modified_content[:10],
        "new_count": len(new_content),
        "removed_count": len(removed_content),
        "modified_count": len(modified_content)
    }


# =============================================================================
# MAIN PROCESSING FUNCTIONS
# =============================================================================

def process_document(
    text: str,
    doc_type: str = "10-K",
    ticker: str = "",
    filing_date: str = "",
    previous_text: str = ""
) -> Dict[str, Any]:
    """Process a document and extract all intelligence."""
    
    result = {
        "document_id": f"{ticker}_{doc_type}_{filing_date}".replace("-", ""),
        "company": {"ticker": ticker, "name": ""},
        "filing": {
            "type": doc_type,
            "date": filing_date,
            "description": FILING_TYPES.get(doc_type, "SEC Filing")
        },
        "processed": {
            "timestamp": datetime.now().isoformat(),
            "status": "complete"
        },
        "sections": {},
        "extracted_metrics": {},
        "risks": [],
        "risk_scores": {},
        "forward_looking": [],
        "delta": None,
        "summary": ""
    }
    
    # Detect sections
    sections = detect_sections(text)
    
    # Process each section
    for section_name, section_text in sections.items():
        summary = extractive_summarize(section_text, num_sentences=4)
        word_count = len(section_text.split())
        
        result["sections"][section_name] = {
            "text": section_text[:20000],  # Limit storage
            "summary": summary,
            "word_count": word_count
        }
    
    # Generate overall summary
    if "mda" in sections:
        result["summary"] = extractive_summarize(sections["mda"], num_sentences=5)
    elif "business" in sections:
        result["summary"] = extractive_summarize(sections["business"], num_sentences=5)
    else:
        result["summary"] = extractive_summarize(text[:10000], num_sentences=5)
    
    # Extract risks
    risk_text = sections.get("risk_factors", text[:20000])
    result["risks"] = extract_risks(risk_text)
    result["risk_scores"] = calculate_risk_scores(result["risks"])
    
    # Extract metrics
    result["extracted_metrics"] = extract_metrics(text)
    
    # Extract forward-looking statements
    result["forward_looking"] = extract_forward_looking(text[:30000])
    
    # Delta analysis if previous text provided
    if previous_text:
        result["delta"] = detect_changes(text, previous_text)
        
        # Update risk statuses based on delta
        if result["delta"]:
            for risk in result["risks"]:
                # Simple heuristic: if risk text contains new content words, mark as new
                risk_words = set(risk["text"].lower().split())
                new_words = set(' '.join(result["delta"]["new_content"]).lower().split())
                if len(risk_words & new_words) > 5:
                    risk["status"] = "new"
    
    return result


def get_filing_types() -> List[Dict[str, str]]:
    """Get available SEC filing types."""
    return [{"type": k, "description": v} for k, v in FILING_TYPES.items()]


def fetch_and_process_filing(ticker: str, filing_type: str = "10-K") -> Dict[str, Any]:
    """Fetch and process the most recent filing for a company."""
    try:
        filings = fetch_company_filings(ticker, filing_type, count=2)
        
        if not filings:
            return {"error": f"No {filing_type} filings found for {ticker}"}
        
        # Fetch current filing
        current_filing = filings[0]
        current_text = fetch_filing_text(current_filing["url"])
        
        if not current_text:
            return {"error": "Failed to fetch filing content"}
        
        # Fetch previous filing for comparison if available
        previous_text = ""
        if len(filings) > 1:
            try:
                previous_text = fetch_filing_text(filings[1]["url"])
            except Exception as e:
                logger.warning(f"Failed to fetch previous filing for {ticker}: {e}")
        
        # Process document
        result = process_document(
            text=current_text,
            doc_type=filing_type,
            ticker=ticker,
            filing_date=current_filing["date"],
            previous_text=previous_text
        )
        
        # Add company and filing info
        if "company" not in result:
            result["company"] = {}
        result["company"]["name"] = current_filing.get("company", ticker)
        
        if "filing" not in result:
            result["filing"] = {}
        result["filing"]["url"] = current_filing["url"]
        result["filing"]["date"] = current_filing["date"]
        
        # Add previous filing info if available
        if len(filings) > 1:
            result["filing"]["compared_to"] = {
                "date": filings[1]["date"],
                "url": filings[1]["url"]
            }
        
        return result
    except Exception as e:
        logger.error(f"Error in fetch_and_process_filing for {ticker}: {e}", exc_info=True)
        return {"error": f"Internal processing error: {str(e)}"}


def compare_documents(
    text1: str,
    text2: str,
    ticker: str = "",
    doc_type: str = "10-K"
) -> Dict[str, Any]:
    """Compare two documents and return comprehensive delta analysis."""
    
    # Process both documents
    doc1 = process_document(text1, doc_type, ticker, "current")
    doc2 = process_document(text2, doc_type, ticker, "previous")
    
    # Detailed comparison
    comparison = {
        "delta": detect_changes(text1, text2),
        "sections_comparison": {},
        "risk_evolution": {
            "new_risks": [],
            "removed_risks": [],
            "modified_risks": []
        },
        "metrics_comparison": {}
    }
    
    # Compare sections
    for section_name in set(doc1["sections"].keys()) | set(doc2["sections"].keys()):
        sect1 = doc1["sections"].get(section_name, {}).get("text", "")
        sect2 = doc2["sections"].get(section_name, {}).get("text", "")
        
        if sect1 and sect2:
            section_delta = detect_changes(sect1, sect2)
            comparison["sections_comparison"][section_name] = {
                "change_pct": section_delta["text_change_pct"],
                "word_count_change": len(sect1.split()) - len(sect2.split())
            }
        elif sect1:
            comparison["sections_comparison"][section_name] = {"status": "new_section"}
        else:
            comparison["sections_comparison"][section_name] = {"status": "removed_section"}
    
    # Compare risks
    risk1_ids = {r["text"][:100] for r in doc1["risks"]}
    risk2_ids = {r["text"][:100] for r in doc2["risks"]}
    
    for risk in doc1["risks"]:
        if risk["text"][:100] not in risk2_ids:
            comparison["risk_evolution"]["new_risks"].append(risk)
    
    for risk in doc2["risks"]:
        if risk["text"][:100] not in risk1_ids:
            comparison["risk_evolution"]["removed_risks"].append(risk)
    
    # Compare metrics
    for metric_name in set(doc1["extracted_metrics"].keys()) | set(doc2["extracted_metrics"].keys()):
        val1 = doc1["extracted_metrics"].get(metric_name, {}).get("value", 0)
        val2 = doc2["extracted_metrics"].get(metric_name, {}).get("value", 0)
        
        if val1 and val2:
            change = ((val1 - val2) / val2 * 100) if val2 else 0
            comparison["metrics_comparison"][metric_name] = {
                "current": val1,
                "previous": val2,
                "change_pct": round(change, 2)
            }
    
    comparison["current_document"] = doc1
    comparison["previous_document"] = doc2
    
    return comparison


# =============================================================================
# PHASE 14 ENHANCEMENTS: DISCLOSURE INTENSITY & MARGIN EXTRACTION
# =============================================================================

def calculate_disclosure_intensity(text: str) -> Dict[str, Any]:
    """
    Calculate disclosure intensity metrics.
    
    Measures how much detail the company provides in various areas.
    """
    text_lower = text.lower()
    word_count = len(text.split())
    
    # Define disclosure categories and their indicators
    disclosure_categories = {
        "risk_disclosure": {
            "indicators": ["risk", "uncertainty", "could", "may", "adverse", "material", 
                          "significant", "potential", "impact"],
            "weight": 1.0
        },
        "guidance_disclosure": {
            "indicators": ["expect", "anticipate", "guidance", "outlook", "forecast",
                          "target", "range", "estimate", "projection"],
            "weight": 1.2
        },
        "segment_disclosure": {
            "indicators": ["segment", "geography", "region", "division", "business unit",
                          "product line", "revenue breakdown", "operating segment"],
            "weight": 1.0
        },
        "competitive_disclosure": {
            "indicators": ["competition", "competitive", "market share", "competitor",
                          "pricing pressure", "industry dynamics"],
            "weight": 0.8
        },
        "esg_disclosure": {
            "indicators": ["sustainability", "environmental", "carbon", "emissions",
                          "diversity", "governance", "ESG", "climate", "social"],
            "weight": 1.0
        },
        "executive_disclosure": {
            "indicators": ["compensation", "bonus", "stock option", "incentive",
                          "golden parachute", "executive", "management change"],
            "weight": 0.7
        }
    }
    
    scores = {}
    details = {}
    
    for category, config in disclosure_categories.items():
        count = sum(text_lower.count(ind) for ind in config["indicators"])
        # Normalize by document length (per 1000 words)
        normalized_score = (count / max(1, word_count / 1000)) * config["weight"]
        scores[category] = round(min(100, normalized_score * 5), 1)  # Scale to 0-100
        details[category] = {"mention_count": count, "score": scores[category]}
    
    # Overall intensity (average)
    overall = sum(scores.values()) / len(scores) if scores else 0
    
    return {
        "overall_intensity": round(overall, 1),
        "category_scores": scores,
        "details": details,
        "word_count": word_count,
        "interpretation": (
            "High disclosure" if overall > 60 else
            "Moderate disclosure" if overall > 30 else
            "Low disclosure"
        )
    }


def extract_margins(text: str) -> Dict[str, Any]:
    """Extract margin metrics from financial text."""
    margins = {}
    
    # Margin patterns
    margin_patterns = {
        "gross_margin": r"(?:gross\s*margin|gross\s*profit\s*margin)[:\s]*(\d+\.?\d*)%?",
        "operating_margin": r"(?:operating\s*margin|operating\s*profit\s*margin)[:\s]*(\d+\.?\d*)%?",
        "net_margin": r"(?:net\s*margin|net\s*profit\s*margin)[:\s]*(\d+\.?\d*)%?",
        "ebitda_margin": r"(?:ebitda\s*margin)[:\s]*(\d+\.?\d*)%?"
    }
    
    for margin_name, pattern in margin_patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                value = float(matches[0])
                margins[margin_name] = {"value": value, "unit": "%"}
            except:
                pass
    
    return margins


def detect_red_flags(text: str) -> List[Dict[str, Any]]:
    """Detect potential red flags in document text."""
    red_flags = []
    text_lower = text.lower()
    
    # Red flag patterns
    flag_patterns = {
        "going_concern": {
            "pattern": r"going\s*concern|substantial\s*doubt|ability\s*to\s*continue",
            "severity": "critical",
            "description": "Going concern language detected"
        },
        "auditor_change": {
            "pattern": r"change\s*in\s*auditor|dismissal\s*of\s*independent|auditor\s*resignation",
            "severity": "high",
            "description": "Auditor change or dismissal indicated"
        },
        "restatement": {
            "pattern": r"restatement|restated|correct.{0,20}error|material\s*misstatement",
            "severity": "high",
            "description": "Financial restatement mentioned"
        },
        "internal_control_weakness": {
            "pattern": r"material\s*weakness|significant\s*deficiency|internal\s*control.{0,30}deficien",
            "severity": "medium",
            "description": "Internal control weakness disclosed"
        },
        "related_party": {
            "pattern": r"related\s*party\s*transaction|affiliate\s*transaction",
            "severity": "low",
            "description": "Related party transactions disclosed"
        },
        "litigation_risk": {
            "pattern": r"litigation|lawsuit|legal\s*proceeding|class\s*action|settlement",
            "severity": "medium",
            "description": "Significant litigation mentioned"
        }
    }
    
    for flag_name, config in flag_patterns.items():
        matches = re.findall(config["pattern"], text_lower)
        if matches:
            red_flags.append({
                "type": flag_name,
                "severity": config["severity"],
                "description": config["description"],
                "occurrences": len(matches)
            })
    
    return red_flags


def analyze_document_enhanced(
    text: str,
    doc_type: str = "10-K",
    ticker: str = "",
    filing_date: str = ""
) -> Dict[str, Any]:
    """
    Enhanced document analysis with Phase 14 features.
    
    Includes disclosure intensity, margin extraction, and red flag detection.
    """
    # Standard processing
    result = process_document(text, doc_type, ticker, filing_date)
    
    # Add enhanced analysis
    result["disclosure_intensity"] = calculate_disclosure_intensity(text)
    result["margins"] = extract_margins(text)
    result["red_flags"] = detect_red_flags(text)
    
    # Risk category score summary
    if result["risk_scores"]:
        result["risk_summary"] = {
            "highest_risk_category": max(result["risk_scores"], key=result["risk_scores"].get),
            "lowest_risk_category": min(result["risk_scores"], key=result["risk_scores"].get),
            "total_risks_identified": len(result["risks"])
        }
    
    return result

