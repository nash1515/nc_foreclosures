"""Extraction module for structured data from OCR text and case events."""

from extraction.extractor import (
    extract_property_address,
    extract_bid_amount,
    extract_upset_deadline,
    extract_sale_date,
    extract_legal_description,
    extract_trustee_name,
    extract_attorney_info,
    extract_all_from_case,
    update_case_with_extracted_data
)
from extraction.classifier import classify_case, update_case_classification

__all__ = [
    'extract_property_address',
    'extract_bid_amount',
    'extract_upset_deadline',
    'extract_sale_date',
    'extract_legal_description',
    'extract_trustee_name',
    'extract_attorney_info',
    'extract_all_from_case',
    'update_case_with_extracted_data',
    'classify_case',
    'update_case_classification'
]
