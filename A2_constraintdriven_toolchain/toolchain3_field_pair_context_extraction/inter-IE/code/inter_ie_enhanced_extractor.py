#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inter-IE Enhanced Constraint Extractor
Cross-IE Enhanced Constraint Extractor

Main improvements:
1. Chapter Relevance Scoring System (Dual IE) - as a bonus feature
2. Multi-signal confidence rating (HIGH/MEDIUM/LOW/VERY_LOW)
3. Smart field pair filtering
4. Class Encapsulation Design
5. Performance Optimization (Caching + Precomputation + Batching + Multiprocessing)

Based on:
- Best Practices for Intra-IE Enhanced Edition
- Protocol knowledge of Inter-IE
"""

import json
import os
import re
import glob
from itertools import product, combinations
from typing import List, Dict, Tuple, Set
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial, lru_cache
import multiprocessing
import time
from pathlib import Path

# ============================================================================
# User Configuration Area - Modify all parameters and paths here
# ============================================================================

# Path Configuration
IE_DIR = "../../../toolchain2_IE_collection/inter-IE/outputs/inter-IE_strategy/selected_ies"
SPEC_DIR = "../../../toolchain1_3GPP_preprocessing/outputs/txt_specifications_mathpix/txt_specifications_mathpix_md"
CLUSTER_CONFIG_PATH = "./cluster_config_aggressive_inter_ie.json"
OUTPUT_DIR = "../output/context_enhanced"

# Field-to-generation strategy
# Optional values: 'smart' | 'all' | 'reference-only'
FIELD_PAIR_STRATEGY = 'smart'  # Recommended: smart (intelligent filtering)

# Performance Configuration
MAX_IE_WORKERS = 5  # IE's concurrent connections per level
MAX_SPEC_WORKERS = 10  # Regulate the number of file-level parallelism
ENABLE_IE_PARALLEL = True  # Enable IE-level parallelism
ENABLE_SPEC_PARALLEL = True  # Enable standard file-level parallelization

# Debug mode
DEBUG_MODE = False

# Chapter relevance threshold (retained but with reduced effect)
LOW_RELEVANCE_THRESHOLD = 0.0  # 0.0 = retain all constraints

# Dual IE Chapter Rating Bonus Coefficient
BOTH_IE_MATCH_BONUS = 1.2  # IE matching bonus (1.0-2.0)

# ============================================================================
# Global functions for multiprocessing
# ============================================================================

def process_spec_file_for_inter_ie(spec_file: str, 
                                   field_pairs_with_sources: List[Tuple[Tuple[str, str], Tuple[str, str]]],
                                   field_patterns: Dict[str, Dict],
                                   ie1_variants: List[str],
                                   ie2_variants: List[str],
                                   debug: bool = False) -> List[Dict]:
    """Multi-process handling of single specification file"""
    extractor = InterIEEnhancedConstraintExtractor(debug=debug)
    return extractor.extract_constraints_from_file_optimized(
        spec_file, field_pairs_with_sources, field_patterns, 
        ie1_variants, ie2_variants
    )

# ============================================================================
# Inter-IE Enhanced Constraint Extractor Class
# ============================================================================

class InterIEEnhancedConstraintExtractor:
    """
    Cross-IE Enhanced Constraint Extractor
    
    Integrated:
    - Intra-IE chapter scoring, confidence levels, and optimization techniques
    - Inter-IE protocol knowledge and special patterns
    
    Innovation:
    - Multi-signal confidence assessment (independent of chapter matching)
    - Smart field pair filtering
    - Extended output format
    """
    
    def __init__(self, debug=False, strict_mode=True):
        self.debug = debug
        self.strict_mode = strict_mode
        
        # Cache
        self._pattern_cache = {}
        self._compiled_pattern_cache = {}
        
        # ============ Protocol Term Abbreviation Mapping Table (Inter-IE Complete Version) ============
        self.acronym_mappings = {
            'controlresourceset': ['coreset', 'crs', 'control resource set'],
            'physicaldownlinkcontrolchannel': ['pdcch'],
            'physicaldownlinksharedchannel': ['pdsch'],
            'physicaluplinkcontrolchannel': ['pucch'],
            'physicaluplinksharedchannel': ['pusch'],
            'demodulationreferencesignal': ['dmrs', 'dm-rs'],
            'channelstateinformation': ['csi'],
            'soundingreferencesignal': ['srs'],
            'transmissionconfigurationindicator': ['tci'],
            'quasicolocation': ['qcl'],
            'physicalresourceblock': ['prb'],
            'resourceblockgroup': ['rbg'],
            'synchronizationsignalblock': ['ssb', 'ss-pbch'],
            'modulationandcodingscheme': ['mcs'],
            'downlinkcontrolinformation': ['dci'],
            'uplinkcontrolinformation': ['uci'],
            'hybridautomaticrepeatrequest': ['harq'],
            'mediumaccesscontrol': ['mac'],
            'radiolinkcontrol': ['rlc'],
            'packetdataconvergenceprotocol': ['pdcp'],
            'radionetworktemporaryidentifier': ['rnti'],
            'searchspace': ['ss', 'search space'],
            'bandwidthpart': ['bwp'],
            'bufferstatusreporting': ['bsr', 'buffer status'],
            'powerheadroomreporting': ['phr', 'power headroom'],
            'schedulingrequest': ['sr'],
            'discontinuousreception': ['drx'],
            'timingadvancegroup': ['tag', 'timing advance'],
            'semipersistentscheduling': ['sps'],
            'commonresourceset': ['coreset0'],
            'dedicatedresourceset': ['coreset1'],
            'timedomainresourceallocation': ['tdra'],
            'frequencydomainresourceallocation': ['fdra'],
            'aggregationlevel': ['al'],
            'cyclicprefix': ['cp'],
            'subcarrierspacing': ['scs'],
            'resourceelementgroup': ['reg'],
            'controlchannelelement': ['cce'],
        }
        
        # Reverse mapping
        self.acronym_reverse_mappings = {}
        for fullname, acronyms in self.acronym_mappings.items():
            for acronym in acronyms:
                if acronym not in self.acronym_reverse_mappings:
                    self.acronym_reverse_mappings[acronym] = []
                self.acronym_reverse_mappings[acronym].append(fullname)
        
        # ============ Constraint Keywords (Complete Version) ============
        self.constraint_keywords = [
            # Mandatory requirements
            'shall', 'shall not', 'shall be', 'shall have',
            'must', 'must not', 'must be', 'must have',
            'mandatory', 'required', 'required to', 'required that',
            'need to', 'needs to', 'needed',
            
            # Conditional requirements
            'if', 'when', 'whenever', 'where', 'given that',
            'provided that', 'assuming', 'in case',
            'only if', 'if and only if', 'iff',
            'unless', 'except when', 'except if',
            'valid only if', 'valid only when', 'valid if',
            'applicable only if', 'applicable when',
            
            # Dependency relationships
            'depends on', 'dependent on', 'depending on',
            'determined by', 'defined by', 'specified by',
            'according to', 'based on', 'derived from',
            
            # Prohibitions and restrictions
            'prohibited', 'not allowed', 'not permitted',
            'forbidden', 'disallowed', 'invalid if',
            'cannot', 'may not', 'should not',
            'limited to', 'restricted to', 'constrained by',
            'subject to', 'conditional on',
            
            # Necessity and requirements
            'necessary', 'necessarily', 'essential',
            'prerequisite', 'precondition',
            'require', 'requires', 'requiring',
            
            # Additional common constraint words
            'ensure', 'ensures', 'ensuring',
            'guarantee', 'guarantees',
            'enforce', 'enforces', 'enforcing',
            'comply', 'complies', 'compliance',
            'conform', 'conforms', 'conformance',
            
            # Equality and consistency constraints
            'same', 'same value', 'same as', 'identical', 'identical to',
            'equal', 'equal to', 'equals', 'equivalent', 'equivalent to',
            'match', 'matches', 'matching',
            'consistent', 'consistent with', 'consistency',
            'aligned', 'aligned with', 'alignment',
            'correspond', 'corresponds', 'corresponding',
            
            # Configure and set actions
            'set', 'sets', 'setting', 'set to',
            'configure', 'configures', 'configured',
            'assign', 'assigns', 'assigned',
            'apply', 'applies', 'applied',
            'use', 'uses', 'using',
            'indicate', 'indicates', 'indication',
            
            # Timing and conditional triggering
            'upon', 'upon receiving', 'upon reconfiguration',
            'after', 'before', 'during', 'following',
            'once', 'as soon as',
            
            # Difference constraint
            'different', 'different from', 'differs',
            'distinct', 'separate', 'independent'
        ]
        
        self.constraint_keywords = sorted(list(set(self.constraint_keywords)))
        
        # Precompiled constraint keyword regex
        self.constraint_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in self.constraint_keywords) + r')\b',
            re.IGNORECASE
        )
        
        # ============ Special Constraint Mode (Inter-IE Exclusive) ============
        self.special_constraint_patterns = [
            # Pattern 1: "sets X and Y to the same value"
            re.compile(
                r'\bsets?\b.*?\bto\s+the\s+same\s+value\b',
                re.IGNORECASE
            ),
            # Pattern 2: "X and Y shall be equal/identical/same"
            re.compile(
                r'\b(shall|must|is|are)\s+(be\s+)?(equal|identical|the\s+same)\b',
                re.IGNORECASE
            ),
            # Pattern 3: "X matches/corresponds to Y"
            re.compile(
                r'\b(match|correspond|align)s?\s+(to|with)\b',
                re.IGNORECASE
            ),
            # Pattern 4: "both X and Y"
            re.compile(
                r'\bboth\b.*?\band\b',
                re.IGNORECASE
            ),
            # Pattern 5: "X takes the value of Y"
            re.compile(
                r'\btakes?\s+(the\s+)?value\s+(of|from)?\b',
                re.IGNORECASE
            ),
            # Pattern 6: "upon ... the network sets/configures"
            re.compile(
                r'\bupon\b.*?\b(set|configure|assign|apply)s?\b',
                re.IGNORECASE
            ),
            # Pattern 7: "same X" or "identical X"
            re.compile(
                r'\b(same|identical)\s+\w+',
                re.IGNORECASE
            )
        ]
        
        self.special_pattern_names = [
            'same_value_pattern',
            'equality_pattern',
            'correspondence_pattern',
            'both_and_pattern',
            'takes_value_pattern',
            'upon_action_pattern',
            'same_identifier_pattern'
        ]
        
        if self.debug:
            print(f"Loaded {len(self.acronym_mappings)} acronym mappings")
            print(f"Loaded {len(self.constraint_keywords)} constraint keywords")
            print(f"Loaded {len(self.special_constraint_patterns)} special patterns")
    
    # Cache Optimization Methods
    
    @lru_cache(maxsize=1000)
    def split_camel_case(self, name: str) -> str:
        """Camel Case Splitting (Cached)"""
        name = name.replace('-', ' ').replace('_', ' ')
        result = re.sub(r'(?<!^)(?=[A-Z])', ' ', name)
        result = re.sub(r'\s+', ' ', result)
        return result.lower().strip()
    
    @lru_cache(maxsize=1000)
    def normalize_field_name(self, field_name: str) -> str:
        """Standardized field names (cache)"""
        normalized = field_name.lower()
        normalized = re.sub(r'[-_]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
    
    def get_compiled_pattern(self, pattern: str) -> re.Pattern:
        """Get compiled regex (cached)"""
        if pattern not in self._compiled_pattern_cache:
            self._compiled_pattern_cache[pattern] = re.compile(pattern, re.IGNORECASE)
        return self._compiled_pattern_cache[pattern]
    
    # ==================== Field Processing ====================
    
    def load_field_names_from_list(self, field_list: List[Dict]) -> Tuple[List[str], Dict[str, List[int]]]:
        """Load field names from field list"""
        field_names = set()
        field_id_mapping = {}
        
        for item in field_list:
            if not isinstance(item, dict):
                continue
            
            field_name = item.get('field_name', '')
            field_id = item.get('field_id')
            
            if field_name:
                # Remove array index
                clean_name = re.sub(r'\[\d+\]', '', field_name)
                field_names.add(clean_name)
                
                if field_id is not None:
                    if clean_name not in field_id_mapping:
                        field_id_mapping[clean_name] = []
                    if field_id not in field_id_mapping[clean_name]:
                        field_id_mapping[clean_name].append(field_id)
        
        return sorted(list(field_names)), field_id_mapping
    
    # ==================== Smart Field Pair Filtering ====================
    
    @staticmethod
    def is_reference_field(field_name: str) -> bool:
        """Determine if it is a reference field (ending with Id/ID)"""
        clean_name = re.sub(r'\[\d+\]', '', field_name)
        return clean_name.endswith('Id') or clean_name.endswith('ID')
    
    @staticmethod
    def clean_field_name_for_comparison(field_name: str) -> str:
        """Clean field names for comparison"""
        name = re.sub(r'\[\d+\]', '', field_name)
        name = name.lower().replace('-', '').replace('_', '')
        return name
    
    def calculate_field_name_similarity(self, field1: str, field2: str) -> float:
        """
        Calculate field name similarity (0.0-1.0)
        
        Method:
        1. Edit Distance
        2. Common Substring
        3. Vocabulary Overlap
        """
        clean1 = self.clean_field_name_for_comparison(field1)
        clean2 = self.clean_field_name_for_comparison(field2)
        
        # Completely identical
        if clean1 == clean2:
            return 1.0
        
        # One contains another
        if clean1 in clean2 or clean2 in clean1:
            shorter = min(len(clean1), len(clean2))
            longer = max(len(clean1), len(clean2))
            return shorter / longer
        
        # Calculate vocabulary-level overlap
        words1 = set(re.split(r'[-_\s]', field1.lower()))
        words2 = set(re.split(r'[-_\s]', field2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        common_words = words1 & words2
        total_words = words1 | words2
        
        if total_words:
            return len(common_words) / len(total_words)
        
        return 0.0
    
    def should_generate_inter_ie_pair(self, field1_name: str, field2_name: str) -> bool:
        """
        Determine whether this cross-IE field pair should be generated
        
        Rules (priority from high to low):
        1. Reference fields (ending with Id/ID) → Must be generated
        2. Fields with the same name (different IE) → Must be generated
        3. Field name similarity > 0.3 → Generate
        4. Other → Skip
        """
        # Rule 1: Reference Fields
        if self.is_reference_field(field1_name) or self.is_reference_field(field2_name):
            return True
        
        # Rule 2: Fields with the same name
        clean1 = self.clean_field_name_for_comparison(field1_name)
        clean2 = self.clean_field_name_for_comparison(field2_name)
        if clean1 == clean2:
            return True
        
        # Rule 3: Name Similarity
        similarity = self.calculate_field_name_similarity(field1_name, field2_name)
        if similarity > 0.3:
            return True
        
        return False
    
    def generate_cross_ie_field_pairs(self, fields1: List[str], fields2: List[str], 
                                     field_id_mapping1: Dict[str, List[int]],
                                     field_id_mapping2: Dict[str, List[int]],
                                     strategy: str = 'smart') -> List[Tuple[Tuple[str, str], Tuple[List[int], List[int]]]]:
        """
        Generate cross-IE field pairs
        
        strategy:
        - 'all': All combinations
        - 'smart': Smart filtering (recommended)
        - 'reference-only': Generate only reference field pairs
        """
        pairs = []
        
        if strategy == 'all':
            # All Cartesian products
            for field1 in fields1:
                for field2 in fields2:
                    pairs.append((
                        (field1, field2),
                        (field_id_mapping1.get(field1, []), field_id_mapping2.get(field2, []))
                    ))
        
        elif strategy == 'reference-only':
            # Generate only reference field pairs
            for field1 in fields1:
                if not self.is_reference_field(field1):
                    continue
                for field2 in fields2:
                    if not self.is_reference_field(field2):
                        continue
                    pairs.append((
                        (field1, field2),
                        (field_id_mapping1.get(field1, []), field_id_mapping2.get(field2, []))
                    ))
        
        else:  # 'smart' (default)
            # Smart Filter
            for field1 in fields1:
                for field2 in fields2:
                    if self.should_generate_inter_ie_pair(field1, field2):
                        pairs.append((
                            (field1, field2),
                            (field_id_mapping1.get(field1, []), field_id_mapping2.get(field2, []))
                        ))
        
        return pairs
    
    # IE Information Extraction
    
    def extract_ie_info_from_filename(self, ie_filename: str) -> Dict:
        """Extract information from IE filename"""
        # Format: 10_18_rlc-Config.json
        match = re.search(r'(\d+)_(\d+)_(.+)\.json$', ie_filename)
        if not match:
            return {'ie_name': '', 'ie_short_name': '', 'ie_prefix': ''}
        
        full_name = match.group(3)
        if '-' in full_name:
            parts = full_name.split('-', 1)
            prefix = parts[0]
            short_name = parts[1]
        else:
            prefix = ''
            short_name = full_name
        
        return {
            'ie_name': full_name,
            'ie_short_name': short_name,
            'ie_prefix': prefix
        }
    
    def generate_ie_variants(self, ie_info: Dict) -> List[str]:
        """Generate IE Name Variants"""
        variants = set()
        
        ie_name = ie_info.get('ie_short_name', '')
        ie_prefix = ie_info.get('ie_prefix', '')
        
        if not ie_name:
            return []
        
        # 1. Original Name
        variants.add(ie_name)
        variants.add(ie_name.lower())
        
        # 2. Camel Case Splitting
        camel_spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', ie_name)
        variants.add(camel_spaced)
        variants.add(camel_spaced.lower())
        
        # 3. Config Variants
        if 'Config' in ie_name:
            variants.add(ie_name.replace('Config', 'Configuration'))
            variants.add(camel_spaced.replace('Config', 'Configuration'))
            variants.add(camel_spaced.replace('Config', 'Configuration').lower())
        
        # 4. Prefix Variants
        if ie_prefix:
            variants.add(f"{ie_prefix}-{ie_name}")
            variants.add(f"{ie_prefix.upper()} {camel_spaced}")
            variants.add(f"{ie_prefix} {camel_spaced.lower()}")
            variants.add(f"{ie_prefix.upper()}-{ie_name}")
        
        # 5. Protocol Abbreviations
        ie_normalized = ie_name.lower().replace('-', '').replace('_', '')
        for full_term, acronyms in self.acronym_mappings.items():
            if full_term in ie_normalized:
                variants.update(acronyms)
                for acronym in acronyms:
                    variants.add(acronym.upper())
        
        variants.discard('')
        return sorted(list(variants), key=len, reverse=True)
    
    # ==================== Chapter Relevance Scoring (Retained as Bonus Points) ====================
    
    def build_section_index(self, lines: List[str], ie1_variants: List[str], ie2_variants: List[str]) -> Dict:
        """
        Build Chapter Index (Dual IE Version)
        
        Calculate for each chapter:
        - ie1_score: IE1 relevance score
        - ie2_score: IE2 relevance score
        - combined_score: Combined Score
        - match_type: BOTH/SINGLE/NONE
        
        Note: For Inter-IE, section relevance is typically 0 (constraints appear in process sections).
        """
        sections = []
        current_section = None
        
        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            section_match = re.match(r'^(\d+\.[\d.]+)\s+(.+?)(?:\s*[-⋯.]+.*)?$', line_stripped)
            
            if section_match:
                if current_section:
                    current_section['end_line'] = line_idx - 1
                    sections.append(current_section)
                
                section_number = section_match.group(1)
                section_title = section_match.group(2).strip()
                section_title = re.sub(r'^[-\s]+', '', section_title)
                section_title = re.sub(r'\s*[-⋯.]+\s*$', '', section_title)
                section_title = section_title.strip()
                
                if len(section_title) < 3:
                    continue
                
                # Calculate dual IE correlation
                relevance_info = self.calculate_inter_ie_section_relevance(
                    section_title, ie1_variants, ie2_variants
                )
                
                current_section = {
                    'start_line': line_idx,
                    'end_line': len(lines) - 1,
                    'number': section_number,
                    'title': section_title,
                    **relevance_info
                }
        
        if current_section:
            sections.append(current_section)
        
        if not sections:
            sections.append({
                'start_line': 0,
                'end_line': len(lines) - 1,
                'number': 'N/A',
                'title': 'Entire Document',
                'ie1_score': 0.0,
                'ie2_score': 0.0,
                'combined_score': 0.0,
                'match_type': 'NONE',
                'matched_variants': {'ie1': [], 'ie2': []}
            })
        
        # Establish mapping from line numbers to chapters
        line_to_section = {}
        for idx, section in enumerate(sections):
            for line_num in range(section['start_line'], section['end_line'] + 1):
                line_to_section[line_num] = idx
        
        return {
            'sections': sections,
            'line_to_section': line_to_section
        }
    
    def calculate_section_relevance(self, section_title: str, ie_variants: List[str]) -> Tuple[float, List[str]]:
        """
        Calculate the relevance between individual IE and chapters
        
        Returns: (score, list of matched variants)
        """
        score = 0.0
        matched_variants = []
        title_lower = section_title.lower()
        
        for variant in ie_variants:
            variant_lower = variant.lower()
            
            # Exact match
            if variant_lower == title_lower:
                score += 50.0
                matched_variants.append(variant)
            # Contains match
            elif variant_lower in title_lower or title_lower in variant_lower:
                if len(variant_lower) > 10:
                    score += 30.0
                elif len(variant_lower) > 5:
                    score += 20.0
                else:
                    score += 10.0
                matched_variants.append(variant)
            # Vocabulary matching
            else:
                variant_words = set(variant_lower.split())
                title_words = set(title_lower.split())
                common_words = variant_words & title_words - {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'for', 'to'}
                
                if len(common_words) >= 2:
                    score += 5.0 * len(common_words)
                    matched_variants.append(variant)
        
        return score, list(set(matched_variants))
    
    def calculate_inter_ie_section_relevance(self, section_title: str, 
                                            ie1_variants: List[str], 
                                            ie2_variants: List[str]) -> Dict:
        """
        Calculate Dual IE Chapter Correlation
        
        Strategy:
        1. Calculate the correlation of ie1 and ie2 respectively
        2. Combine scores based on matching results
        3. Bonus granted when dual IE matching occurs
        
        Return:
        {
            'ie1_score': float,
            'ie2_score': float,
            'combined_score': float,
            'match_type': 'BOTH'|'SINGLE'|'NONE',
            'matched_variants': {'ie1': [...], 'ie2': [...]}
        }
        """
        ie1_score, ie1_matched = self.calculate_section_relevance(section_title, ie1_variants)
        ie2_score, ie2_matched = self.calculate_section_relevance(section_title, ie2_variants)
        
        # Determine match type and combination score
        if ie1_score > 0 and ie2_score > 0:
            # Dual IE matching: weighted sum (additive)
            combined_score = (ie1_score + ie2_score) * BOTH_IE_MATCH_BONUS
            match_type = 'BOTH'
        elif ie1_score > 0 or ie2_score > 0:
            # Single IE matching: take the maximum value
            combined_score = max(ie1_score, ie2_score)
            match_type = 'SINGLE'
        else:
            # No match
            combined_score = 0.0
            match_type = 'NONE'
        
        return {
            'ie1_score': ie1_score,
            'ie2_score': ie2_score,
            'combined_score': combined_score,
            'match_type': match_type,
            'matched_variants': {
                'ie1': ie1_matched,
                'ie2': ie2_matched
            }
        }
    
    # ==================== Multi-Signal Confidence Calculation (Core Improvement) ====================
    
    @staticmethod
    def calculate_inter_ie_confidence(constraint: Dict) -> str:
        """
        Improved Inter-IE Confidence Calculation (Multi-Signal)
        
        Does not rely on section_relevance (typically 0 in Inter-IE)
        Use three signals:
        Constraint keyword intensity (0-40 points)
        2. Field Matching Quality (0-30 points)
        3. Chapter Relevance (0-30 points, bonus points)
        
        Total score >= 60: HIGH
        Total score >= 40: MEDIUM
        Total score ≥20: LOW
        Total score <20: VERY_LOW
        """
        score = 0.0
        
        # Signal 1: Constraint Keyword Strength (Core Signal, 0-40 points)
        keyword = constraint.get('constraint_keyword', '')
        if keyword:
            keyword_lower = keyword.lower()
            
            # Strong Constraint Keywords (40 points)
            strong_keywords = ['shall', 'must', 'required', 'mandatory', 'necessary']
            if any(kw in keyword_lower for kw in strong_keywords):
                score += 40
            
            # Medium constraint keywords (30 points)
            elif any(kw in keyword_lower for kw in ['if', 'when', 'depends', 'according', 'based on']):
                score += 30
            
            # Soft constraint keywords (20 points)
            elif keyword and not keyword.startswith('['):  # Non-special mode
                score += 20
            
            # Special Mode (25 points)
            elif keyword.startswith('['):
                score += 25
        
        # Signal 2: Field Matching Quality (0-30 points)
        matched_fields = constraint.get('matched_fields', [])
        if len(matched_fields) >= 2:
            # Both fields match exactly
            score += 30
        elif len(matched_fields) == 1:
            # Only one field matches exactly
            score += 15
        
        # Signal 3: Chapter Relevance (Bonus points, maximum 30 points)
        section_relevance = constraint.get('section_relevance', {})
        section_score = section_relevance.get('combined_score', 0.0)
        score += min(section_score, 30)
        
        # Classification
        if score >= 60:
            return 'HIGH'
        elif score >= 40:
            return 'MEDIUM'
        elif score >= 20:
            return 'LOW'
        else:
            return 'VERY_LOW'
    
    # Field Matching Pattern
    
    def create_field_pattern(self, field_name: str) -> str:
        """Create field matching pattern (cache)"""
        if field_name in self._pattern_cache:
            return self._pattern_cache[field_name]
        
        patterns = []
        
        # 1. Standardized matching
        normalized = self.normalize_field_name(field_name)
        words = normalized.split()
        pattern_parts = [re.escape(word) for word in words]
        pattern1 = r'[\s\-_]*'.join(pattern_parts)
        patterns.append(r'\b' + pattern1 + r'\b')
        
        # 2. Camel Case Splitting
        if re.search(r'[a-z][A-Z]', field_name):
            camel_split = self.split_camel_case(field_name)
            words = camel_split.split()
            pattern2 = r'[\s\-_]*'.join([re.escape(word) for word in words])
            patterns.append(r'\b' + pattern2 + r'\b')
        
        # 3. Original Form
        escaped = re.escape(field_name)
        pattern3 = escaped.replace(r'\-', r'[-_]').replace(r'\_', r'[-_]')
        patterns.append(r'\b' + pattern3 + r'\b')
        
        # 4. Protocol Abbreviations
        field_normalized = field_name.lower().replace('-', '').replace('_', '')
        for full_term, acronyms in self.acronym_mappings.items():
            if full_term in field_normalized:
                for acronym in acronyms:
                    patterns.append(r'\b' + re.escape(acronym) + r'\b')
                    patterns.append(r'\b' + re.escape(acronym.upper()) + r'\b')
        
        unique_patterns = list(set(patterns))
        result = '|'.join([f'({p})' for p in unique_patterns])
        
        self._pattern_cache[field_name] = result
        return result
    
    def precompute_field_patterns(self, field_names: List[str]) -> Dict[str, Dict]:
        """Pre-calculate match patterns for all fields"""
        field_patterns = {}
        
        for field in field_names:
            patterns = {
                'standard': self.create_field_pattern(field)
            }
            field_patterns[field] = patterns
        
        return field_patterns
    
    # ==================== Constraint Detection ====================
    
    def contains_constraint_keyword_fast(self, sentence: str) -> Tuple[bool, str]:
        """Quick Check Constraint Keywords (Enhanced Version)"""
        # First use keyword matching
        match = self.constraint_pattern.search(sentence)
        if match:
            if self.debug:
                print(f"    → Matched keyword: '{match.group(1)}'")
            return True, match.group(1)
        
        # Try special mode again
        for idx, pattern in enumerate(self.special_constraint_patterns):
            match = pattern.search(sentence)
            if match:
                if self.debug:
                    print(f"    → Matched special pattern: {self.special_pattern_names[idx]}")
                return True, f"[{self.special_pattern_names[idx]}]"
        
        if self.debug:
            print(f"    ✗ No constraint pattern found")
        
        return False, ""
    
    # ==================== Batch Field Search ====================
    
    def batch_find_field_occurrences(self, lines: List[str], field_patterns: Dict[str, Dict]) -> Dict[str, List[Tuple[int, str]]]:
        """Batch find all field occurrence positions"""
        field_occurrences = {field: [] for field in field_patterns}
        
        for line_idx, line in enumerate(lines):
            if len(line) < 20:
                continue
            
            for field_name, patterns in field_patterns.items():
                pattern = patterns.get('standard', '')
                if pattern:
                    compiled_pattern = self.get_compiled_pattern(pattern)
                    matches = compiled_pattern.finditer(line)
                    for match in matches:
                        field_occurrences[field_name].append((line_idx, match.group(0)))
        
        return field_occurrences
    
    # ==================== Core Constraint Extraction ====================
    
    def extract_constraints_from_file_optimized(self, file_path: str,
                                               field_pairs_with_sources: List[Tuple[Tuple[str, str], Tuple[str, str], Tuple[List[int], List[int]]]],
                                               field_patterns: Dict[str, Dict],
                                               ie1_variants: List[str],
                                               ie2_variants: List[str]) -> List[Dict]:
        """
        Optimized Constraint Extraction (Inter-IE Version)
        
        Parameters:
        - field_pairs_with_sources: [((field1, field2), (ie1, ie2), (ids1, ids2)), ...]
        """
        constraints = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            if self.debug:
                print(f"Error reading {file_path}: {e}")
            return constraints
        
        # Build Dual IE Chapter Index
        section_index = self.build_section_index(lines, ie1_variants, ie2_variants)
        
        # Batch find field occurrences
        field_occurrences = self.batch_find_field_occurrences(lines, field_patterns)
        
        # Expand search window (Inter-IE may require larger range)
        max_line_distance = 2
        
        # Process field pairs
        for (field1, field2), (ie1, ie2), (field1_ids, field2_ids) in field_pairs_with_sources:
            if not field_occurrences[field1] or not field_occurrences[field2]:
                continue
            
            # Find cases where two fields appear in nearby rows
            for line1_idx, match1_text in field_occurrences[field1]:
                for line2_idx, match2_text in field_occurrences[field2]:
                    if abs(line1_idx - line2_idx) <= max_line_distance:
                        # Construct text
                        min_idx = min(line1_idx, line2_idx)
                        max_idx = max(line1_idx, line2_idx)
                        
                        text_lines = []
                        for idx in range(min_idx, max_idx + 1):
                            if idx < len(lines):
                                text_lines.append(lines[idx].strip())
                        text = ' '.join(text_lines)
                        
                        # Check constraint keywords
                        has_constraint, keyword = self.contains_constraint_keyword_fast(text)
                        if has_constraint:
                            # Get chapter information
                            section_info = self.get_section_info_for_line(line1_idx, section_index)
                            
                            # Apply threshold filtering (chapter relevance)
                            combined_score = section_info['section_relevance']['combined_score']
                            if combined_score >= LOW_RELEVANCE_THRESHOLD or combined_score == 0.0:
                                
                                # Build constraints (excluding confidence)
                                constraint = {
                                    "fields": [field1, field2],
                                    "source_IEs": [ie1, ie2],
                                    "field_ids": [field1_ids, field2_ids],
                                    "matched_fields": [match1_text, match2_text],
                                    "original_sentence": text,
                                    "source_file": os.path.basename(file_path),
                                    "constraint_keyword": keyword,
                                    "is_cross_ie": True,
                                    **section_info
                                }
                                
                                # Calculate confidence (using multiple signals)
                                constraint['confidence'] = self.calculate_inter_ie_confidence(constraint)
                                
                                constraints.append(constraint)
                                break  # Find constraint, jump to next field pair
        
        return constraints
    
    def get_section_info_for_line(self, line_idx: int, section_index: Dict) -> Dict:
        """Get row chapter information (Inter-IE version)"""
        if line_idx in section_index['line_to_section']:
            section_idx = section_index['line_to_section'][line_idx]
            section = section_index['sections'][section_idx]
            
            return {
                'section_number': section['number'],
                'section_title': section['title'],
                'section_relevance': {
                    'combined_score': section['combined_score'],
                    'ie1_score': section['ie1_score'],
                    'ie2_score': section['ie2_score'],
                    'match_type': section['match_type'],
                    'matched_variants': section['matched_variants']
                }
                # Note: Confidence is not calculated here, but will be calculated uniformly after constraint construction.
            }
        else:
            return {
                'section_number': 'N/A',
                'section_title': 'Unknown',
                'section_relevance': {
                    'combined_score': 0.0,
                    'ie1_score': 0.0,
                    'ie2_score': 0.0,
                    'match_type': 'NONE',
                    'matched_variants': {'ie1': [], 'ie2': []}
                }
            }
    
    # ==================== IE Compatibility ====================
    
    def extract_constraints_for_ie_pair(self, ie1: str, ie2: str, ie_dir: str, spec_dir: str) -> List[Dict]:
        """Extract all constraints for specific IE pairs"""
        if self.debug:
            print(f"\nProcessing IE pair: {ie1} <-> {ie2}")
        
        # Load Fields
        ie1_path = os.path.join(ie_dir, f"{ie1}.json")
        ie2_path = os.path.join(ie_dir, f"{ie2}.json")
        
        with open(ie1_path, 'r') as f:
            field_list1 = json.load(f)
        with open(ie2_path, 'r') as f:
            field_list2 = json.load(f)
        
        fields1, field_id_mapping1 = self.load_field_names_from_list(field_list1)
        fields2, field_id_mapping2 = self.load_field_names_from_list(field_list2)
        
        if self.debug:
            print(f"  {ie1}: {len(fields1)} fields")
            print(f"  {ie2}: {len(fields2)} fields")
        
        # Generate field pairs
        field_pairs_raw = self.generate_cross_ie_field_pairs(
            fields1, fields2, field_id_mapping1, field_id_mapping2, 
            strategy=FIELD_PAIR_STRATEGY
        )
        
        # Add IE information
        field_pairs_with_sources = [
            (pair[0], (ie1, ie2), pair[1]) 
            for pair in field_pairs_raw
        ]
        
        if self.debug:
            print(f"  Generated {len(field_pairs_with_sources)} field pairs (strategy: {FIELD_PAIR_STRATEGY})")
        
        # Generate IE variants
        ie1_info = self.extract_ie_info_from_filename(f"{ie1}.json")
        ie2_info = self.extract_ie_info_from_filename(f"{ie2}.json")
        
        ie1_variants = self.generate_ie_variants(ie1_info)
        ie2_variants = self.generate_ie_variants(ie2_info)
        
        if self.debug:
            print(f"  IE1 variants: {len(ie1_variants)}")
            print(f"  IE2 variants: {len(ie2_variants)}")
        
        # Precomputed Field Mode
        all_fields = list(set(fields1 + fields2))
        field_patterns = self.precompute_field_patterns(all_fields)
        
        # Get all specification documents
        spec_files = glob.glob(os.path.join(spec_dir, "*.txt"))
        spec_files.extend(glob.glob(os.path.join(spec_dir, "*.md")))
        
        all_constraints = []
        
        # Multi-process handling specification document
        if ENABLE_SPEC_PARALLEL and len(spec_files) > 1:
            process_func = partial(
                process_spec_file_for_inter_ie,
                field_pairs_with_sources=field_pairs_with_sources,
                field_patterns=field_patterns,
                ie1_variants=ie1_variants,
                ie2_variants=ie2_variants,
                debug=False
            )
            
            with ProcessPoolExecutor(max_workers=min(MAX_SPEC_WORKERS, len(spec_files))) as executor:
                for constraints in executor.map(process_func, spec_files):
                    all_constraints.extend(constraints)
        else:
            # Serial processing
            for spec_file in spec_files:
                constraints = self.extract_constraints_from_file_optimized(
                    spec_file, field_pairs_with_sources, field_patterns,
                    ie1_variants, ie2_variants
                )
                all_constraints.extend(constraints)
        
        # Deduplication
        unique_constraints = []
        seen_sentences = set()
        
        for constraint in all_constraints:
            sentence = constraint['original_sentence']
            fields_key = tuple(sorted(constraint['fields']))
            unique_key = (fields_key, sentence[:200])
            
            if unique_key not in seen_sentences:
                seen_sentences.add(unique_key)
                unique_constraints.append(constraint)
        
        if self.debug:
            print(f"  Found {len(unique_constraints)} unique constraints")
        
        return unique_constraints

# ============================================================================
# Cluster management and IE generation
# ============================================================================

def load_cluster_config(config_path: str) -> Dict:
    """Load cluster configuration"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_ie_pairs(cluster_config: Dict, ie_dir: str) -> List[Tuple[str, str]]:
    """Generate IE pairs based on cluster configuration"""
    ie_pairs = set()
    clusters = cluster_config['clusters']
    
    # Get available IE files
    available_ies = set()
    for ie_file in glob.glob(os.path.join(ie_dir, "*.json")):
        ie_name = os.path.splitext(os.path.basename(ie_file))[0]
        available_ies.add(ie_name)
    
    # Processing allowed cluster pairs
    for cluster_pair in cluster_config['allowed_cluster_pairs']:
        cluster1, cluster2 = cluster_pair
        ies1 = clusters.get(cluster1, [])
        ies2 = clusters.get(cluster2, [])
        
        for ie1 in ies1:
            for ie2 in ies2:
                if ie1 in available_ies and ie2 in available_ies:
                    pair = tuple(sorted([ie1, ie2]))
                    ie_pairs.add(pair)
    
    # Handle pairs within the cluster
    for cluster in cluster_config['allow_intra_cluster_pairs']:
        ies = clusters.get(cluster, [])
        for ie1, ie2 in combinations(ies, 2):
            if ie1 in available_ies and ie2 in available_ies:
                pair = tuple(sorted([ie1, ie2]))
                ie_pairs.add(pair)
    
    return sorted(list(ie_pairs))

