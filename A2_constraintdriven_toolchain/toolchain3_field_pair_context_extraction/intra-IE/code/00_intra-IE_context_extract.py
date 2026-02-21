#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import argparse
from pathlib import Path
from itertools import combinations
from typing import List, Dict, Tuple, Set
from multiprocessing import Pool, cpu_count
from functools import lru_cache
import time

# ============================================================================
# Path Configuration
# ============================================================================

DEFAULT_IE_DIR = "../../../toolchain2_IE_collection/intra-IE/outputs/intra-IE_strategy/selected_ies"
DEFAULT_SPEC_DIR = "../../../toolchain1_3GPP_preprocessing/outputs/txt_specifications_mathpix/txt_specifications_mathpix_md"
DEFAULT_OUTPUT_DIR = "../outputs/context_with_sections_all_pairs"
DEFAULT_WORKERS = 8

GENERATE_ALL_PAIRS = True

# ============================================================================
# Global functions for multiprocessing
# ============================================================================

def process_file_for_multiprocessing(args):
    """File processing function for multiprocessing"""
    spec_file, field_pairs, field_patterns, strict_mode, include_self_constraints, ie_variants = args
    extractor = EnhancedConstraintExtractor(debug=False, strict_mode=strict_mode)
    return extractor.extract_constraints_from_file_optimized(
        spec_file, field_pairs, field_patterns, ie_variants, include_self_constraints
    )

# ============================================================================
# Core Extractor Class
# ============================================================================

