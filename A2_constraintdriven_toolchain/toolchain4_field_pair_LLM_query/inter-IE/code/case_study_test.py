#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single Field Pair Test - Manual DSL Generation Test
测试特定字段对的 DSL 生成（使用高质量 evidence）
"""

import json
import sys
import os
from openai import OpenAI

# 复用的配置
API_KEY = "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"
MODEL = "gpt-4o"

# 复用的 Prompt Template
PROMPT_TEMPLATE = """You are a 3GPP specification expert and protocol testing engineer.

Goal: Decide if there is a VALID semantic constraint of type {{CrossReference, ValueDependency, RangeAlignment, Association, Conditional}} between two fields from DIFFERENT IEs for 5G RRC message mutation. If not strictly supported by evidence, output NO_RULE.

CRITICAL: This is INTER-IE constraint. The two fields come from DIFFERENT Information Elements.

Inputs:
- IE Pair: {ie1} ↔ {ie2}
- Target fields (from DIFFERENT IEs): 
  - field1 = {field1} (from {ie1})
  - field2 = {field2} (from {ie2})
- Evidence snippets (verbatim from 3GPP): 
{evidence_text}

## CRITICAL REQUIREMENT
This is an INTER-IE constraint. The constraint MUST relate field1 (from {ie1}) to field2 (from {ie2}).
If evidence only describes single-IE behavior → NO_RULE

Strict Rules:
1) EVIDENCE-ONLY. Use ONLY the provided snippets. No external memory.
2) NORMATIVE CHECK. Accept only constraints backed by explicit normative wording (shall/shall not/only/only if/must) OR explicit math/table relations. If wording is "should", mark advisory=true and still return NO_RULE unless a non-advisory relation also exists.
3) INTER-IE SCOPE. The constraint MUST relate field1 (from {ie1}) to field2 (from {ie2}). If evidence only describes single IE behavior, output NO_RULE.
4) DIRECTION & TRIGGER. Identify the correct trigger condition(s) and avoid reversing implication.
5) MACHINE-CHECKABLE. The DSL must use the canonical grammar below and be directly checkable (no vague words).
6) UNITS & ENUMS. Normalize any required units or enum-to-number mapping explicitly (e.g., n1→1, n2→2). If unknown, output NO_RULE.
7) VERSION/SCOPE GUARDS. If the rule only applies under specific releases/options, include them in `preconditions`.
8) LOGICAL CONSISTENCY 
- Check for contradictions before outputting DSL
- Verify constraint is logically feasible
- If impossible or contradictory → NO_RULE

Allowed Types and Canonical DSL Grammar:

For Inter-IE constraints, use field1 and field2 to refer to the two fields:

- CrossReference (ID/reference matching):
  - MATCH(field1, field2)          // IDs must match
  - EQ(field1, field2)              // Values must be equal
  
- ValueDependency (value determines valid values):
  - IMPLIES(EQ(field1, value), EQ(field2, value))
  - IMPLIES(IN(field1, {{v1,v2}}), IN(field2, {{v1,v2}}))
  - MAP(field1, field2, {{a->b, c->d}})
  
- RangeAlignment (coordinated ranges):
  - IMPLIES(EQ(field1, X), AND(GE(field2, min), LE(field2, max)))
  - LT(field1, field2) | LE(field1, field2) | GT(field1, field2) | GE(field1, field2)
  
- Association (logical association):
  - ASSOCIATED(field1, field2, condition)
  - IMPLIES(condition_on_field1, requirement_on_field2)
  
- Conditional (conditional constraints):
  - CONDITIONAL(EQ(field1, X), action_on_field2)

Basic Operators:
- EQ(X,Y) | NE(X,Y)
- IN(X,{{v1,v2,...}})
- LT(X,Y) | LE(X,Y) | GT(X,Y) | GE(X,Y)
- AND(...) | OR(...) | NOT(...)
- IMPLIES(condition, result)
- MATCH(field1, field2)

Output JSON ONLY:
{{
  "result": "DSL | NO_RULE",
  "type": "CrossReference | ValueDependency | RangeAlignment | Association | Conditional",
  "dsl": "formal DSL expression using operators above",
  "preconditions": ["list any preconditions"],
  "predicate": "human-readable predicate description",
  "advisory": false,
  "examples": {{
    "valid": ["concrete assignment example"],
    "invalid": ["concrete assignment example"]
  }},
  "notes": "1-2 lines explaining why NO_RULE or edge-guards",
  "version_tags": ["r16","r17"]
}}

