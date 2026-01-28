#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze High-Scoring Noise Evidence
Why does Section 6.3.2 dominate the top 50?
"""

import json
import sys

sys.path.insert(0, '.')
from generate_inter_ie_dsl_concurrent_improved import sample_evidences_smart

AGGREGATED_FILE = "../output/inter_ie_aggregated/aggregated_inter_ie_field_pairs.json"
TARGET_KEY = "pdcch-configcommon_commoncontrolresourceset___controlresourcesetid___pdcch-configcommon_commonsearchspacelist___controlresourcesetid"

def calculate_score_detailed(evidence):
    """Calculate score with detailed breakdown"""
    confidence_priority = {'HIGH': 40, 'MEDIUM': 30, 'LOW': 20, 'VERY_LOW': 10, 'UNKNOWN': 0}
    
    # 1. Confidence
    conf = evidence.get('confidence', 'UNKNOWN')
    conf_score = confidence_priority.get(conf, 0)
    
    # 2. Section relevance
    section_rel = evidence.get('section_relevance', {})
    section_score = section_rel.get('combined_score', 0)
    
    # 3. Keywords
    text = evidence.get('text', '').lower()
    
    keyword_breakdown = {}
    patterns = [
        ('association between', 100),
        ('reference between', 100),
        ('shall match', 25),
        ('reference to', 20),
        ('refers to', 20),
        ('match', 1),
        ('associated with', 3),
        ('referenced by', 3),
        ('linked to', 3),
        ('corresponds to', 3),
    ]
    
    keyword_total = 0
    for pattern, points in patterns:
        if pattern in text:
            keyword_breakdown[pattern] = points
            keyword_total += points
    
    # 4. Field mentions
    field_count = sum(text.count(x) for x in ['id', 'index', 'identifier', 'reference'])
    field_bonus = 5 if field_count >= 2 else 0
    
    # 5. Section 10.1 bonus
    section_num = evidence.get('section_number', '')
    has_association = 'association between' in text
    
    if section_num == '10.1' and has_association:
        section_bonus = 300
    elif section_num == '10.1':
        section_bonus = 30
    else:
        section_bonus = 0
    
    total = conf_score + section_score + keyword_total + field_bonus + section_bonus
    
    return {
        'total': total,
        'confidence': conf_score,
        'section_relevance': section_score,
        'keywords': keyword_total,
        'keyword_details': keyword_breakdown,
        'field_bonus': field_bonus,
        'section_bonus': section_bonus,
        'section': section_num,
        'text_preview': text[:150]
    }

def main():
    print("="*80)
    print("🔍 Analyzing High-Scoring Noise Evidence")
    print("="*80)
    
    # Load data
    with open(AGGREGATED_FILE, 'r') as f:
        data = json.load(f)
    
    field_pair_data = data[TARGET_KEY]
    evidences = field_pair_data['evidences']
    
    # Sample
    sampled = sample_evidences_smart(evidences, 70)
    
    print(f"\n📊 Analyzing top 70 sampled evidences")
    print()
    
    # Analyze section 6.3.2 evidences
    section_632_evidences = [e for e in sampled if e.get('section_number') == '6.3.2']
    
    print(f"🔬 Section 6.3.2 Analysis ({len(section_632_evidences)} evidences)")
    print("="*80)
    print()
    
    # Show top 10 from section 6.3.2
    print("Top 10 from Section 6.3.2:")
    print("-"*80)
    
    for idx, e in enumerate(section_632_evidences[:10], 1):
        breakdown = calculate_score_detailed(e)
        
        print(f"\n{idx}. Total Score: {breakdown['total']}")
        print(f"   Breakdown:")
        print(f"     - Confidence: {breakdown['confidence']}")
        print(f"     - Section Relevance: {breakdown['section_relevance']}")
        print(f"     - Keywords: {breakdown['keywords']} {breakdown['keyword_details']}")
        print(f"     - Field Bonus: {breakdown['field_bonus']}")
        print(f"   Text: {breakdown['text_preview']}...")
    
    print("\n" + "="*80)
    print("📊 Summary Statistics")
    print("="*80)
    
    # Score distribution for section 6.3.2
    scores_632 = [calculate_score_detailed(e)['total'] for e in section_632_evidences]
    avg_632 = sum(scores_632) / len(scores_632) if scores_632 else 0
    
    print(f"\nSection 6.3.2:")
    print(f"  Average score: {avg_632:.1f}")
    print(f"  Min score: {min(scores_632) if scores_632 else 0}")
    print(f"  Max score: {max(scores_632) if scores_632 else 0}")
    
    # Check section_relevance.combined_score distribution
    section_rel_scores = [e.get('section_relevance', {}).get('combined_score', 0) 
                         for e in section_632_evidences]
    
    print(f"\n  Section relevance scores:")
    from collections import Counter
    score_dist = Counter(section_rel_scores)
    for score, count in sorted(score_dist.items(), reverse=True):
        print(f"    {score}: {count} evidences")
    
    # Check what keywords they match
    print(f"\n  Matched keywords:")
    all_keywords = []
    for e in section_632_evidences:
        breakdown = calculate_score_detailed(e)
        all_keywords.extend(breakdown['keyword_details'].keys())
    
    keyword_counts = Counter(all_keywords)
    for kw, count in keyword_counts.most_common():
        print(f"    '{kw}': {count} times")
    
    # Compare with section 10.1
    section_101_evidences = [e for e in sampled if e.get('section_number') == '10.1']
    if section_101_evidences:
        scores_101 = [calculate_score_detailed(e)['total'] for e in section_101_evidences]
        avg_101 = sum(scores_101) / len(scores_101)
        
        print(f"\nSection 10.1 (for comparison):")
        print(f"  Count: {len(section_101_evidences)}")
        print(f"  Average score: {avg_101:.1f}")
        print(f"  Max score: {max(scores_101)}")
    
    print("\n" + "="*80)
    print("💡 Insights")
    print("="*80)
    
    # Insight 1: Why is 6.3.2 scoring high?
    high_section_rel = [s for s in section_rel_scores if s >= 20]
    if len(high_section_rel) > len(section_rel_scores) * 0.5:
        print("\n⚠️  Most 6.3.2 evidences have high section_relevance scores (≥20)")
        print("   → This suggests toolchain3 incorrectly marked them as relevant")
    
    # Insight 2: Keyword pollution
    if 'match' in keyword_counts or 'associated with' in keyword_counts:
        print("\n⚠️  Many 6.3.2 evidences contain generic keywords ('match', 'associated with')")
        print("   → These are likely false positives (single-IE descriptions)")
    
    # Insight 3: Are they actually inter-IE?
    print("\n🔍 Random sample of 6.3.2 evidence content:")
    for e in section_632_evidences[:3]:
        text = e.get('text', '')[:300]
        print(f"\n   {text}...")
        
        if 'search space' not in text.lower() or 'coreset' not in text.lower():
            print("   ❌ Does NOT mention both SearchSpace and CORESET")
        elif 'association' not in text.lower():
            print("   ⚠️  Mentions both but no 'association' keyword")

if __name__ == "__main__":
    main()