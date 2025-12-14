# Zillow QuickLink Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add clickable Zillow links to Case Detail and Dashboard pages using property addresses.

**Architecture:** Pure frontend implementation. Create a URL helper utility to format addresses into Zillow URLs. Add brand icons (Zillow, PropWire) as SVG assets. Update Case Detail QuickLinks section and add quicklink icons column to Dashboard table.

**Tech Stack:** React, Ant Design, Vite

---

## Task 1: Create URL Helper Utility

**Files:**
- Create: `frontend/src/utils/urlHelpers.js`

**Step 1: Create the utility file**

Create file with formatZillowUrl function:
- Takes address string
- Returns null if empty/falsy
- Removes special characters (commas, periods, #, etc.)
- Replaces spaces with hyphens
- Returns formatted URL: `https://www.zillow.com/homes/{formatted}_rb/`

Example:
```javascript
export const formatZillowUrl = (address) => {
  if (!address) return null;

  // Remove special characters and replace spaces with hyphens
  const formatted = address
    .replace(/[.,#]/g, '')
    .replace(/\s+/g, '-')
    .toLowerCase();

  return `https://www.zillow.com/homes/${formatted}_rb/`;
};
```

**Step 2: Verify build passes**

Run: `cd /home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

---

## Task 2: Add Brand Icon Assets

**Files:**
- Create: `frontend/src/assets/ZillowIcon.jsx`
- Create: `frontend/src/assets/PropWireIcon.jsx`

**Step 1: Create Zillow icon component**

Create a React component that renders the Zillow "Z" logo as an inline SVG. Use the official Zillow blue color (#006AFF). Make it accept size and style props for flexibility.

Example:
```javascript
import React from 'react';

export const ZillowIcon = ({ size = 16, style = {}, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    style={style}
    {...props}
  >
    {/* Zillow "Z" logo path */}
    <path d="M..." fill="#006AFF"/>
  </svg>
);
```

**Step 2: Create PropWire icon component**

Create a React component that renders the PropWire logo as an inline SVG. Use appropriate colors. Make it accept size and style props.

Example:
```javascript
import React from 'react';

export const PropWireIcon = ({ size = 16, style = {}, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    style={style}
    {...props}
  >
    {/* PropWire logo path */}
    <path d="M..." fill="#0066CC"/>
  </svg>
);
```

**Step 3: Verify build passes**

Run: `cd /home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink/frontend && npm run build`

**Step 4: Commit**

---

## Task 3: Update Case Detail QuickLinks

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx`

**Step 1: Import the new utilities and icons**

Add imports at the top of the file:
```javascript
import { formatZillowUrl } from '../utils/urlHelpers';
import { ZillowIcon } from '../assets/ZillowIcon';
```

**Step 2: Update Zillow button in QuickLinks section (around line 225)**

Replace the disabled Zillow button with:
```javascript
<Tooltip title={!propertyAddress ? "No address available" : "Search on Zillow"}>
  <Button
    icon={<ZillowIcon size={16} style={{ opacity: !propertyAddress ? 0.4 : 1 }} />}
    disabled={!propertyAddress}
    onClick={() => propertyAddress && window.open(formatZillowUrl(propertyAddress), '_blank')}
  >
    Zillow
  </Button>
</Tooltip>
```

**Step 3: Verify build passes**

Run: `cd /home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink/frontend && npm run build`

**Step 4: Manual test**

Start dev server, navigate to a case with address, verify Zillow link works

**Step 5: Commit**

---

## Task 4: Add QuickLinks Column to Dashboard

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`

**Step 1: Import utilities and icons**

Add imports at the top:
```javascript
import { formatZillowUrl } from '../utils/urlHelpers';
import { ZillowIcon } from '../assets/ZillowIcon';
import { PropWireIcon } from '../assets/PropWireIcon';
import { FileTextOutlined, HomeOutlined } from '@ant-design/icons';
import { Space, Tooltip } from 'antd'; // Ensure Tooltip is imported
```

**Step 2: Add QuickLinks column to table columns array**

Add a new column after Property Address (around line 210):
```javascript
{
  title: 'Links',
  key: 'quicklinks',
  width: 120,
  fixed: 'right',
  render: (_, record) => {
    const hasAddress = record.property_address;

    return (
      <Space size="small">
        <Tooltip title={hasAddress ? "Search on Zillow" : "No address available"}>
          <span
            onClick={() => hasAddress && window.open(formatZillowUrl(record.property_address), '_blank')}
            style={{
              cursor: hasAddress ? 'pointer' : 'not-allowed',
              opacity: hasAddress ? 1 : 0.4,
              display: 'inline-flex',
              alignItems: 'center'
            }}
          >
            <ZillowIcon size={16} />
          </span>
        </Tooltip>

        <Tooltip title="PropWire - Coming soon">
          <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
            <PropWireIcon size={16} />
          </span>
        </Tooltip>

        <Tooltip title="Deed - Coming soon">
          <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
            <FileTextOutlined style={{ fontSize: 16 }} />
          </span>
        </Tooltip>

        <Tooltip title="Property Info - Coming soon">
          <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
            <HomeOutlined style={{ fontSize: 16 }} />
          </span>
        </Tooltip>
      </Space>
    );
  }
}
```

**Step 3: Style the icons**

- Active icons: normal color, cursor pointer, onClick opens link
- Disabled icons: grey color (opacity 0.4), cursor not-allowed, no onClick

**Step 4: Verify build passes**

Run: `cd /home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink/frontend && npm run build`

**Step 5: Manual test**

Start dev server, verify Dashboard shows Links column with Zillow active and others disabled

**Step 6: Commit**

---

## Task 5: Final Verification and Cleanup

**Step 1: Full build verification**

Run: `cd /home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink/frontend && npm run build`
Expected: Clean build with no errors

**Step 2: Manual end-to-end test**

- Dashboard: Verify Links column shows, Zillow clickable, others disabled
- Case Detail: Verify Zillow link works in QuickLinks section
- Test with case that has no address: Verify disabled state

**Step 3: Final commit if any cleanup needed**

---

## Implementation Notes

- All paths are absolute from worktree root: `/home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink`
- Frontend directory: `/home/ahn/projects/nc_foreclosures/.worktrees/zillow-quicklink/frontend`
- Property address field: `record.property_address` or `propertyAddress` depending on context
- Use existing Ant Design components (Button, Space, Tooltip) for consistency
- All external links should open in new tab (`window.open(..., '_blank')`)
