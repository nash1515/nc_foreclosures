/**
 * Cases API client
 */

const API_BASE = '/api';

/**
 * Fetch cases with filters and pagination
 */
export async function fetchCases({
  page = 1,
  pageSize = 20,
  classification = '',
  county = '',
  search = '',
  startDate = '',
  endDate = '',
  watchlistOnly = false,
  sortBy = 'file_date',
  sortOrder = 'desc'
} = {}) {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
    sort_by: sortBy,
    sort_order: sortOrder
  });

  if (classification) params.append('classification', classification);
  if (county) params.append('county', county);
  if (search) params.append('search', search);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (watchlistOnly) params.append('watchlist_only', 'true');

  const response = await fetch(`${API_BASE}/cases?${params}`, {
    credentials: 'include'
  });
  if (!response.ok) {
    throw new Error('Failed to fetch cases');
  }
  return response.json();
}

/**
 * Fetch single case detail
 */
export async function fetchCase(caseId) {
  const response = await fetch(`${API_BASE}/cases/${caseId}`, {
    credentials: 'include'
  });
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Case not found');
    }
    throw new Error('Failed to fetch case');
  }
  return response.json();
}

/**
 * Add case to watchlist
 */
export async function addToWatchlist(caseId) {
  const response = await fetch(`${API_BASE}/cases/${caseId}/watchlist`, {
    method: 'POST',
    credentials: 'include'
  });
  if (!response.ok) {
    throw new Error('Failed to add to watchlist');
  }
  return response.json();
}

/**
 * Remove case from watchlist
 */
export async function removeFromWatchlist(caseId) {
  const response = await fetch(`${API_BASE}/cases/${caseId}/watchlist`, {
    method: 'DELETE',
    credentials: 'include'
  });
  if (!response.ok) {
    throw new Error('Failed to remove from watchlist');
  }
  return response.json();
}

/**
 * Update case collaboration fields
 */
export async function updateCase(caseId, updates) {
  const response = await fetch(`${API_BASE}/cases/${caseId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(updates)
  });
  if (!response.ok) {
    let errorMsg = 'Failed to update case';
    try {
      const error = await response.json();
      errorMsg = error.error || errorMsg;
    } catch (e) {
      // Response wasn't JSON (e.g., HTML error page)
      errorMsg = `Server error: ${response.status}`;
    }
    throw new Error(errorMsg);
  }
  return response.json();
}
