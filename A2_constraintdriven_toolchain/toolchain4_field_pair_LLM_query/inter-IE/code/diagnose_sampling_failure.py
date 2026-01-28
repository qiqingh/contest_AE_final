#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnose why sampling failed for the core requirement case
"""

import json
from collections import Counter

AGGREGATED_FILE = "../output/inter_ie_aggregated/aggregated_inter_ie_field_pairs.json"
TARGET_KEY = "pdcch-configcommon_commoncontrolresourceset___controlresourcesetid___pdcch-configcommon_commonsearchspacelist___controlresourcesetid"

def calculate_relevance_score(evidence):
    """Same scoring as in the batch script"""
    confidence_priority = {'HIGH': 40, 'MEDIUM': 30, 'LOW': 20, 'VERY_LOW': 10, 'UNKNOWN': 0}
    
    inter_ie_patterns = [
        # CRITICAL phrases (100 points each) - MUST be in top 10
        ('association between', 100),  # Massive increase to beat all noise
        ('reference between', 100),
        
        # High-value phrases (20-25 points)
        ('shall match', 25),
        ('reference to', 20),
        ('refers to', 20),
        
        # Low-value phrases (1-3 points)
        ('match', 1),  # Nearly eliminated
        ('associated with', 3),
        ('referenced by', 3),
        ('linked to', 3),
        ('corresponds to', 3),
    ]
    
    # 1. Confidence score
    confidence = evidence.get('confidence', 'UNKNOWN')
    confidence_score = confidence_priority.get(confidence, 0)
    
    # 2. Section relevance score
    section_relevance = evidence.get('section_relevance', {})
    section_score = section_relevance.get('combined_score', 0)
    
    # 3. Keyword matching
    text = evidence.get('text', '').lower()
    keyword_score = 0
    
    for pattern, points in inter_ie_patterns:
        if pattern in text:
            keyword_score += points
    
    # 4. Field mention bonus
    field_mention_count = 0
    for field_indicator in ['id', 'index', 'identifier', 'reference']:
        field_mention_count += text.count(field_indicator)
    
    if field_mention_count >= 2:
        keyword_score += 5
    
    # 5. SUPER CRITICAL: Combination bonus for Section 10.1 + "association between"
    section_num = evidence.get('section_number', '')
    has_association_between = 'association between' in text
    
    if section_num == '10.1' and has_association_between:
        keyword_score += 300  # MASSIVE bonus for golden combination
    elif section_num == '10.1':
        keyword_score += 30  # Section alone
    
    total_score = confidence_score + section_score + keyword_score
    return total_score

def main():
    print("="*80)
    print("🔍 Sampling Failure Diagnosis")
    print("="*80)
    
    # Load aggregated data
    with open(AGGREGATED_FILE, 'r') as f:
        data = json.load(f)
    
    if TARGET_KEY not in data:
        print(f"❌ Key not found: {TARGET_KEY}")
        return
    
    field_pair_data = data[TARGET_KEY]
    evidences = field_pair_data['evidences']
    
    print(f"\n📊 Data Summary:")
    print(f"   Total evidences: {len(evidences)}")
    print(f"   Confidence distribution: {field_pair_data['confidence_counts']}")
    
    # Calculate scores for all evidences
    scored_evidences = []
    for e in evidences:
        score = calculate_relevance_score(e)
        scored_evidences.append((score, e))
    
    # Sort by score
    scored_evidences.sort(key=lambda x: x[0], reverse=True)
    
    # Analyze top 50 (what would be sampled with new config)
    print(f"\n📝 Top 50 Evidences (What batch script would sample with MAX_EVIDENCES_PER_PAIR=50):")
    print("-"*80)
    
    for idx, (score, e) in enumerate(scored_evidences[:50], 1):
        conf = e.get('confidence', 'UNKNOWN')
        section = e.get('section_number', 'N/A')
        section_score = e.get('section_relevance', {}).get('combined_score', 0)
        text_preview = e.get('text', '')[:80]
        
        # Check for key phrase
        has_association = 'association between' in e.get('text', '').lower()
        marker = " ✅ KEY!" if has_association else ""
        
        print(f"{idx:2d}. Score={score:3.0f} (conf={conf}:{40 if conf=='HIGH' else 0}, "
              f"section={section_score}, section={section}){marker}")
        print(f"    {text_preview}...")
        print()
    
    # Find where "association between" evidences are
    print("\n🔎 Location of 'association between' evidences:")
    print("-"*80)
    
    found_count = 0
    for idx, (score, e) in enumerate(scored_evidences, 1):
        text = e.get('text', '').lower()
        if 'association between' in text and 'search space' in text:
            found_count += 1
            section = e.get('section_number', 'N/A')
            section_score = e.get('section_relevance', {}).get('combined_score', 0)
            conf = e.get('confidence', 'UNKNOWN')
            
            print(f"Rank #{idx:3d} | Score={score:3.0f} | Section={section} | "
                  f"Conf={conf} | SectionScore={section_score}")
            print(f"  Text: {e.get('text', '')[:120]}...")
            print()
            
            if idx <= 50:
                print("  ✅ This WOULD be sampled (in top 50)")
            else:
                print(f"  ❌ This would NOT be sampled (rank {idx} > 50)")
            print()
    
    if found_count == 0:
        print("❌ NO 'association between' evidence found!")
    else:
        print(f"\n📊 Found {found_count} 'association between' evidence(s)")
    
    # Section distribution in top 50
    print("\n📂 Section distribution in top 50:")
    sections = [e.get('section_number', 'N/A') for _, e in scored_evidences[:50]]
    section_counts = Counter(sections)
    for section, count in section_counts.most_common():
        print(f"   {section}: {count} evidences")
    
    # Section distribution of HIGH + score=20
    print("\n📊 Section distribution of HIGH confidence + score=20:")
    high_quality = [e for e in evidences 
                   if e.get('confidence') == 'HIGH' 
                   and e.get('section_relevance', {}).get('combined_score', 0) == 20]
    print(f"   Total: {len(high_quality)}")
    sections_hq = Counter([e.get('section_number', 'N/A') for e in high_quality])
    for section, count in sections_hq.most_common(5):
        print(f"   {section}: {count} evidences")

if __name__ == "__main__":
    main()