Decision rules for NO_RULE:
- Evidence lacks both target fields or doesn't relate them across IEs.
- Evidence is purely definitional without cross-field relation.
- Only 'should' guidance with no non-advisory constraint.
- Requires external assumptions not present in evidence.
- Evidence only describes single-IE behavior.

Examples:

1. CrossReference (ID matching):
   DSL: "MATCH(field1, field2)"
   Type: CrossReference
   
2. ValueDependency:
   DSL: "IMPLIES(EQ(field1, 'typeD'), EQ(field2, 'enabled'))"
   Type: ValueDependency
   
3. Conditional with range:
   DSL: "IMPLIES(IN(field1, {{1,2,3}}), AND(GE(field2, 0), LE(field2, 9)))"
   Type: RangeAlignment
"""

def format_evidences_for_prompt(evidences):
    """Format evidence list into prompt text"""
    formatted_blocks = []
    
    for idx, evidence in enumerate(evidences, 1):
        section = evidence.get('section_number', 'N/A')
        title = evidence.get('section_title', 'Unknown')
        source = evidence.get('source_file', 'Unknown')
        confidence = evidence.get('confidence', 'UNKNOWN')
        sentence = evidence.get('text', '')
        
        block = f"""---EVIDENCE #{idx}---
[Source: {source} | Section {section}: {title} | Confidence: {confidence}]
{sentence}"""
        formatted_blocks.append(block)
    
    return "\n\n".join(formatted_blocks)

def call_chatgpt_api(prompt):
    """Call ChatGPT API"""
    try:
        client = OpenAI(api_key=API_KEY)
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a 3GPP specification expert. Always respond with valid JSON using the exact format specified."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response
        if response_text.startswith('```json'):
            response_text = response_text.strip('```json').strip('```').strip()
        elif response_text.startswith('```'):
            response_text = response_text.strip('```').strip()
        
        result = json.loads(response_text)
        return result
            
    except Exception as e:
        print(f"❌ API call error: {str(e)}")
        return None

def main():
    print("="*80)
    print("🧪 Single Field Pair DSL Generation Test")
    print("="*80)
    
    # 配置
    AGGREGATED_FILE = "../output/inter_ie_aggregated/aggregated_inter_ie_field_pairs.json"
    TARGET_KEY = "commoncontrolresourceset___controlresourcesetid___commonsearchspacelist___controlresourcesetid"
    OUTPUT_FILE = "test_dsl_result.json"
    
    print(f"\n📂 Loading aggregated data...")
    print(f"   File: {AGGREGATED_FILE}")
    print(f"   Target: {TARGET_KEY}")
    
    # 加载聚合数据
    try:
        with open(AGGREGATED_FILE, 'r', encoding='utf-8') as f:
            aggregated_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # 获取目标 field pair
    if TARGET_KEY not in aggregated_data:
        print(f"❌ Target key not found: {TARGET_KEY}")
        return
    
    field_pair_data = aggregated_data[TARGET_KEY]
    
    print(f"\n✅ Found field pair data")
    print(f"   Total evidences: {len(field_pair_data['evidences'])}")
    
    # 筛选 HIGH confidence 且 combined_score = 20 的 evidence
    high_quality_evidences = [
        e for e in field_pair_data['evidences']
        if e.get('confidence') == 'HIGH' 
        and e.get('section_relevance', {}).get('combined_score', 0) == 20
    ]
    
    print(f"   HIGH confidence + score=20: {len(high_quality_evidences)}")
    
    # 进一步筛选：优先选择section 10.1的evidence（最相关的章节）
    section_10_1_evidences = [
        e for e in high_quality_evidences
        if e.get('section_number') == '10.1'
    ]
    
    print(f"   From section 10.1: {len(section_10_1_evidences)}")
    
    # 如果section 10.1有evidence，按关键词优先排序
    if section_10_1_evidences:
        # 定义关键词（最相关的evidence应该包含这些词）
        keywords = [
            'association between',
            'search space set',
            'controlResourceSetId',
            'by controlResourceSet'
        ]
        
        # 计算每条evidence的相关性得分
        def relevance_score(evidence):
            text = evidence.get('text', '').lower()
            score = 0
            for keyword in keywords:
                if keyword.lower() in text:
                    score += 1
            return score
        
        # 按相关性排序（高分在前）
        section_10_1_evidences.sort(key=relevance_score, reverse=True)
        
        # 显示排序后的前3条得分
        print(f"   Top 3 relevance scores:")
        for idx, e in enumerate(section_10_1_evidences[:3], 1):
            score = relevance_score(e)
            preview = e['text'][:80]
            print(f"     {idx}. Score={score}: {preview}...")
        
        high_quality_evidences = section_10_1_evidences[:10]  # 限制最多10条
        print(f"   ✅ Using top 10 by relevance from section 10.1")
    else:
        high_quality_evidences = high_quality_evidences[:10]  # 限制最多10条
        print(f"   ⚠️  No section 10.1 evidences, using top 10 from all")
    
    if not high_quality_evidences:
        print(f"❌ No suitable evidences found!")
        return
    
    # 提取 IE 和字段信息
    ie1 = field_pair_data['ie_pair'][0]
    ie2 = field_pair_data['ie_pair'][1]
    field1 = field_pair_data['field_pair'][0]
    field2 = field_pair_data['field_pair'][1]
    
    print(f"\n🎯 Test Configuration:")
    print(f"   IE1: {ie1}")
    print(f"   Field1: {field1}")
    print(f"   IE2: {ie2}")
    print(f"   Field2: {field2}")
    print(f"   Evidence count: {len(high_quality_evidences)}")
    
    # 显示将要使用的 evidence
    print(f"\n📝 Evidence to be used:")
    for idx, evidence in enumerate(high_quality_evidences, 1):
        text = evidence['text']
        text_preview = text[:100] + "..." if len(text) > 100 else text
        print(f"   {idx}. [{evidence['confidence']}] {text_preview}")
    
    # 调试：显示完整的前3条evidence
    print(f"\n🔍 First 3 evidences (full text for debugging):")
    for idx, evidence in enumerate(high_quality_evidences[:3], 1):
        print(f"\n--- Evidence #{idx} ---")
        print(evidence['text'][:500])  # 显示前500字符
    
    # 格式化 evidence
    evidence_text = format_evidences_for_prompt(high_quality_evidences)
    
    # 构造 prompt
    prompt = PROMPT_TEMPLATE.format(
        ie1=ie1,
        ie2=ie2,
        field1=field1,
        field2=field2,
        evidence_text=evidence_text
    )
    
    # 估算 token 数
    estimated_tokens = len(prompt) // 4
    print(f"\n📊 Prompt stats:")
    print(f"   Estimated tokens: {estimated_tokens}")
    print(f"   Prompt length: {len(prompt)} chars")
    
    # 询问用户是否继续
    print(f"\n⚠️  This will call OpenAI API (cost: ~$0.01)")
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Aborted.")
        return
    
    # 调用 API
    print(f"\n🔄 Calling OpenAI API...")
    api_response = call_chatgpt_api(prompt)
    
    if not api_response:
        print(f"❌ Failed to get API response")
        return
    
    # 显示结果
    print(f"\n{'='*80}")
    print("📊 API Response")
    print(f"{'='*80}")
    print(json.dumps(api_response, indent=2, ensure_ascii=False))
    
    # 保存完整结果
    result = {
        "test_config": {
            "ie1": ie1,
            "field1": field1,
            "ie2": ie2,
            "field2": field2,
            "evidence_count": len(high_quality_evidences),
            "model": MODEL
        },
        "evidences_used": high_quality_evidences,
        "api_response": api_response,
        "prompt": prompt
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full result saved to: {OUTPUT_FILE}")
    
    # 总结
    print(f"\n{'='*80}")
    print("📋 Summary")
    print(f"{'='*80}")
    
    if api_response.get("result") == "DSL":
        print(f"✅ SUCCESS - DSL Generated!")
        print(f"   Type: {api_response.get('type')}")
        print(f"   DSL: {api_response.get('dsl')}")
        print(f"   Predicate: {api_response.get('predicate')}")
    else:
        print(f"⭕ NO_RULE")
        print(f"   Reason: {api_response.get('notes')}")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()