/**
 * Analysis API client
 */

const API_BASE = '/api/cases';

/**
 * Fetch analysis results for a case
 */
export async function fetchAnalysis(caseId) {
  const response = await fetch(`${API_BASE}/${caseId}/analysis`, {
    credentials: 'include'
  });

  if (response.status === 404) {
    return null; // No analysis yet
  }

  if (!response.ok) {
    throw new Error('Failed to fetch analysis');
  }

  return response.json();
}

/**
 * Resolve a discrepancy (accept or reject AI value)
 */
export async function resolveDiscrepancy(caseId, index, action) {
  const response = await fetch(
    `${API_BASE}/${caseId}/analysis/discrepancies/${index}/resolve`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    }
  );

  if (!response.ok) {
    let errorMsg = 'Failed to resolve discrepancy';
    try {
      const error = await response.json();
      errorMsg = error.error || errorMsg;
    } catch (e) {
      errorMsg = `Server error: ${response.status}`;
    }
    throw new Error(errorMsg);
  }

  return response.json();
}

/**
 * Rerun analysis for a case
 */
export async function rerunAnalysis(caseId) {
  const response = await fetch(
    `${API_BASE}/${caseId}/analysis/rerun`,
    {
      method: 'POST',
      credentials: 'include'
    }
  );

  if (!response.ok) {
    throw new Error('Failed to rerun analysis');
  }

  return response.json();
}
