# Statistical Approach Implementation

## Overview

This document describes the transition from hardcoded domain-specific patterns to a universal statistical approach in the Korean RAG system. The new approach eliminates all hardcoded word lists and patterns, making the system dialect-agnostic and domain-agnostic.

## Changes Made

### 1. SimpleStatFilter (`backend/rag/query_rewriter.py`)

**Removed Hardcoded Patterns:**
- ✅ 15 hardcoded stop words (그, 이, 저, 것, 등, 및, ...)
- ✅ 8 hardcoded verb endings (하다, 되다, 하는, 하고, ...)

**New Statistical Methods:**

#### Shannon Entropy
```python
def _calculate_entropy(self, word: str) -> float:
    """
    Calculate Shannon entropy of character distribution.
    Formula: H(X) = -Σ p(x) * log2(p(x))

    Higher entropy = more information content = more likely content word
    """
```

**Thresholds:**
- Normal mode: entropy ≥ 1.2, diversity ≥ 0.4
- Strict mode: entropy ≥ 2.0, diversity ≥ 0.6

#### Character Diversity
```python
diversity = len(set(word)) / len(word)
```

Higher diversity indicates more unique characters, suggesting a content word rather than a function word.

#### Repetitive Suffix Detection
```python
def _has_repetitive_suffix(self, word: str) -> bool:
    """
    Detect repetitive suffix patterns (statistical approach).
    NO HARDCODED patterns - pure statistical detection.
    """
```

### 2. ResponsePostProcessor (`backend/rag/response_postprocessor.py`)

**Removed Hardcoded Patterns:**
- ✅ 17 hardcoded Korean particles (은, 는, 이, 가, 을, 를, ...)

**New Statistical Entity Normalization:**

```python
def _normalize_entity(self, entity: str) -> str:
    """
    Normalize entity using STATISTICAL suffix trimming - NO HARDCODING.

    Strategy: Iteratively trim 1-2 characters from end and check if
    shorter form is more "canonical" (has higher character diversity).

    This works for ANY Korean dialect without hardcoded particle lists.
    """
```

**Character Diversity Calculation:**
```python
def _calculate_diversity(self, text: str) -> float:
    """
    Calculate character diversity (unique chars / total chars).
    Higher diversity = more information content = more likely root form.
    """
```

### 3. Kept Minimal Structural Patterns

The following patterns were **intentionally kept** as they serve grammatical/structural purposes:

#### Meta-Question Detection (`query_rewriter.py`)
```python
meta_keywords = ("요약", "정리", "간단히", "짧게", "다시", "설명")
```
These are grammatical markers for query intent classification, not content filtering.

#### Pronoun Tokens (Legacy, Currently Unused)
```python
pronoun_tokens = ("그", "이", "저", "그것", "이것", "저것")
```
Kept for backward compatibility. Could be replaced with statistical anaphora resolution in future.

## Benefits

1. **Dialect-Agnostic**: Works with any Korean dialect without modification
2. **Domain-Agnostic**: No hardcoded domain-specific vocabulary
3. **Universal**: Statistical measures (entropy, diversity) work across languages
4. **Maintainable**: No need to update hardcoded word lists
5. **Scalable**: Automatically adapts to new vocabulary and domains

## Testing

### Test Coverage

#### SimpleStatFilter Tests (`tests/test_statistical_filter.py`)
- ✅ Entropy calculation for content words
- ✅ Character diversity calculation
- ✅ Repetitive suffix detection
- ✅ Shannon entropy formula verification
- ✅ No hardcoded patterns verification

#### ResponsePostProcessor Tests (`tests/test_response_postprocessor_statistical.py`)
- ✅ Statistical entity normalization
- ✅ Character diversity calculation
- ✅ No hardcoded particles verification
- ✅ Full text cleaning integration

### Test Results

All tests passing:
```
tests/test_statistical_filter.py::test_statistical_filter_entropy PASSED
tests/test_statistical_filter.py::test_statistical_filter_diversity PASSED
tests/test_statistical_filter.py::test_statistical_filter_repetitive_suffix PASSED
tests/test_statistical_filter.py::test_statistical_filter_entropy_calculation PASSED
tests/test_statistical_filter.py::test_no_hardcoded_patterns PASSED

tests/test_response_postprocessor_statistical.py::test_normalize_entity_statistical PASSED
tests/test_response_postprocessor_statistical.py::test_calculate_diversity PASSED
tests/test_response_postprocessor_statistical.py::test_no_hardcoded_particles PASSED
tests/test_response_postprocessor_statistical.py::test_clean_text_integration PASSED
```

## Technical Details

### Shannon Entropy Formula

```
H(X) = -Σ p(x) * log2(p(x))
```

Where:
- `p(x)` is the probability of character `x`
- Higher entropy indicates more information content
- Content words typically have higher entropy than function words

### Character Diversity Formula

```
diversity = |unique_characters| / |total_characters|
```

Where:
- Higher diversity indicates more unique characters
- Content words typically have higher diversity
- Function words often have repetitive characters

### Statistical Suffix Trimming

The algorithm iteratively tries removing 1-2 characters from the end of an entity and checks if the shorter form has equal or higher character diversity. This works because:

1. Korean particles (은, 는, 이, 가, ...) often reduce diversity by adding common characters
2. The root form of a word typically has higher diversity
3. No hardcoded list of particles is needed

## Examples

### Before (Hardcoded)
```python
STOP_WORDS = ["그", "이", "저", "것", ...]  # 15 words
particles = ["은", "는", "이", "가", ...]    # 17 particles
```

### After (Statistical)
```python
# Shannon entropy calculation
entropy = -Σ p(x) * log2(p(x))

# Character diversity
diversity = len(set(word)) / len(word)

# Statistical suffix detection
if candidate_diversity >= best_diversity:
    best_form = candidate
```

## Migration Notes

### Breaking Changes
None. The API remains the same.

### Behavior Changes
- Entity normalization may trim more aggressively in some cases
- Words with equal character diversity prefer shorter forms
- This is expected behavior for a pure statistical approach

## Future Improvements

1. **Adaptive Thresholds**: Learn optimal entropy/diversity thresholds from training data
2. **Statistical Anaphora Resolution**: Replace pronoun_tokens with statistical method
3. **Multilingual Support**: Extend statistical approach to other languages
4. **Performance Metrics**: Track effectiveness on diverse Korean dialects

## References

- Shannon Entropy: https://en.wikipedia.org/wiki/Entropy_(information_theory)
- Korean Morphology: https://en.wikipedia.org/wiki/Korean_grammar
- Statistical NLP: https://nlp.stanford.edu/

## Contact

For questions or issues related to the statistical approach, please open an issue on the project repository.

---

**Last Updated**: 2025-10-13
**Version**: 1.0
