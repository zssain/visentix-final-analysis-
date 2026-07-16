# F-001 Recompute Report

**Date:** 2026-06-29
**Formula:** F-001_v1 = Σ(component × weight), weights={"authority": 0.25, "freshness": 0.25, "completeness": 0.25, "extraction_confidence": 0.25}
**Sources:** 303
**Drifted (delta > 0.001):** 0

## Summary

All 303 source_record rows were recomputed using the F-001_v1 formula.
The recomputed values were written to derived_data_item (object_type='source').
The original source_record.source_reliability_score was NOT modified.

## Result: Zero Drift

All stored scores match the recomputed values exactly.
The original corpus F-001 scores are consistent with the formula definition.

## Conclusion

source_record.source_reliability_score remains UNTOUCHED.
Recomputed values are in derived_data_item for lineage/verification.