# ============================================================================
# Main processing function
# ============================================================================

def process_ie_pair_wrapper(args):
    """IE for handling wrapper functions (for multiprocessing)"""
    ie1, ie2, ie_dir, spec_dir, output_dir = args
    
    extractor = InterIEEnhancedConstraintExtractor(debug=DEBUG_MODE)
    
    output_path = os.path.join(output_dir, f"{ie1}_{ie2}_constraints_enhanced.json")
    
    try:
        constraints = extractor.extract_constraints_for_ie_pair(ie1, ie2, ie_dir, spec_dir)
        
        # Save results
        clean_constraints = []
        for c in constraints:
            clean_constraint = {
                "fields": c["fields"],
                "source_IEs": c["source_IEs"],
                "field_ids": c["field_ids"],
                "matched_fields": c["matched_fields"],
                "original_sentence": c["original_sentence"],
                "source_file": c["source_file"],
                "section_number": c["section_number"],
                "section_title": c["section_title"],
                "section_relevance": c["section_relevance"],
                "confidence": c["confidence"],
                "is_cross_ie": c["is_cross_ie"]
            }
            clean_constraints.append(clean_constraint)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clean_constraints, f, ensure_ascii=False, indent=2)
        
        return (ie1, ie2), True, len(constraints)
        
    except Exception as e:
        print(f"Error processing {ie1} <-> {ie2}: {e}")
        import traceback
        traceback.print_exc()
        return (ie1, ie2), False, 0