class EnhancedConstraintExtractor:
    def __init__(self, debug=False, strict_mode=True):
        self.debug = debug
        self.strict_mode = strict_mode
        
        self._pattern_cache = {}
        self._compiled_pattern_cache = {}
        
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
            'logicalchannel': ['logical channel'],
            'cellgroupconfig': ['cell group configuration', 'cell group'],
        }
        
        self.field_prefix_mappings = {
            'bsr': ['BSR', 'Buffer Status', 'Buffer Status Reporting'],
            'phr': ['PHR', 'Power Headroom', 'Power Headroom Reporting'],
            'sr': ['SR', 'Scheduling Request'],
            'drx': ['DRX', 'Discontinuous Reception'],
            'tag': ['TAG', 'Timing Advance'],
            'harq': ['HARQ'],
            'sps': ['SPS', 'Semi-Persistent Scheduling'],
            'csi': ['CSI'],
            'pdsch': ['PDSCH'],
            'pdcch': ['PDCCH'],
            'coreset': ['CORESET'],
            'bwp': ['BWP'],
        }
        
        self.constraint_keywords = [
            'shall', 'shall not', 'shall be', 'shall have',
            'must', 'must not', 'must be', 'must have',
            'mandatory', 'required', 'required to', 'required that',
            'need to', 'needs to', 'needed',
            'if', 'when', 'whenever', 'where', 'given that',
            'provided that', 'assuming', 'in case',
            'only if', 'if and only if', 'iff',
            'unless', 'except when', 'except if',
            'valid only if', 'valid only when', 'valid if',
            'applicable only if', 'applicable when',
            'depends on', 'dependent on', 'depending on',
            'determined by', 'defined by', 'specified by',
            'given by', 'indicated by', 'contained in',
            'obtained from', 'corresponds to',
            'according to', 'based on', 'derived from',
            'set to', 'configured with',
            'prohibited', 'not allowed', 'not permitted',
            'forbidden', 'disallowed', 'invalid if',
            'cannot', 'may not', 'should not',
            'limited to', 'restricted to', 'constrained by',
            'subject to', 'conditional on',
            'necessary', 'necessarily', 'essential',
            'prerequisite', 'precondition',
            'require', 'requires', 'requiring',
            'ensure', 'ensures', 'ensuring',
            'guarantee', 'guarantees',
            'enforce', 'enforces', 'enforcing',
            'comply', 'complies', 'compliance',
            'conform', 'conforms', 'conformance'
        ]
        
        self.constraint_keywords = sorted(list(set(self.constraint_keywords)))
        
        self.constraint_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(kw) for kw in self.constraint_keywords) + r')\b',
            re.IGNORECASE
        )
        
        self.self_reference_patterns = [
            r'is\s+set\s+to',
            r'is\s+configured\s+with',
            r'has\s+value',
            r'equals\s+to',
            r'different\s+values?\s+of',
            r'when.*is',
            r'if.*is\s+not\s+present',
            r'possible\s+values?',
            r'valid\s+values?',
            r'shall\s+report',
            r'shall\s+be\s+set',
            r'can\s+only\s+be\s+present',
            r'to\s+be\s+the\s+same',
            r'shall\s+be\s+the\s+same',
            r'must\s+be\s+equal',
            r'should\s+be\s+identical',
            r'shall\s+expect.*same',
        ]

    @staticmethod
    def clean_latex_text(text: str) -> str:
        """Clean LaTeX while preserving mathematical relations"""
        text = text.replace(r'\geq', ' >= ')
        text = text.replace(r'\leq', ' <= ')
        text = text.replace(r'\neq', ' != ')
        text = text.replace(r'\approx', ' ~= ')
        text = text.replace(r'\equiv', ' == ')
        text = text.replace(r'\ll', ' << ')
        text = text.replace(r'\gg', ' >> ')
        
        text = re.sub(r'\\ge\b', ' >= ', text)
        text = re.sub(r'\\le\b', ' <= ', text)
        text = re.sub(r'\\ne\b', ' != ', text)
        
        text = re.sub(r'\\\(', '', text)
        text = re.sub(r'\\\)', '', text)
        text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\textit\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\texttt\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\emph\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\underline\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\hline', '', text)
        text = re.sub(r'\\\\', ' ', text)
        text = re.sub(r'\\\(\s*\d+>\s*\\\)', '', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def extract_ie_name_from_path(self, field_path: str) -> str:
        pattern = r'\.([a-zA-Z]+-[A-Za-z]+Config|[a-zA-Z]+Config|[a-zA-Z]+-[A-Za-z]+)\.'
        match = re.search(pattern, field_path)
        if match:
            return match.group(1)
        
        parts = field_path.split('.')
        for part in reversed(parts):
            if 'Config' in part or len(part) > 5:
                clean_part = re.sub(r'\[[^\]]+\]', '', part)
                if clean_part and clean_part[0].islower():
                    return clean_part
        
        return "UnknownIE"
    
    def extract_ie_info_from_filename(self, json_path: str) -> Dict:
        basename = os.path.basename(json_path)
        match = re.search(r'\d+_\d+_(.+)\.json$', basename)
        if not match:
            return {'ie_name': '', 'ie_short_name': '', 'ie_prefix': ''}
        
        full_name = match.group(1)
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
    
    def generate_ie_variants(self, ie_info: Dict, field_names: List[str] = None) -> List[str]:
        variants = set()
        
        ie_name = ie_info.get('ie_short_name', '')
        ie_prefix = ie_info.get('ie_prefix', '')
        
        if not ie_name:
            return []
        
        variants.add(ie_name)
        variants.add(ie_name.lower())
        
        camel_spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', ie_name)
        variants.add(camel_spaced)
        variants.add(camel_spaced.lower())
        
        if 'Config' in ie_name:
            variants.add(ie_name.replace('Config', 'Configuration'))
            variants.add(camel_spaced.replace('Config', 'Configuration'))
            variants.add(camel_spaced.replace('Config', 'Configuration').lower())
        
        if ie_prefix:
            variants.add(f"{ie_prefix}-{ie_name}")
            variants.add(f"{ie_prefix.upper()} {camel_spaced}")
            variants.add(f"{ie_prefix} {camel_spaced.lower()}")
            variants.add(f"{ie_prefix.upper()}-{ie_name}")
        
        ie_normalized = ie_name.lower().replace('-', '').replace('_', '')
        for full_term, acronyms in self.acronym_mappings.items():
            if full_term in ie_normalized:
                variants.update(acronyms)
                for acronym in acronyms:
                    variants.add(acronym.upper())
        
        if field_names:
            for field in field_names:
                field_lower = field.lower()
                for prefix, concepts in self.field_prefix_mappings.items():
                    if field_lower.startswith(prefix):
                        variants.update(concepts)
                        for concept in concepts:
                            variants.add(concept.lower())
        
        variants.discard('')
        return sorted(list(variants), key=len, reverse=True)

    def build_section_index(self, lines: List[str], ie_variants: List[str]) -> Dict:
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
                
                relevance_score, matched = self.calculate_section_relevance(
                    section_title, ie_variants
                )
                
                current_section = {
                    'start_line': line_idx,
                    'end_line': len(lines) - 1,
                    'number': section_number,
                    'title': section_title,
                    'relevance_score': relevance_score,
                    'matched_variants': matched
                }
        
        if current_section:
            sections.append(current_section)
        
        if not sections:
            sections.append({
                'start_line': 0,
                'end_line': len(lines) - 1,
                'number': 'N/A',
                'title': 'Entire Document',
                'relevance_score': 0.0,
                'matched_variants': []
            })
        
        line_to_section = {}
        for idx, section in enumerate(sections):
            for line_num in range(section['start_line'], section['end_line'] + 1):
                line_to_section[line_num] = idx
        
        return {
            'sections': sections,
            'line_to_section': line_to_section
        }

    def calculate_section_relevance(self, section_title: str, ie_variants: List[str]) -> Tuple[float, List[str]]:
        score = 0.0
        matched_variants = []
        title_lower = section_title.lower()
        
        for variant in ie_variants:
            variant_lower = variant.lower()
            
            if variant_lower == title_lower:
                score += 50.0
                matched_variants.append(variant)
            elif variant_lower in title_lower or title_lower in variant_lower:
                if len(variant_lower) > 10:
                    score += 30.0
                elif len(variant_lower) > 5:
                    score += 20.0
                else:
                    score += 10.0
                matched_variants.append(variant)
            else:
                variant_words = set(variant_lower.split())
                title_words = set(title_lower.split())
                common_words = variant_words & title_words - {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'for', 'to'}
                
                if len(common_words) >= 2:
                    score += 5.0 * len(common_words)
                    matched_variants.append(variant)
        
        return score, list(set(matched_variants))
    
    @staticmethod
    def get_confidence_level(relevance_score: float) -> str:
        if relevance_score >= 30.0:
            return 'HIGH'
        elif relevance_score >= 15.0:
            return 'MEDIUM'
        elif relevance_score >= 5.0:
            return 'LOW'
        else:
            return 'VERY_LOW'

    def load_field_names_from_list(self, field_list: List[Dict]) -> Tuple[List[str], Dict[str, List[int]]]:
        field_names = set()
        field_id_mapping = {}
        
        for item in field_list:
            if not isinstance(item, dict):
                continue
            
            field_name = item.get('field_name', '')
            field_id = item.get('field_id')
            
            if field_name:
                clean_name = re.sub(r'\[\d+\]', '', field_name)
                field_names.add(clean_name)
                
                if field_id is not None:
                    if clean_name not in field_id_mapping:
                        field_id_mapping[clean_name] = []
                    if field_id not in field_id_mapping[clean_name]:
                        field_id_mapping[clean_name].append(field_id)
        
        return sorted(list(field_names)), field_id_mapping

    def generate_field_pairs(self, field_names: List[str], field_id_mapping: Dict[str, List[int]], 
                            include_self_pairs=True) -> List[Dict]:
        pairs = []
        
        for field1, field2 in combinations(field_names, 2):
            pairs.append({
                'field1': field1,
                'field2': field2,
                'field1_ids': field_id_mapping.get(field1, []),
                'field2_ids': field_id_mapping.get(field2, [])
            })
        
        if include_self_pairs:
            for field in field_names:
                pairs.append({
                    'field1': field,
                    'field2': field,
                    'field1_ids': field_id_mapping.get(field, []),
                    'field2_ids': field_id_mapping.get(field, [])
                })
        
        return pairs
    
    @lru_cache(maxsize=1000)
    def split_camel_case(self, name: str) -> str:
        name = name.replace('-', ' ').replace('_', ' ')
        result = re.sub(r'(?<!^)(?=[A-Z])', ' ', name)
        result = re.sub(r'\s+', ' ', result)
        return result.lower().strip()
    
    @lru_cache(maxsize=1000)
    def normalize_field_name(self, field_name: str) -> str:
        normalized = field_name.lower()
        normalized = re.sub(r'[-_]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
    
    def get_compiled_pattern(self, pattern: str) -> re.Pattern:
        if pattern not in self._compiled_pattern_cache:
            self._compiled_pattern_cache[pattern] = re.compile(pattern, re.IGNORECASE)
        return self._compiled_pattern_cache[pattern]
    
    def get_acronym_patterns(self, field_name: str) -> List[str]:
        acronym_patterns = []
        normalized = field_name.lower().replace('-', '').replace('_', '').replace(' ', '')
        
        for full_term, acronyms in self.acronym_mappings.items():
            if full_term in normalized:
                for acronym in acronyms:
                    escaped_acronym = re.escape(acronym)
                    acronym_patterns.append(r'\b' + escaped_acronym + r'\b')
        
        return acronym_patterns
    
    def create_field_pattern(self, field_name: str) -> str:
        if field_name in self._pattern_cache:
            return self._pattern_cache[field_name]
        
        patterns = []
        
        normalized = self.normalize_field_name(field_name)
        words = normalized.split()
        pattern_parts = [re.escape(word) for word in words]
        pattern1 = r'[\s\-_]*'.join(pattern_parts)
        patterns.append(r'\b' + pattern1 + r'\b')
        
        if re.search(r'[a-z][A-Z]', field_name):
            camel_split = self.split_camel_case(field_name)
            words = camel_split.split()
            pattern2 = r'[\s\-_]*'.join([re.escape(word) for word in words])
            patterns.append(r'\b' + pattern2 + r'\b')
        
        escaped = re.escape(field_name)
        pattern3 = escaped.replace(r'\-', r'[-_]').replace(r'\_', r'[-_]')
        patterns.append(r'\b' + pattern3 + r'\b')
        
        acronym_patterns = self.get_acronym_patterns(field_name)
        if acronym_patterns:
            patterns.extend(acronym_patterns)
        
        unique_patterns = list(set(patterns))
        result = '|'.join([f'({p})' for p in unique_patterns])
        
        self._pattern_cache[field_name] = result
        return result

    def create_loose_pattern(self, field_name: str) -> str:
        cache_key = f"loose_{field_name}"
        if cache_key in self._pattern_cache:
            return self._pattern_cache[cache_key]
        
        critical_suffixes = ['Id', 'Type', 'Config', 'Mode', 'State', 'Index']
        field_parts = re.split(r'[-_]', field_name)
        
        if len(field_parts) <= 2:
            for suffix in critical_suffixes:
                if field_name.endswith(suffix) or field_name.endswith('-' + suffix):
                    result = self.create_field_pattern(field_name)
                    self._pattern_cache[cache_key] = result
                    return result
        
        normalized = self.normalize_field_name(field_name)
        words = normalized.split()
        
        if len(words) > 2:
            main_words = words[:2]
            pattern = r'[\s\-_]*'.join([re.escape(w) for w in main_words])
            result = r'\b' + pattern + r'\b'
        elif len(words) == 2:
            first_word = re.escape(words[0])
            second_word = re.escape(words[1])
            pattern = first_word + r'[\s\-_]+' + second_word
            result = r'\b' + pattern + r'\b'
        else:
            result = self.create_field_pattern(field_name)
        
        self._pattern_cache[cache_key] = result
        return result

    @lru_cache(maxsize=500)
    def generate_abbreviations(self, field_name: str) -> List[str]:
        abbreviations = []
        
        critical_suffixes = ['Id', 'Type', 'Config', 'Configuration', 'Mode', 'List', 
                            'Index', 'Value', 'State', 'Status', 'Info', 'Data']
        
        has_critical_suffix = any(
            field_name.endswith(suffix) or field_name.endswith('-' + suffix) or field_name.endswith('_' + suffix)
            for suffix in critical_suffixes
        )
        
        field_parts = re.split(r'[-_]', field_name)
        if len(field_parts) <= 2 and has_critical_suffix:
            return []
        
        non_critical_suffixes = ['Configuration', 'Config']
        for suffix in non_critical_suffixes:
            pattern = r'[-_]?' + suffix + r'$'
            clean_name = re.sub(pattern, '', field_name, flags=re.IGNORECASE)
            if clean_name != field_name and len(clean_name) >= 6:
                abbreviations.append(clean_name)
        
        if len(field_name) >= 15:
            camel_case_abbr = ''.join([c for c in field_name if c.isupper()])
            if len(camel_case_abbr) >= 4:
                abbreviations.append(camel_case_abbr)
                abbreviations.append(camel_case_abbr.lower())
        
        return list(set(abbreviations))

    def validate_match_quality(self, field_name: str, matched_text: str) -> bool:
        field_lower = field_name.lower()
        matched_lower = matched_text.lower()
        
        if len(matched_text) < 3 and matched_lower != field_lower:
            return False
        
        generic_abbreviations = {'ap', 'id', 'cfg', 'conf', 'typ', 'mod', 'lst', 'pos', 'ref', 'sig'}
        if matched_lower in generic_abbreviations and matched_lower not in field_lower:
            return False
        
        field_words = re.split(r'[-_\s]', field_name.lower())
        if len(field_words) > 1:
            main_word = field_words[0]
            if len(main_word) > 3 and main_word not in matched_lower:
                if not self.is_known_abbreviation(field_name, matched_text):
                    return False
        
        return True
    
    def is_known_abbreviation(self, field_name: str, matched_text: str) -> bool:
        field_lower = field_name.lower().replace('-', '').replace('_', '')
        matched_lower = matched_text.lower()
        
        normalized_field = field_lower.replace(' ', '')
        for full_term, acronyms in self.acronym_mappings.items():
            if full_term in normalized_field:
                for acronym in acronyms:
                    if matched_lower == acronym.lower().replace('-', ''):
                        return True
        
        return False
    
    def contains_constraint_keyword_fast(self, sentence: str) -> Tuple[bool, str]:
        match = self.constraint_pattern.search(sentence)
        if match:
            return True, match.group(1)
        return False, ""
    
    def contains_self_reference_keywords(self, text: str, field_name: str) -> bool:
        text_lower = text.lower()
        field_lower = field_name.lower()
        
        if field_lower not in text_lower:
            return False
        
        for pattern in self.self_reference_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def get_context_lines(self, lines: List[str], line_idx: int, context_size: int = 5) -> List[str]:
        start_idx = max(0, line_idx - context_size)
        end_idx = min(len(lines), line_idx + context_size + 1)
        
        context = []
        for i in range(start_idx, end_idx):
            line = lines[i].strip()
            if line:
                context.append(line)
        
        return context
    
    def batch_find_field_occurrences(self, lines: List[str], field_patterns: Dict[str, Dict]) -> Dict[str, List[Tuple[int, str]]]:
        field_occurrences = {field: [] for field in field_patterns}
        
        for line_idx, line in enumerate(lines):
            if len(line) < 20:
                continue
            
            clean_line = self.clean_latex_text(line)
            
            for field_name, patterns in field_patterns.items():
                for pattern_type, pattern in patterns.items():
                    if pattern:
                        compiled_pattern = self.get_compiled_pattern(pattern)
                        matches = compiled_pattern.finditer(clean_line)
                        for match in matches:
                            field_occurrences[field_name].append((line_idx, match.group(0)))
        
        return field_occurrences
    
    def extract_constraints_from_file_optimized(self, file_path: str, field_pairs: List[Dict], 
                                                field_patterns: Dict[str, Dict],
                                                ie_variants: List[str],
                                                include_self_constraints: bool = True) -> List[Dict]:
        constraints = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return constraints
        
        section_index = self.build_section_index(lines, ie_variants)
        LOW_RELEVANCE_THRESHOLD = 0.0
        field_occurrences = self.batch_find_field_occurrences(lines, field_patterns)
        
        for pair_info in field_pairs:
            field1 = pair_info['field1']
            field2 = pair_info['field2']
            field1_ids = pair_info['field1_ids']
            field2_ids = pair_info['field2_ids']
            
            is_self_pair = (field1 == field2)
            
            if is_self_pair and include_self_constraints:
                if not field_occurrences[field1]:
                    continue
                
                processed_lines = set()
                
                for line_idx, match_text in field_occurrences[field1]:
                    if line_idx in processed_lines:
                        continue
                    
                    line = lines[line_idx].strip()
                    clean_line = self.clean_latex_text(line)
                    
                    pattern = field_patterns[field1]['standard']
                    compiled_pattern = self.get_compiled_pattern(pattern)
                    matches = list(compiled_pattern.finditer(clean_line))
                    
                    if len(matches) >= 2 or self.contains_self_reference_keywords(clean_line, field1):
                        has_constraint, keyword = self.contains_constraint_keyword_fast(clean_line)
                        if has_constraint:
                            context_lines = self.get_context_lines(lines, line_idx, context_size=5)
                            extended_text = ' '.join(context_lines)
                            clean_extended = self.clean_latex_text(extended_text)
                            
                            if self.contains_constraint_keyword_fast(clean_extended)[0]:
                                section_info = self.get_section_info_for_line(line_idx, section_index)
                                
                                if section_info['ie_relevance_score'] >= LOW_RELEVANCE_THRESHOLD or \
                                   section_info['ie_relevance_score'] == 0.0:
                                    constraints.append({
                                        "fields": [field1, field2],
                                        "field_ids": [field1_ids, field2_ids],
                                        "matched_fields": [match_text, match_text],
                                        "original_sentence": clean_extended,
                                        "source_file": os.path.basename(file_path),
                                        "constraint_keyword": keyword,
                                        "is_self_reference": True,
                                        **section_info
                                    })
                                    processed_lines.add(line_idx)
                                
            elif not is_self_pair:
                if not field_occurrences[field1] or not field_occurrences[field2]:
                    continue
                
                for line1_idx, match1_text in field_occurrences[field1]:
                    for line2_idx, match2_text in field_occurrences[field2]:
                        if abs(line1_idx - line2_idx) <= 10:
                            min_idx = min(line1_idx, line2_idx)
                            max_idx = max(line1_idx, line2_idx)
                            
                            context_lines = []
                            for i in range(max(0, min_idx - 2), min(len(lines), max_idx + 3)):
                                line = lines[i].strip()
                                if line:
                                    context_lines.append(line)
                            
                            text = ' '.join(context_lines)
                            clean_text = self.clean_latex_text(text)
                            
                            has_constraint, keyword = self.contains_constraint_keyword_fast(clean_text)
                            if has_constraint:
                                if self.strict_mode:
                                    if len(match1_text) < 3 or len(match2_text) < 3:
                                        continue
                                
                                section_info = self.get_section_info_for_line(line1_idx, section_index)
                                
                                if section_info['ie_relevance_score'] >= LOW_RELEVANCE_THRESHOLD or \
                                   section_info['ie_relevance_score'] == 0.0:
                                    constraints.append({
                                        "fields": [field1, field2],
                                        "field_ids": [field1_ids, field2_ids],
                                        "matched_fields": [match1_text, match2_text],
                                        "original_sentence": clean_text,
                                        "source_file": os.path.basename(file_path),
                                        "constraint_keyword": keyword,
                                        "is_self_reference": False,
                                        **section_info
                                    })
                                    break
        
        return constraints
    
    def get_section_info_for_line(self, line_idx: int, section_index: Dict) -> Dict:
        if line_idx in section_index['line_to_section']:
            section_idx = section_index['line_to_section'][line_idx]
            section = section_index['sections'][section_idx]
            
            return {
                'section_number': section['number'],
                'section_title': section['title'],
                'ie_relevance_score': section['relevance_score'],
                'matched_ie_variants': section['matched_variants'],
                'confidence': self.get_confidence_level(section['relevance_score'])
            }
        else:
            return {
                'section_number': 'N/A',
                'section_title': 'Unknown',
                'ie_relevance_score': 0.0,
                'matched_ie_variants': [],
                'confidence': 'VERY_LOW'
            }
    
    def precompute_field_patterns(self, field_names: List[str]) -> Dict[str, Dict]:
        field_patterns = {}
        
        for field in field_names:
            patterns = {
                'standard': self.create_field_pattern(field),
                'loose': self.create_loose_pattern(field),
                'abbreviations': []
            }
            
            abbrevs = self.generate_abbreviations(field)
            if abbrevs:
                abbrev_patterns = [r'\b' + re.escape(abbr) + r'\b' for abbr in abbrevs]
                if abbrev_patterns:
                    patterns['abbreviations'] = '|'.join(abbrev_patterns)
            
            field_patterns[field] = patterns
        
        return field_patterns

# ============================================================================
# Processing function
# ============================================================================

def process_single_ie_adapted(ie_json_path: str, spec_dir: str, output_dir: str,
                              debug_mode=False, strict_mode=True, 
                              use_multiprocessing=True, include_self_constraints=True,
                              use_all_pairs=False):
    """Process single IE"""
    ie_name = os.path.splitext(os.path.basename(ie_json_path))[0]
    output_path = os.path.join(output_dir, f"{ie_name}_constraints.json")
    
    print(f"\n{'='*60}")
    print(f"Processing IE: {ie_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    extractor = EnhancedConstraintExtractor(debug=debug_mode, strict_mode=strict_mode)
    
    try:
        with open(ie_json_path, 'r') as f:
            field_list = json.load(f)
        
        if not field_list or not isinstance(field_list, list):
            raise ValueError("Invalid field list format")
        
        field_names, field_id_mapping = extractor.load_field_names_from_list(field_list)
        print(f"Found {len(field_names)} unique fields")
        
        if use_all_pairs:
            field_pairs = extractor.generate_field_pairs(field_names, field_id_mapping, 
                                                         include_self_pairs=include_self_constraints)
        else:
            pairs = []
            for i in range(len(field_names) - 1):
                field1 = field_names[i]
                field2 = field_names[i + 1]
                pairs.append({
                    'field1': field1,
                    'field2': field2,
                    'field1_ids': field_id_mapping.get(field1, []),
                    'field2_ids': field_id_mapping.get(field2, [])
                })
            field_pairs = pairs
        
        print(f"Generated {len(field_pairs)} field pairs")
        
        ie_info = extractor.extract_ie_info_from_filename(ie_json_path)
        ie_variants = extractor.generate_ie_variants(ie_info, field_names)
        print(f"IE variants: {len(ie_variants)}")
        
        field_patterns = extractor.precompute_field_patterns(field_names)
        
        # ===== FIXED: Always search ALL specification files =====
        # Previous logic only used one file if found, causing 38.211 to be skipped
        spec_files = []
        for ext in ['.md', '.txt']:
            spec_files.extend(list(Path(spec_dir).glob(f'*{ext}')))
        
        print(f"Found {len(spec_files)} specification files to process")
        for idx, f in enumerate(spec_files[:5], 1):
            print(f"  {idx}. {Path(f).name}")
        if len(spec_files) > 5:
            print(f"  ... and {len(spec_files) - 5} more")
        # ===== END OF FIX =====
        
        all_constraints = []
        
        if use_multiprocessing and len(spec_files) > 1:
            process_args = [
                (str(f), field_pairs, field_patterns, strict_mode, include_self_constraints, ie_variants)
                for f in spec_files
            ]
            
            with Pool(processes=min(cpu_count(), len(spec_files))) as pool:
                for constraints in pool.imap_unordered(process_file_for_multiprocessing, process_args):
                    all_constraints.extend(constraints)
        else:
            for idx, spec_file in enumerate(spec_files):
                print(f"  Processing [{idx+1}/{len(spec_files)}]: {Path(spec_file).name}", end="")
                constraints = extractor.extract_constraints_from_file_optimized(
                    str(spec_file), field_pairs, field_patterns, ie_variants, include_self_constraints
                )
                all_constraints.extend(constraints)
                print(f" → {len(constraints)} constraints")
        
        unique_constraints = []
        seen_sentences = set()
        
        for constraint in all_constraints:
            sentence = constraint['original_sentence']
            fields_key = tuple(sorted(constraint['fields']))
            unique_key = (fields_key, sentence[:200])
            
            if unique_key not in seen_sentences:
                seen_sentences.add(unique_key)
                unique_constraints.append(constraint)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unique_constraints, f, ensure_ascii=False, indent=2)
        
        elapsed_time = time.time() - start_time
        
        self_ref_count = sum(1 for c in unique_constraints if c.get('is_self_reference', False))
        confidence_stats = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'VERY_LOW': 0}
        for c in unique_constraints:
            conf = c.get('confidence', 'VERY_LOW')
            confidence_stats[conf] += 1
        
        print(f"\n{'='*60}")
        print(f"Found {len(unique_constraints)} unique constraints")
        print(f"  - Self-reference: {self_ref_count}")
        print(f"  - Cross-field: {len(unique_constraints) - self_ref_count}")
        print(f"Confidence: HIGH={confidence_stats['HIGH']}, MEDIUM={confidence_stats['MEDIUM']}, "
              f"LOW={confidence_stats['LOW']}, VERY_LOW={confidence_stats['VERY_LOW']}")
        print(f"Processing time: {elapsed_time:.2f} seconds")
        print(f"Results saved to: {output_path}")
        
        return {
            'ie_name': ie_name,
            'total_constraints': len(unique_constraints),
            'self_reference_constraints': self_ref_count,
            'cross_field_constraints': len(unique_constraints) - self_ref_count,
            'confidence_stats': confidence_stats,
            'output_file': output_path,
            'processing_time': elapsed_time
        }
        
    except Exception as e:
        print(f"Error during constraint extraction: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ie_name': ie_name,
            'total_constraints': 0,
            'output_file': output_path,
            'processing_time': 0,
            'error': str(e)
        }

def batch_process_ies_adapted(ie_dir: str, spec_dir: str, output_dir: str,
                              debug_mode=False, strict_mode=True,
                              use_multiprocessing=True, include_self_constraints=True,
                              use_all_pairs=False):
    """Batch Process IE"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    ie_files = list(Path(ie_dir).glob("*.json"))
    ie_files = [f for f in ie_files if not f.name.startswith('_')]
    
    if not ie_files:
        print(f"No valid JSON files found in {ie_dir}")
        return
    
    print(f"\n{'='*60}")
    print(f"Batch Processing {len(ie_files)} IE files")
    print(f"Field Pair Strategy: {'All Pairs' if use_all_pairs else 'Adjacent Pairs'}")
    print(f"{'='*60}")
    
    total_start_time = time.time()
    results = []
    
    for idx, ie_file in enumerate(ie_files, 1):
        print(f"\n[{idx}/{len(ie_files)}]", end="")
        
        try:
            result = process_single_ie_adapted(
                str(ie_file), spec_dir, output_dir,
                debug_mode, strict_mode,
                use_multiprocessing, include_self_constraints,
                use_all_pairs
            )
            results.append(result)
        except Exception as e:
            print(f"\nError processing {ie_file}: {e}")
            continue
    
    total_elapsed_time = time.time() - total_start_time
    
    print(f"\n{'='*60}")
    print("Batch Processing Summary")
    print(f"{'='*60}")
    print(f"Total IE files processed: {len(results)}")
    print(f"Total processing time: {total_elapsed_time:.2f} seconds")
    if len(results) > 0:
        print(f"Average time per IE: {total_elapsed_time/len(results):.2f} seconds")
    
    total_constraints = sum(r['total_constraints'] for r in results)
    print(f"Total constraints found: {total_constraints}")
    
    summary_path = os.path.join(output_dir, "batch_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_files': len(results),
            'total_constraints': total_constraints,
            'total_processing_time': total_elapsed_time,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    print(f"\nBatch summary saved to: {summary_path}")

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced Intra-IE Constraint Extractor - FIXED VERSION'
    )
    parser.add_argument('--ie_dir', default=DEFAULT_IE_DIR, help='IE JSON directory')
    parser.add_argument('--spec_dir', default=DEFAULT_SPEC_DIR, help='Specification directory')
    parser.add_argument('--output_dir', default=DEFAULT_OUTPUT_DIR, help='Output directory')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS, help='Number of workers')
    parser.add_argument('--all-pairs', action='store_true', help='Generate all field pairs (vs adjacent)')
    parser.add_argument('--no-self', action='store_true', help='Disable self-reference constraints')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-strict', action='store_true', help='Disable strict matching mode')
    
    args = parser.parse_args()
    
    global GENERATE_ALL_PAIRS
    GENERATE_ALL_PAIRS = args.all_pairs
    
    batch_process_ies_adapted(
        args.ie_dir,
        args.spec_dir,
        args.output_dir,
        debug_mode=args.debug,
        strict_mode=not args.no_strict,
        use_multiprocessing=True,
        include_self_constraints=not args.no_self,
        use_all_pairs=args.all_pairs
    )

if __name__ == "__main__":
    main()