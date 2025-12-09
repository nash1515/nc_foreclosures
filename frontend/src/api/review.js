const API_BASE = '/api/review';

export async function getDailyReview(date) {
  const params = date ? `?date=${date}` : '';
  const response = await fetch(`${API_BASE}/daily${params}`);
  if (!response.ok) throw new Error('Failed to fetch review data');
  return response.json();
}

export async function approveAllForeclosures(date) {
  const response = await fetch(`${API_BASE}/foreclosures/approve-all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date })
  });
  if (!response.ok) throw new Error('Failed to approve all foreclosures');
  return response.json();
}

export async function rejectForeclosures(caseIds) {
  const response = await fetch(`${API_BASE}/foreclosures/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_ids: caseIds })
  });
  if (!response.ok) throw new Error('Failed to reject foreclosures');
  return response.json();
}

export async function addSkippedCases(skippedIds) {
  const response = await fetch(`${API_BASE}/skipped/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skipped_ids: skippedIds })
  });
  if (!response.ok) throw new Error('Failed to add skipped cases');
  return response.json();
}

export async function dismissSkippedCases(skippedIds) {
  const response = await fetch(`${API_BASE}/skipped/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skipped_ids: skippedIds })
  });
  if (!response.ok) throw new Error('Failed to dismiss skipped cases');
  return response.json();
}

export async function getPendingCount() {
  const response = await fetch(`${API_BASE}/pending-count`);
  if (!response.ok) throw new Error('Failed to fetch pending count');
  return response.json();
}