def main():
    print("=" * 80)
    print("Inter-IE Enhanced Constraint Extractor (v2)")
    print("Cross-IE Enhanced Constraint Extractor - Multi-Signal Confidence")
    print("=" * 80)
    
    # Validate input
    if not os.path.exists(IE_DIR):
        print(f"\n❌ IE directory does not exist: {IE_DIR}")
        return
    
    if not os.path.exists(SPEC_DIR):
        print(f"\n❌ Specification directory does not exist: {SPEC_DIR}")
        return
    
    if not os.path.exists(CLUSTER_CONFIG_PATH):
        print(f"❌ Cluster configuration does not exist: {CLUSTER_CONFIG_PATH}")
        return
    
    # Create output directory
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Create output directory: {OUTPUT_DIR}")
    
    # Load cluster configuration
    print("Loading cluster configuration...")
    cluster_config = load_cluster_config(CLUSTER_CONFIG_PATH)
    
    # Generate IE pairs
    print("Generate IE pair...")
    ie_pairs = generate_ie_pairs(cluster_config, IE_DIR)
    print(f"Generated {len(ie_pairs)} IE pairs")
    
    # Display Configuration
    print("\n" + "=" * 80)
    print("Run Configuration")
    print("=" * 80)
    print(f"Field pair strategy: {FIELD_PAIR_STRATEGY}")
    print(f"Confidence calculation: Multi-signal (keywords + field matching + section relevance)")
    print(f"Dual IE Bonus Coefficient: {BOTH_IE_MATCH_BONUS}")
    print(f"Relevance threshold: {LOW_RELEVANCE_THRESHOLD}")
    print(f"IE pair parallelism: {'Enable' if ENABLE_IE_PARALLEL else 'Disabled'} (workers={MAX_IE_WORKERS})")
    print(f"Specification file parallelism: {'Enable' if ENABLE_SPEC_PARALLEL else 'Disabled'} (workers={MAX_SPEC_WORKERS})")
    print(f"Debug mode: {'Enable' if DEBUG_MODE else 'Disable'}")
    print("=" * 80)
    
    # Start processing
    start_time = time.time()
    
    successful_pairs = 0
    failed_pairs = []
    total_constraints = 0
    
    if ENABLE_IE_PARALLEL:
        # Parallel processing IE pairs
        print(f"\nProcessing {len(ie_pairs)} IE pairs in parallel (workers={MAX_IE_WORKERS})...")
        
        process_args = [
            (ie1, ie2, IE_DIR, SPEC_DIR, OUTPUT_DIR)
            for ie1, ie2 in ie_pairs
        ]
        
        with ThreadPoolExecutor(max_workers=min(MAX_IE_WORKERS, len(ie_pairs))) as executor:
            futures = {
                executor.submit(process_ie_pair_wrapper, args): args[:2]
                for args in process_args
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                ie_pair = futures[future]
                try:
                    (ie1, ie2), success, constraint_count = future.result()
                    
                    if success:
                        successful_pairs += 1
                        total_constraints += constraint_count
                        print(f"\r[{completed}/{len(ie_pairs)}] ✓ {ie1} <-> {ie2}: {constraint_count} constraints",
                              end='', flush=True)
                    else:
                        failed_pairs.append((ie1, ie2))
                        print(f"\r[{completed}/{len(ie_pairs)}] ✗ {ie1} <-> {ie2}",
                              end='', flush=True)
                
                except Exception as exc:
                    print(f'\n{ie_pair[0]} <-> {ie_pair[1]} exception occurred: {exc}')
                    failed_pairs.append(ie_pair)
        
        print()  # Line break
    
    else:
        # Serial processing IE pairs
        print(f"\nSerially processing {len(ie_pairs)} IE pairs...")
        
        for idx, (ie1, ie2) in enumerate(ie_pairs, 1):
            print(f"\n[{idx}/{len(ie_pairs)}] Processing: {ie1} <-> {ie2}")
            
            (ie1, ie2), success, constraint_count = process_ie_pair_wrapper(
                (ie1, ie2, IE_DIR, SPEC_DIR, OUTPUT_DIR)
            )
            
            if success:
                successful_pairs += 1
                total_constraints += constraint_count
                print(f"  ✓ {constraint_count} constraints")
            else:
                failed_pairs.append((ie1, ie2))
                print(f"  ✗ Failed")
    
    # Save Summary
    elapsed_time = time.time() - start_time
    
    summary = {
        'extraction_type': 'inter_ie_enhanced_v2',
        'version': 'multi-signal_confidence',
        'configuration': {
            'field_pair_strategy': FIELD_PAIR_STRATEGY,
            'confidence_method': 'multi_signal',
            'both_ie_match_bonus': BOTH_IE_MATCH_BONUS,
            'low_relevance_threshold': LOW_RELEVANCE_THRESHOLD,
            'ie_parallel': ENABLE_IE_PARALLEL,
            'spec_parallel': ENABLE_SPEC_PARALLEL
        },
        'statistics': {
            'total_ie_pairs': len(ie_pairs),
            'successful_pairs': successful_pairs,
            'failed_pairs': len(failed_pairs),
            'total_constraints': total_constraints,
            'avg_constraints_per_pair': total_constraints / len(ie_pairs) if ie_pairs else 0,
            'processing_time_seconds': elapsed_time,
            'avg_time_per_pair': elapsed_time / len(ie_pairs) if ie_pairs else 0
        },
        'failed_pairs_list': [f"{ie1}_{ie2}" for ie1, ie2 in failed_pairs]
    }
    
    summary_path = os.path.join(OUTPUT_DIR, "extraction_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # Print Summary
    print("\n" + "=" * 80)
    print("Processing completed")
    print("=" * 80)
    print(f"Successfully processed: {successful_pairs}/{len(ie_pairs)} IE pairs")
    
    if failed_pairs:
        print(f"Failed IE pairs:")
        for ie1, ie2 in failed_pairs:
            print(f"  {ie1} <-> {ie2}")
    
    print(f"Total constraints: {total_constraints}")
    print(f"Average constraints per IE pair: {total_constraints/len(ie_pairs):.1f}")
    print(f"Total processing time: {elapsed_time:.2f} seconds")
    print(f"Average time per IE pair: {elapsed_time/len(ie_pairs):.2f} seconds")
    print(f"Summary file: {summary_path}")

if __name__ == "__main__":
    main()