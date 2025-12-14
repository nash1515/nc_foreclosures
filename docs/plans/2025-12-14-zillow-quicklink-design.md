# Zillow QuickLink Integration Design

## Overview

Add Zillow property links to the NC Foreclosures application. This is the first enrichment feature, implemented in isolation before integrating with the main system.

## Scope

- Generate clickable Zillow links from property addresses
- Display in Case Detail page (existing QuickLinks section)
- Add quicklink icons to Dashboard page
- No API calls, no scraping, no database changes

## URL Construction

**Zillow URL Format:**
```
https://www.zillow.com/homes/{formatted-address}_rb/
```

**Address Formatting Rules:**
- Replace spaces with hyphens: `123 Main St` → `123-Main-St`
- Include city, state, zip: `123-Main-St-Raleigh-NC-27601`
- Remove special characters (commas, periods, #, etc.)

**Example:**
- Input: `123 Main St, Raleigh, NC 27601`
- Output: `https://www.zillow.com/homes/123-Main-St-Raleigh-NC-27601_rb/`

## Case Detail Page Changes

- Populate existing Zillow quicklink placeholder with constructed URL
- Use Zillow "Z" brand logo
- Link opens in new tab
- If no property address: show greyed out / disabled state

## Dashboard Page Changes

Add quicklink icons to each case row:

| Quicklink | Icon | Behavior |
|-----------|------|----------|
| Zillow | Zillow "Z" logo | Constructed URL from address |
| PropWire | PropWire logo | Disabled for now |
| County Deed | FileTextOutlined | Disabled for now |
| County Property | HomeOutlined | Disabled for now |

NC Courts already linked via case number (no additional icon needed).

**Disabled state for future links:**
- Greyed out appearance
- Tooltip: "Coming soon"
- No click action

## Files to Create/Modify

1. **`frontend/src/utils/urlHelpers.ts`** (new)
   - `formatZillowUrl(address: string): string | null`
   - Returns null if address is empty/invalid

2. **`frontend/src/assets/`** (new icons)
   - Zillow logo SVG
   - PropWire logo SVG

3. **Case Detail page component**
   - Update QuickLinks section to use `formatZillowUrl()`
   - Active Zillow link when address exists, disabled otherwise

4. **Dashboard page component**
   - Add quicklink icons column/section to case rows
   - Zillow active, others disabled with "Coming soon" tooltip

## Technical Notes

- Pure frontend implementation
- No backend changes
- No database changes
- No new API endpoints
- Address data already available in case responses

## Error Handling

- Missing/empty address: Show disabled/greyed Zillow icon
- Malformed address: Construct URL anyway, let Zillow handle search/404
